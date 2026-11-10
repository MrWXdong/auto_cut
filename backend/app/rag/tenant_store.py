from __future__ import annotations

import inspect
from typing import Any

from app.rag.store import RagStore


class TenantRagStore:
    def __init__(self, store: RagStore, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "tenant_id", tenant_id)

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._store, name)
        if not callable(value):
            return value
        try:
            parameters = inspect.signature(value).parameters
        except (TypeError, ValueError):
            return value
        if "tenant_id" not in parameters:
            return value
        parameter_names = list(parameters)
        tenant_index = parameter_names.index("tenant_id")

        def bound(*args: Any, **kwargs: Any) -> Any:
            if len(args) <= tenant_index:
                kwargs.setdefault("tenant_id", self.tenant_id)
            return value(*args, **kwargs)

        return bound
