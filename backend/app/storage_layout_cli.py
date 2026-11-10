from __future__ import annotations

from app.config import get_settings
from app.storage_config import resolve_storage_root
from app.storage_layout import migrate_storage_layout


def main() -> None:
    settings = get_settings()
    root = resolve_storage_root(settings.work_root, settings.database_path)
    moved = migrate_storage_layout(root, settings.database_path)
    print(f"存储根目录：{root}")
    if not moved:
        print("没有需要迁移的任务目录。")
        return
    print(f"已迁移 {len(moved)} 个任务目录：")
    for item in moved:
        print(f"  {item['job_id']} -> {item['work_dir']}")


if __name__ == "__main__":
    main()
