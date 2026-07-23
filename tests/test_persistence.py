from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_winch_calculator import make_input

from app.modules.registry import get_module
from app.persistence.database import (
    backup_database,
    connect,
    database_is_ready,
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

    def test_readiness_does_not_create_or_accept_an_unmigrated_database(self) -> None:
        missing = Path(self.temporary_directory.name) / "missing.sqlite3"
        self.assertFalse(database_is_ready(missing))
        self.assertFalse(missing.exists())

        incomplete = Path(self.temporary_directory.name) / "incomplete.sqlite3"
        sqlite3.connect(incomplete).close()
        self.assertFalse(database_is_ready(incomplete))

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
