from __future__ import annotations

from typing import Any

from app.core.workflow.context import RunContext
from app.core.workflow.node import Node


def format_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class BuildSubtitleNode(Node):
    type = "subtitle.build"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        segments = inputs["params"].get("segments") or inputs["data"].get("segments") or []
        if not segments:
            raise ValueError("no transcript segments to build subtitles from")

        blocks: list[str] = []
        for segment in segments:
            text = str(segment.get("text") or "").strip()
            if not text:
                continue
            blocks.append(
                f"{len(blocks) + 1}\n"
                f"{format_timestamp(float(segment['start']))} --> "
                f"{format_timestamp(float(segment['end']))}\n"
                f"{text}\n"
            )

        output = ctx.work_dir / "subtitles" / "subtitles.srt"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(blocks), encoding="utf-8")
        return {"path": str(output), "count": len(blocks)}
