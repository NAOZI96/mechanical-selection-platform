from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_winch_calculator import make_input

from app.modules.registry import get_module
from app.persistence.database import (
    MIGRATIONS_DIR,
    _apply_migration_atomically,
    backup_database,
    connect,
    database_is_ready,
    database_is_writable,
    initialize_database,
)
from app.persistence.repository import CalculationRepository
from app.services.calculations import CalculationService


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "source.sqlite3"
        initialize_database(self.database_path)
        self.repository = CalculationRepository(self.database_path)
        self.service = CalculationService(self.repository, get_module)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_migrations_enable_required_sqlite_pragmas(self) -> None:
        with connect(self.database_path) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"schema_migrations", "calculations", "report_artifacts"} <= tables)
        self.assertTrue(database_is_ready(self.database_path))
        self.assertTrue(database_is_writable(self.database_path))

    def test_readiness_does_not_create_or_accept_an_unmigrated_database(self) -> None:
        missing = Path(self.temporary_directory.name) / "missing.sqlite3"
        self.assertFalse(database_is_ready(missing))
        self.assertFalse(missing.exists())

        incomplete = Path(self.temporary_directory.name) / "incomplete.sqlite3"
        sqlite3.connect(incomplete).close()
        self.assertFalse(database_is_ready(incomplete))
        self.assertFalse(database_is_writable(incomplete))

    def test_write_readiness_probe_rolls_back_without_ledger_pollution(self) -> None:
        self.assertTrue(database_is_writable(self.database_path))
        with connect(self.database_path) as connection:
            probe_count = connection.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = ?",
                ("__readiness_write_probe__",),
            ).fetchone()[0]
        self.assertEqual(probe_count, 0)

    def test_readiness_rejects_schema_drift_even_when_migration_ledger_is_complete(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DROP TRIGGER trg_report_artifacts_ready_insert")
        self.assertFalse(database_is_ready(self.database_path))

        initialize_database(self.database_path)
        self.assertFalse(
            database_is_ready(self.database_path),
            "迁移台账已记录时不得静默重建丢失的 schema 对象",
        )

    def test_readiness_rejects_same_name_trigger_with_wrong_semantics(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DROP TRIGGER trg_report_artifacts_ready_insert")
            connection.execute(
                """
                CREATE TRIGGER trg_report_artifacts_ready_insert
                BEFORE INSERT ON report_artifacts
                BEGIN
                    SELECT 1;
                END
                """
            )
        self.assertFalse(database_is_ready(self.database_path, verify_integrity=False))

    def test_readiness_rejects_constraint_changing_schema_objects(self) -> None:
        drift_scripts = {
            "literal_case_trigger": """
                DROP TRIGGER trg_report_artifacts_ready_insert;
                CREATE TRIGGER trg_report_artifacts_ready_insert
                BEFORE INSERT ON report_artifacts
                WHEN NEW.status = 'READY' AND (
                    NEW.relative_path IS NULL OR NEW.sha256 IS NULL OR
                    NEW.size_bytes IS NULL OR NEW.completed_at IS NULL
                )
                BEGIN
                    SELECT RAISE(ABORT, 'ready report artifact requires path, hash, size, and completed_at');
                END;
            """,
            "unexpected_trigger": """
                CREATE TRIGGER unexpected_calculation_block
                BEFORE INSERT ON calculations
                BEGIN
                    SELECT RAISE(ABORT, 'blocked by drift');
                END;
            """,
            "unexpected_unique_index": """
                CREATE UNIQUE INDEX unexpected_one_calculation_per_module
                ON calculations(module_id);
            """,
            "required_index_made_unique": """
                DROP INDEX idx_calculations_module_id;
                CREATE UNIQUE INDEX idx_calculations_module_id ON calculations(module_id);
            """,
        }
        for case_name, script in drift_scripts.items():
            with self.subTest(case=case_name):
                database_path = Path(self.temporary_directory.name) / f"{case_name}.sqlite3"
                initialize_database(database_path)
                with connect(database_path) as connection:
                    connection.executescript(script)
                self.assertFalse(database_is_ready(database_path, verify_integrity=False))

    def test_readiness_rejects_missing_migrated_column(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("ALTER TABLE calculations RENAME COLUMN release_status TO release_status_broken")
        self.assertFalse(database_is_ready(self.database_path, verify_integrity=False))

    def test_readiness_rejects_index_with_the_right_name_on_the_wrong_column(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DROP INDEX idx_calculations_module_id")
            connection.execute("CREATE INDEX idx_calculations_module_id ON calculations(created_at)")
        self.assertFalse(database_is_ready(self.database_path, verify_integrity=False))

    def test_failed_migration_rolls_back_schema_and_ledger_together(self) -> None:
        migration = Path(self.temporary_directory.name) / "999_atomic_probe.sql"
        migration.write_text(
            "ALTER TABLE calculations ADD COLUMN atomic_probe TEXT;\n"
            "INSERT INTO table_that_does_not_exist(value) VALUES (1);\n",
            encoding="utf-8",
        )
        with self.assertRaises(sqlite3.Error), connect(self.database_path) as connection:
            _apply_migration_atomically(connection, migration)
        with connect(self.database_path) as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(calculations)")}
            ledger = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
        self.assertNotIn("atomic_probe", columns)
        self.assertNotIn(migration.name, ledger)
        self.assertTrue(MIGRATIONS_DIR.is_dir())

    def test_failed_migration_ledger_insert_rolls_back_schema_change(self) -> None:
        migration = Path(self.temporary_directory.name) / "001_initial.sql"
        migration.write_text(
            "ALTER TABLE calculations ADD COLUMN ledger_failure_probe TEXT;\n",
            encoding="utf-8",
        )
        with self.assertRaises(sqlite3.IntegrityError), connect(self.database_path) as connection:
            _apply_migration_atomically(connection, migration)
        with connect(self.database_path) as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(calculations)")}
            ledger_count = connection.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = ?",
                (migration.name,),
            ).fetchone()[0]
        self.assertNotIn("ledger_failure_probe", columns)
        self.assertEqual(ledger_count, 1)

    def test_ready_report_artifact_requires_complete_metadata(self) -> None:
        created = self.service.create("winch_drum", make_input().model_dump(), "request-artifact")
        with self.assertRaises(sqlite3.IntegrityError), connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO report_artifacts (
                    id, calculation_id, format, status, template_version, created_at
                ) VALUES (?, ?, 'pdf', 'ready', ?, ?)
                """,
                (
                    "artifact-incomplete",
                    created["calculation_id"],
                    created["report_template_version"],
                    created["created_at"],
                ),
            )

    def test_online_backup_restores_complete_snapshot(self) -> None:
        created = self.service.create("winch_drum", make_input().model_dump(), "request-1")
        backup_path = Path(self.temporary_directory.name) / "backup.sqlite3"
        backup_database(self.database_path, backup_path)
        restored = CalculationRepository(backup_path).get(created["calculation_id"])
        self.assertEqual(restored, created)

    def test_failed_duplicate_insert_rolls_back(self) -> None:
        created = self.service.create("winch_drum", make_input().model_dump(), "request-2")
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.create(created, "duplicate", "request-3")
        with connect(self.database_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM calculations").fetchone()[0]
        self.assertEqual(count, 1)

    def test_saved_snapshot_read_does_not_depend_on_current_module_lookup(self) -> None:
        created = self.service.create("winch_drum", make_input().model_dump(), "request-4")

        def forbidden_lookup(_: str):
            raise AssertionError("读取旧快照时不得查找或重算当前模块")

        read_only_service = CalculationService(self.repository, forbidden_lookup)
        fetched = read_only_service.get(created["calculation_id"])
        self.assertEqual(fetched, created)


if __name__ == "__main__":
    unittest.main()
