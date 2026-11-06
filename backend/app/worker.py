from __future__ import annotations

import asyncio
import signal

from app.bootstrap import build_registry
from app.config import get_settings
from app.service import JobService
from app.storage import JobStore


async def run_worker(poll_interval: float = 2.0) -> None:
    settings = get_settings()
    store = JobStore(settings.database_path)
    service = JobService(
        store,
        settings.work_root,
        build_registry(),
        settings.max_concurrency,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    while not stop.is_set():
        job = await asyncio.to_thread(store.claim_next)
        if job is None:
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
            except asyncio.TimeoutError:
                pass
            continue
        await service.run_job(job)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
