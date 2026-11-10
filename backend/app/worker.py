from __future__ import annotations

import asyncio
import os
import signal
import socket
from uuid import uuid4

from app.billing.credits import CreditService
from app.bootstrap import build_registry
from app.config import get_settings
from app.object_storage import build_object_storage
from app.platform.store import PlatformStore
from app.service import JobService
from app.storage import JobStore
from app.studio.executors import execute_module_job, execute_pipeline
from app.studio.store import StudioStore
from app.studio.tenant_store import TenantStudioStore


async def run_worker(poll_interval: float = 2.0) -> None:
    settings = get_settings()
    store = JobStore(settings.database_path)
    service = JobService(
        store,
        settings.work_root,
        build_registry(),
        settings.max_concurrency,
        database_path=settings.database_path,
        object_storage=build_object_storage(settings),
    )
    studio = StudioStore(settings.database_path, settings.work_root)
    platform = PlatformStore(settings.database_path)
    platform.seed(settings)
    credits = CreditService(settings.database_path)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:6]}"
    worker_state = {"status": "idle", "job_id": ""}

    async def beat() -> None:
        await asyncio.to_thread(
            store.heartbeat,
            worker_id,
            socket.gethostname(),
            os.getpid(),
            status=worker_state["status"],
            current_job_id=worker_state["job_id"],
        )

    async def heartbeat_loop() -> None:
        while not stop.is_set():
            try:
                await beat()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except TimeoutError:
                pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    heartbeat_task = asyncio.create_task(heartbeat_loop())
    try:
        while not stop.is_set():
            tenant_ids = [
                str(tenant["id"])
                for tenant in platform.list_tenants()
                if tenant.get("status") == "active"
            ] or ["demo"]
            handled = False
            for tenant_id in tenant_ids:
                workflow_job = await asyncio.to_thread(store.claim_next, tenant_id)
                if workflow_job is not None:
                    worker_state.update(status="running", job_id=workflow_job.id)
                    await beat()
                    await service.run_job(workflow_job)
                    saved = service.store.get(workflow_job.id, tenant_id)
                    if saved is not None:
                        if saved.status.value in {"failed", "canceled"}:
                            credits.refund_ref(
                                tenant_id,
                                "workflow_job",
                                workflow_job.id,
                            )
                        else:
                            credits.settle_ref(
                                tenant_id,
                                "workflow_job",
                                workflow_job.id,
                            )
                    handled = True
                    break

                module_job = await asyncio.to_thread(studio.claim_next_job, tenant_id)
                if module_job is not None:
                    worker_state.update(status="running", job_id=module_job["id"])
                    await beat()
                    tenant_studio = TenantStudioStore(studio, tenant_id)
                    await execute_module_job(tenant_studio, module_job, credits)
                    handled = True
                    break

                pipeline = await asyncio.to_thread(
                    studio.claim_next_pipeline,
                    tenant_id,
                )
                if pipeline is not None:
                    worker_state.update(status="running", job_id=pipeline["id"])
                    await beat()
                    tenant_studio = TenantStudioStore(studio, tenant_id)
                    await execute_pipeline(tenant_studio, pipeline, credits)
                    handled = True
                    break

            worker_state.update(status="idle", job_id="")
            await beat()
            if handled:
                continue

            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
            except TimeoutError:
                pass
    finally:
        stop.set()
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        try:
            await asyncio.to_thread(store.remove_worker, worker_id)
        except Exception:
            pass


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
