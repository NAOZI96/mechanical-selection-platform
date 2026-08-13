from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.registry import get_module
from app.persistence.database import _SCHEMA_MIGRATIONS_SQL, MIGRATIONS_DIR, database_is_ready, initialize_database
from app.persistence.repository import CalculationRepository
from tests.test_api import valid_payload


class CalculationIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.database_path = root / "idempotency.sqlite3"
        self.settings = Settings(database_path=self.database_path, reports_dir=root / "reports")
        self.client_context = TestClient(create_app(self.settings))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def _post(
        self,
        *,
        key: str | None = None,
        payload: dict[str, object] | None = None,
        request_id: str | None = None,
        module_id: str = "winch_drum",
    ):
        headers: dict[str, str] = {}
        if key is not None:
            headers["Idempotency-Key"] = key
        if request_id is not None:
            headers["X-Request-ID"] = request_id
        return self.client.post(
            f"/api/v1/modules/{module_id}/calculations",
            json=payload or valid_payload(),
            headers=headers,
        )

    def _calculation_count(self) -> int:
        with closing(sqlite3.connect(self.database_path)) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM calculations").fetchone()[0])

    def test_sequential_retry_replays_committed_snapshot(self) -> None:
        first = self._post(key="lost-response.retry_1", request_id="attempt-1")
        replay = self._post(key="lost-response.retry_1", request_id="attempt-2")

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(first.headers["Idempotency-Replayed"], "false")
        self.assertEqual(replay.headers["Idempotency-Replayed"], "true")
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(self._calculation_count(), 1)
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                "SELECT request_id, idempotency_key, request_fingerprint FROM calculations"
            ).fetchone()
        self.assertEqual(row[0], "attempt-1")
        self.assertEqual(row[1], "lost-response.retry_1")
        self.assertEqual(len(row[2]), 64)

    def test_migration_preserves_existing_rows_with_null_idempotency_metadata(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy-005.sqlite3"
        with closing(sqlite3.connect(legacy_path)) as connection:
            connection.execute(_SCHEMA_MIGRATIONS_SQL)
            for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if migration_path.name >= "006_calculation_idempotency.sql":
                    continue
                connection.executescript(migration_path.read_text(encoding="utf-8"))
                connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration_path.name,))
            connection.execute(
                """
                INSERT INTO calculations (
                    id, module_id, module_version, calculation_model_version,
                    report_template_version, status, release_status,
                    input_original_json, input_si_json, assumptions_json, results_json,
                    steps_json, warnings_json, disclaimer_json, snapshot_schema_version,
                    report_context_json, input_hash, created_at, request_id
                ) VALUES (
                    'legacy-row', 'winch_drum', '1.2.1', 'winch_drum.calc.1.2.1',
                    'winch_drum.report.1.2.1', 'completed', 'engineering_review',
                    '{}', '{}', '[]', '{}', '[]', '[]', '"legacy"', 4,
                    NULL, 'legacy-hash', '2026-08-13T00:00:00Z', 'legacy-request'
                )
                """
            )
            connection.commit()

        initialize_database(legacy_path)

        with closing(sqlite3.connect(legacy_path)) as connection:
            row = connection.execute("SELECT id, idempotency_key, request_fingerprint FROM calculations").fetchone()
            index_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'idx_calculations_module_idempotency_key'"
            ).fetchone()[0]
        self.assertEqual(row, ("legacy-row", None, None))
        self.assertIn("WHERE idempotency_key IS NOT NULL", index_sql)
        self.assertTrue(database_is_ready(legacy_path))

    def test_same_key_with_different_normalized_request_returns_conflict(self) -> None:
        first = self._post(key="conflict-key")
        changed = valid_payload()
        changed_input = changed["input"]
        self.assertIsInstance(changed_input, dict)
        changed_input["rated_line_pull_kn"] = 101
        conflict = self._post(key="conflict-key", payload=changed)

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(conflict.json()["error"]["code"], "IDEMPOTENCY_KEY_REUSED")
        self.assertEqual(self._calculation_count(), 1)

    def test_requests_without_key_remain_intentionally_repeatable(self) -> None:
        first = self._post()
        second = self._post()

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.headers["Idempotency-Replayed"], "false")
        self.assertEqual(second.headers["Idempotency-Replayed"], "false")
        self.assertNotEqual(first.json()["calculation_id"], second.json()["calculation_id"])
        self.assertEqual(self._calculation_count(), 2)

    def test_idempotency_key_is_scoped_by_module(self) -> None:
        shared_key = "same-key.different-module"
        winch = self._post(key=shared_key)
        transmission_payload = {"input": dict(get_module("transmission_check").example_input)}
        transmission = self._post(
            key=shared_key,
            payload=transmission_payload,
            module_id="transmission_check",
        )
        transmission_replay = self._post(
            key=shared_key,
            payload=transmission_payload,
            module_id="transmission_check",
        )

        self.assertEqual(winch.status_code, 201, winch.text)
        self.assertEqual(transmission.status_code, 201, transmission.text)
        self.assertEqual(transmission_replay.status_code, 201, transmission_replay.text)
        self.assertNotEqual(winch.json()["calculation_id"], transmission.json()["calculation_id"])
        self.assertEqual(transmission.headers["Idempotency-Replayed"], "false")
        self.assertEqual(transmission_replay.headers["Idempotency-Replayed"], "true")
        self.assertEqual(self._calculation_count(), 2)

    def test_committed_replay_bypasses_capacity_write_gate(self) -> None:
        first = self._post(key="capacity-replay")
        self.assertEqual(first.status_code, 201, first.text)

        with patch.object(Settings, "allows_calculation_write", return_value=False):
            replay = self._post(key="capacity-replay")
            new_request = self._post(key="capacity-new")

        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.headers["Idempotency-Replayed"], "true")
        self.assertEqual(replay.json()["calculation_id"], first.json()["calculation_id"])
        self.assertEqual(new_request.status_code, 503, new_request.text)
        self.assertEqual(new_request.json()["error"]["code"], "PERSISTENT_CAPACITY_LIMIT")
        self.assertEqual(self._calculation_count(), 1)

    def test_concurrent_same_key_inserts_exactly_one_snapshot(self) -> None:
        worker_count = 6
        insert_barrier = threading.Barrier(worker_count)
        original_create = CalculationRepository.create

        def synchronized_create(repository, *args, **kwargs):
            insert_barrier.wait(timeout=10)
            return original_create(repository, *args, **kwargs)

        with (
            patch.object(Settings, "allows_calculation_write", return_value=True),
            patch.object(CalculationRepository, "create", new=synchronized_create),
        ):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                responses = list(
                    executor.map(
                        lambda index: self._post(
                            key="concurrent-key",
                            request_id=f"concurrent-attempt-{index}",
                        ),
                        range(worker_count),
                    )
                )

        self.assertTrue(all(response.status_code == 201 for response in responses), [r.text for r in responses])
        self.assertEqual(
            {response.json()["calculation_id"] for response in responses}, {responses[0].json()["calculation_id"]}
        )
        replay_headers = [response.headers["Idempotency-Replayed"] for response in responses]
        self.assertEqual(replay_headers.count("false"), 1)
        self.assertEqual(replay_headers.count("true"), worker_count - 1)
        self.assertEqual(self._calculation_count(), 1)

    def test_header_validation_rejects_non_url_safe_or_out_of_range_keys(self) -> None:
        invalid_keys = ("", "contains space", "contains/slash", "contains%percent", "a" * 129)
        for key in invalid_keys:
            with self.subTest(key=key):
                response = self.client.post(
                    "/api/v1/modules/winch_drum/calculations",
                    json=valid_payload(),
                    headers={"Idempotency-Key": key},
                )
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self._calculation_count(), 0)

    def test_database_checks_reject_invalid_or_unpaired_idempotency_metadata(self) -> None:
        created = self._post()
        self.assertEqual(created.status_code, 201, created.text)
        calculation_id = created.json()["calculation_id"]
        invalid_pairs = (
            ("contains space", "a" * 64),
            ("valid-key", None),
            ("valid-key", "g" * 64),
            (None, "a" * 64),
        )
        for key, fingerprint in invalid_pairs:
            with self.subTest(key=key, fingerprint=fingerprint):
                with (
                    self.assertRaises(sqlite3.IntegrityError),
                    closing(sqlite3.connect(self.database_path)) as connection,
                ):
                    connection.execute(
                        "UPDATE calculations SET idempotency_key = ?, request_fingerprint = ? WHERE id = ?",
                        (key, fingerprint, calculation_id),
                    )
        with closing(sqlite3.connect(self.database_path)) as connection:
            metadata = connection.execute(
                "SELECT idempotency_key, request_fingerprint FROM calculations WHERE id = ?",
                (calculation_id,),
            ).fetchone()
        self.assertEqual(metadata, (None, None))

    def test_unknown_envelope_field_is_rejected(self) -> None:
        payload = valid_payload()
        payload["unexpected_envelope_field"] = True
        response = self._post(payload=payload)

        self.assertEqual(response.status_code, 422, response.text)
        details = response.json()["error"]["details"]
        self.assertTrue(any(detail["field"] == "unexpected_envelope_field" for detail in details))
        self.assertEqual(self._calculation_count(), 0)

    def test_success_log_contains_audit_fields_without_input(self) -> None:
        payload = valid_payload()
        payload_input = payload["input"]
        self.assertIsInstance(payload_input, dict)
        payload_input["motor_type"] = "SECRET-INPUT-MUST-NOT-BE-LOGGED"

        with self.assertLogs("app.main", level="INFO") as captured:
            created = self._post(
                key="logged-key",
                payload=payload,
                request_id="logged-request-id",
            )
            replay = self._post(
                key="logged-key",
                payload=payload,
                request_id="logged-retry-id",
            )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(replay.status_code, 201, replay.text)
        messages = "\n".join(captured.output)
        for field in (
            "request_id=logged-request-id",
            "request_id=logged-retry-id",
            "module_id=winch_drum",
            "model_version=winch_drum.calc.1.2.1",
            "duration_ms=",
            "status=completed_with_warnings",
            "warning_count=",
            "idempotency_replayed=false",
            "idempotency_replayed=true",
        ):
            self.assertIn(field, messages)
        self.assertNotIn("SECRET-INPUT-MUST-NOT-BE-LOGGED", messages)


if __name__ == "__main__":
    unittest.main()
