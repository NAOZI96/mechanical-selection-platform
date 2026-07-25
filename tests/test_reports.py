from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.persistence.database import connect
from tests.test_api import valid_payload


class ReportFailureAndLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.database_path = root / "reports.sqlite3"
        self.settings = Settings(
            database_path=self.database_path,
            reports_dir=root / "reports",
        )
        self.app = create_app(self.settings)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def _create(self) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/modules/winch_drum/calculations",
            json=valid_payload(),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_pdf_busy_returns_429_and_retry_after(self) -> None:
        created = self._create()
        report_service = self.app.state.report_service
        self.assertTrue(report_service._semaphore.acquire(blocking=False))
        try:
            response = self.client.get(created["links"]["pdf"])
        finally:
            report_service._semaphore.release()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "PDF_BUSY")
        self.assertEqual(response.headers["retry-after"], "2")

    def test_pdf_timeout_is_isolated_and_records_failed_artifact(self) -> None:
        created = self._create()
        with patch.object(
            self.app.state.report_service,
            "_run_worker",
            side_effect=subprocess.TimeoutExpired(cmd="pdf-worker", timeout=0.01),
        ):
            response = self.client.get(created["links"]["pdf"])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "PDF_TIMEOUT")
        self.assertEqual(
            self.client.get(created["links"]["self"]).status_code,
            200,
        )
        with connect(self.database_path) as connection:
            artifact = connection.execute("SELECT status, error_code FROM report_artifacts").fetchone()
        self.assertEqual(tuple(artifact), ("failed", "PDF_TIMEOUT"))
        self.assertEqual(list((self.settings.reports_dir / ".tmp").glob("*")), [])

    def test_capacity_limit_rejects_pdf_without_losing_calculation(self) -> None:
        root = Path(self.temporary_directory.name) / "limited"
        settings = Settings(
            database_path=root / "limited.sqlite3",
            reports_dir=root / "reports",
            pdf_max_size_bytes=100,
            persistent_capacity_bytes=100,
            persistent_stop_fraction=0.85,
        )
        with TestClient(create_app(settings)) as client:
            created = client.post(
                "/api/v1/modules/winch_drum/calculations",
                json=valid_payload(),
            ).json()
            response = client.get(created["links"]["pdf"])
            snapshot_response = client.get(created["links"]["self"])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "REPORT_CAPACITY_LIMIT")
        self.assertEqual(snapshot_response.status_code, 200)
        with closing(sqlite3.connect(settings.database_path)) as connection:
            artifact_count = connection.execute("SELECT COUNT(*) FROM report_artifacts").fetchone()[0]
        self.assertEqual(artifact_count, 0)

    def test_legacy_snapshot_is_labeled_and_uncached_pdf_requires_recalculation(self) -> None:
        created = self._create()
        legacy_context = dict(created["report_context"])
        legacy_context["schema_version"] = 3
        legacy_context.pop("release_status", None)
        legacy_context.pop("release_status_label", None)
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE calculations
                SET release_status = NULL, report_context_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps(legacy_context, ensure_ascii=False, separators=(",", ":")),
                    created["calculation_id"],
                ),
            )

        snapshot = self.client.get(created["links"]["self"])
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["release_status"], "legacy_unknown")

        html_report = self.client.get(created["links"]["html_report"])
        self.assertEqual(html_report.status_code, 200)
        self.assertIn("未记录（按内部测试边界处理）（legacy_unknown）", html_report.text)

        pdf = self.client.get(created["links"]["pdf"])
        self.assertEqual(pdf.status_code, 409)
        self.assertEqual(pdf.json()["error"]["code"], "LEGACY_RELEASE_STATUS_MISSING")
        self.assertIn("重新计算", pdf.json()["error"]["message"])
        with connect(self.database_path) as connection:
            artifact_count = connection.execute("SELECT COUNT(*) FROM report_artifacts").fetchone()[0]
        self.assertEqual(artifact_count, 0)


if __name__ == "__main__":
    unittest.main()
