"""SQLite connection, migrations, readiness checks, and online backups."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from functools import lru_cache
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
_SCHEMA_MIGRATIONS_SQL = (
    "CREATE TABLE IF NOT EXISTS schema_migrations "
    "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
)


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
        connection.execute(_SCHEMA_MIGRATIONS_SQL)
        applied = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration_path.name in applied:
                continue
            _apply_migration_atomically(connection, migration_path)


def _apply_migration_atomically(connection: sqlite3.Connection, migration_path: Path) -> None:
    """Apply one migration and its ledger row in the same SQLite transaction."""

    script = migration_path.read_text(encoding="utf-8")
    version = migration_path.name.replace("'", "''")
    try:
        connection.executescript(
            f"BEGIN IMMEDIATE;\n{script}\nINSERT INTO schema_migrations(version) VALUES ('{version}');\nCOMMIT;"
        )
    except sqlite3.Error:
        if connection.in_transaction:
            connection.rollback()
        raise


def database_is_ready(database_path: Path, *, verify_integrity: bool = True) -> bool:
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
            if applied != expected:
                return False
            if not _database_schema_matches_migrations(connection):
                return False
            if not verify_integrity:
                return connection.execute("SELECT 1").fetchone()[0] == 1
            return connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except (OSError, sqlite3.Error):
        return False


def database_is_writable(database_path: Path) -> bool:
    """Perform a rolled-back write probe against the main SQLite database."""

    if not database_path.is_file():
        return False
    try:
        with closing(sqlite3.connect(database_path, timeout=1.0)) as connection:
            connection.execute("PRAGMA busy_timeout = 1000")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO schema_migrations(version) VALUES ('__readiness_write_probe__')")
            connection.rollback()
        return True
    except (OSError, sqlite3.Error):
        return False


def _database_schema_matches_migrations(connection: sqlite3.Connection) -> bool:
    return _schema_signature(connection) == _expected_schema_signature()


@lru_cache(maxsize=1)
def _expected_schema_signature() -> tuple[tuple[str, str, str, str], ...]:
    """Build the authoritative schema from the bundled migration files once."""

    with closing(sqlite3.connect(":memory:")) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(_SCHEMA_MIGRATIONS_SQL)
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            connection.executescript(migration_path.read_text(encoding="utf-8"))
        return _schema_signature(connection)


def _schema_signature(connection: sqlite3.Connection) -> tuple[tuple[str, str, str, str], ...]:
    rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE type IN ('table', 'index', 'trigger')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    )
    return tuple((row["type"], row["name"], row["tbl_name"], _normalize_schema_sql(row["sql"] or "")) for row in rows)


def _normalize_schema_sql(sql: str) -> str:
    """Normalize formatting while preserving case-sensitive SQL string literals."""

    return " ".join(sql.split())


def backup_database(database_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as source, closing(sqlite3.connect(backup_path)) as target:
        source.backup(target)
