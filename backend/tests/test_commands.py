from __future__ import annotations

import asyncio
import sys

import pytest

from app.core.commands import run_command


@pytest.mark.asyncio
async def test_run_command_falls_back_when_subprocess_loop_is_unavailable(
    monkeypatch,
) -> None:
    async def unavailable(*_args, **_kwargs):
        raise NotImplementedError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", unavailable)
    output = await run_command(
        [sys.executable, "-c", "print('fallback-ok')"],
        timeout=10,
    )
    assert output.strip() == "fallback-ok"
