from __future__ import annotations

import re
from typing import Any

REFERENCE = re.compile(
    r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\}\}"
)
RESERVED_SCOPES = {"inputs", "vars", "env", "loop"}


class ReferenceError(KeyError):
    """Raised when a template reference cannot be resolved."""


def resolve(value: Any, scope: dict[str, Any]) -> Any:
    if isinstance(value, str):
        match = REFERENCE.fullmatch(value.strip())
        if match is not None:
            return lookup(match.group(1), scope)
        return REFERENCE.sub(
            lambda item: _stringify(lookup(item.group(1), scope)),
            value,
        )
    if isinstance(value, dict):
        return {key: resolve(item, scope) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, scope) for item in value]
    return value


def lookup(path: str, scope: dict[str, Any]) -> Any:
    parts = path.split(".")
    head = parts[0]
    if head in RESERVED_SCOPES:
        if head not in scope:
            raise ReferenceError(f"reference not found: {path}")
        current: Any = scope[head]
    else:
        nodes = scope.get("nodes") or {}
        if head not in nodes:
            raise ReferenceError(f"reference not found: {path}")
        current = nodes[head]

    for part in parts[1:]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ReferenceError(f"reference not found: {path}")
    return current


def build_scope(
    *,
    inputs: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
    node_outputs: dict[str, dict[str, Any]] | None = None,
    env: dict[str, Any] | None = None,
    loop: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "inputs": inputs or {},
        "vars": variables or {},
        "nodes": node_outputs or {},
        "env": env or {},
        "loop": loop or {},
    }


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
