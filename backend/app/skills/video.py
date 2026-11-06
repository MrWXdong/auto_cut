from __future__ import annotations

from typing import Any


class VideoSkill:
    name = "video.generate"

    async def run(self, ctx: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            "video skill is a shell. Wire it to the clip workflow next."
        )
