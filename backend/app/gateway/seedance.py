from __future__ import annotations

from typing import Any


class SeedanceVideo:
    """Shell adapter for ByteDance Seedance via Volcano Ark.

    The real flow is submit -> poll -> download. Fill in the two methods when
    ARK credentials and the endpoint id are available.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def submit(self, prompt: str, **options: Any) -> str:
        raise NotImplementedError(
            "Seedance adapter is a shell. Implement task submission next."
        )

    async def poll(self, task_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Seedance adapter is a shell. Implement task polling next."
        )
