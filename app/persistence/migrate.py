"""Controlled migration command for production deployment workflows."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings

from .database import backup_database, database_is_ready, initialize_database


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    arguments = parser.parse_args()
    settings = Settings.from_environment()
    database_path = settings.database_path

    if arguments.check:
        if not database_is_ready(database_path):
            raise SystemExit("数据库缺失、损坏或迁移版本不完整")
        print("DATABASE_MIGRATIONS=READY")
        return

    if database_path.is_file() and database_path.stat().st_size > 0:
        if arguments.backup_dir is None:
            raise SystemExit("已有数据库执行迁移前必须提供 --backup-dir")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = arguments.backup_dir.resolve() / f"app-before-migration-{timestamp}.sqlite3"
        backup_database(database_path, backup_path)
        print(f"DATABASE_BACKUP={backup_path}")
    initialize_database(database_path)
    if not database_is_ready(database_path):
        raise SystemExit("迁移后数据库就绪检查失败")
    print("DATABASE_MIGRATIONS=APPLIED")


if __name__ == "__main__":
    main()
