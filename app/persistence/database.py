"""SQLite connection, migrations, readiness checks, and online backups."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5.0)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    with connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration_path.name in applied:
                continue
            connection.executescript(migration_path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)",
                (migration_path.name,),
            )


def database_is_ready(database_path: Path) -> bool:
    if not database_path.is_file():
        return False
    try:
        uri = database_path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=1.0)) as connection:
            connection.row_factory = sqlite3.Row
            tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"schema_migrations", "calculations", "report_artifacts"} <= tables:
                return False
            applied = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
            expected = {path.name for path in MIGRATIONS_DIR.glob("*.sql")}
            return applied == expected and connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except (OSError, sqlite3.Error):
        return False


def backup_database(database_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as source, closing(sqlite3.connect(backup_path)) as target:
        source.backup(target)
