from __future__ import annotations

import json
import shutil
from pathlib import Path


def config_path(database_path: Path) -> Path:
    return Path(database_path).parent / "storage.json"


def resolve_storage_root(default_root: Path, database_path: Path) -> Path:
    path = config_path(database_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        configured = str(payload.get("storage_root") or "").strip()
        if configured:
            root = Path(configured).expanduser()
            if root.is_absolute():
                root.mkdir(parents=True, exist_ok=True)
                return root.resolve()
    except (OSError, ValueError, TypeError):
        pass
    return Path(default_root).resolve()


def write_storage_root(database_path: Path, storage_root: Path) -> None:
    path = config_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"storage_root": str(Path(storage_root).resolve())}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_storage(old_root: Path, new_root: Path) -> None:
    old_root = Path(old_root).resolve()
    new_root = Path(new_root).resolve()
    if old_root == new_root or not old_root.exists():
        return
    if old_root.is_relative_to(new_root) or new_root.is_relative_to(old_root):
        raise ValueError("storage root cannot be nested inside the current directory")
    new_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        old_root,
        new_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "storage.json",
            "*.db",
            "*.db-wal",
            "*.db-shm",
            "*.log",
        ),
    )
