from __future__ import annotations

from typing import Any

import httpx

FALLBACK_ERROR_CODES = {
    "ModelNotOpen",
    "InvalidEndpointOrModel.NotFound",
}


class DoubaoImageError(ValueError):
    def __init__(self, message: str, *, provider_code: str = "") -> None:
        super().__init__(message)
        self.provider_code = provider_code


def _doubao_error(response: httpx.Response) -> tuple[str, str]:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        error = {}
    code = str(error.get("code") or "")
    message = str(error.get("message") or response.text or "").strip()
    return code, message[:500]


def _doubao_message(code: str, message: str, model: str, status_code: int) -> str:
    if code == "ModelNotOpen":
        return (
            f"豆包模型 {model} 尚未开通。请登录火山方舟控制台，在模型广场开通该模型；"
            "或创建推理接入点，把 ep-... 接入点 ID 填入模型配置。"
        )
    if code == "InvalidEndpointOrModel.NotFound":
        return (
            f"豆包模型或接入点 {model} 不存在或无权限。请检查模型 ID，"
            "或改用方舟控制台创建的 ep-... 推理接入点。"
        )
    if code in {"AuthenticationError", "InvalidApiKey", "InvalidAuthentication"}:
        return "豆包 API Key 无效，请重新填写 AUTOCUT_DOUBAO_API_KEY。"
    detail = f"：{message}" if message else ""
    return f"豆包生图失败（HTTP {status_code}，{code or 'unknown'}）{detail}"


class ZhipuImage:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/images/generations",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "size": size,
                },
            )
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data") or []
        if not data or not data[0].get("url"):
            raise ValueError("image provider returned no image url")
        return {
            "url": data[0]["url"],
            "id": payload.get("id") or "",
            "model": self.model,
        }


class DoubaoImage:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        fallback_models: list[str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback_models = [
            item for item in (fallback_models or []) if item and item != model
        ]

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        watermark: bool = False,
    ) -> dict[str, Any]:
        candidates = [self.model, *self.fallback_models]
        errors: list[str] = []
        for index, model in enumerate(candidates):
            try:
                result = await self._generate_once(
                    prompt=prompt,
                    size=size,
                    watermark=watermark,
                    model=model,
                )
            except DoubaoImageError as exc:
                errors.append(str(exc))
                if (
                    index == len(candidates) - 1
                    or exc.provider_code not in FALLBACK_ERROR_CODES
                ):
                    raise ValueError("；".join(errors)) from exc
                continue
            self.model = model
            result["fallback_used"] = index > 0
            return result
        raise ValueError("；".join(errors) or "豆包生图失败")

    async def _generate_once(
        self,
        *,
        prompt: str,
        size: str,
        watermark: bool,
        model: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=240.0) as client:
            response = await client.post(
                f"{self.base_url}/images/generations",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "response_format": "url",
                    "watermark": watermark,
                },
            )
            if response.status_code >= 400:
                code, message = _doubao_error(response)
                raise DoubaoImageError(
                    _doubao_message(code, message, model, response.status_code),
                    provider_code=code,
                )
            payload = response.json()
        data = payload.get("data") or []
        if not data or not data[0].get("url"):
            raise ValueError("Doubao image provider returned no image url")
        return {
            "url": data[0]["url"],
            "id": payload.get("id") or "",
            "model": model,
            "watermark": watermark,
        }
