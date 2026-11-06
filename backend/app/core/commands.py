from __future__ import annotations

import asyncio
from collections.abc import Sequence


class CommandError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int, stderr: str) -> None:
        self.command = list(command)
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"command failed with exit code {returncode}: {' '.join(self.command)}\n"
            f"{stderr[-2000:]}"
        )


async def run_command(args: Sequence[str], timeout: float = 600.0) -> str:
    """Run an external command without a shell and return stdout."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise CommandError(args, -1, f"timed out after {timeout} seconds") from None

    if process.returncode != 0:
        raise CommandError(
            args,
            process.returncode or -1,
            stderr.decode("utf-8", errors="replace"),
        )
    return stdout.decode("utf-8", errors="replace")
