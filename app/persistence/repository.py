"""Repository for versioned calculation snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .database import connect


class CalculationRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def create(self, snapshot: dict[str, Any], input_hash: str, request_id: str) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO calculations (
                    id, module_id, module_version, calculation_model_version,
                    report_template_version, status, release_status,
                    input_original_json, input_si_json, assumptions_json, results_json,
                    steps_json, warnings_json, disclaimer_json, snapshot_schema_version,
                    report_context_json, input_hash, created_at, request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["calculation_id"],
                    snapshot["module_id"],
                    snapshot["module_version"],
                    snapshot["calculation_model_version"],
                    snapshot["report_template_version"],
                    snapshot["status"],
                    snapshot["release_status"],
                    _json(snapshot["input_original"]),
                    _json(snapshot["input_si"]),
                    _json(snapshot["assumptions"]),
                    _json(snapshot["results"]),
                    _json(snapshot["steps"]),
                    _json(snapshot["warnings"]),
                    _json(snapshot["disclaimer"]),
                    snapshot["snapshot_schema_version"],
                    _json(snapshot["report_context"]),
                    input_hash,
                    snapshot["created_at"],
                    request_id,
                ),
            )

    def get(self, calculation_id: str) -> dict[str, Any] | None:
        with connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT * FROM calculations WHERE id = ?",
                (calculation_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "calculation_id": row["id"],
            "module_id": row["module_id"],
            "module_version": row["module_version"],
            "calculation_model_version": row["calculation_model_version"],
            "report_template_version": row["report_template_version"],
            "release_status": row["release_status"] or "legacy_unknown",
            "status": row["status"],
            "created_at": row["created_at"],
            "input_original": json.loads(row["input_original_json"]),
            "input_si": json.loads(row["input_si_json"]),
            "assumptions": json.loads(row["assumptions_json"]),
            "results": json.loads(row["results_json"]),
            "steps": json.loads(row["steps_json"]),
            "warnings": json.loads(row["warnings_json"]),
            "disclaimer": json.loads(row["disclaimer_json"]),
            "snapshot_schema_version": row["snapshot_schema_version"],
            "report_context": (None if row["report_context_json"] is None else json.loads(row["report_context_json"])),
            "links": _links(row["id"]),
        }

    def get_report_artifact(
        self,
        calculation_id: str,
        template_version: str,
    ) -> dict[str, Any] | None:
        with connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM report_artifacts
                WHERE calculation_id = ? AND format = 'pdf' AND template_version = ?
                """,
                (calculation_id, template_version),
            ).fetchone()
        return None if row is None else dict(row)

    def begin_report_artifact(
        self,
        *,
        artifact_id: str,
        calculation_id: str,
        template_version: str,
        created_at: str,
    ) -> str:
        with connect(self._database_path) as connection:
            existing = connection.execute(
                """
                SELECT id FROM report_artifacts
                WHERE calculation_id = ? AND format = 'pdf' AND template_version = ?
                """,
                (calculation_id, template_version),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO report_artifacts (
                        id, calculation_id, format, status, template_version, created_at
                    ) VALUES (?, ?, 'pdf', 'generating', ?, ?)
                    """,
                    (artifact_id, calculation_id, template_version, created_at),
                )
                return artifact_id
            persisted_id = str(existing["id"])
            connection.execute(
                """
                UPDATE report_artifacts
                SET status = 'generating', relative_path = NULL, sha256 = NULL,
                    size_bytes = NULL, completed_at = NULL, error_code = NULL
                WHERE id = ?
                """,
                (persisted_id,),
            )
            return persisted_id

    def mark_report_ready(
        self,
        *,
        artifact_id: str,
        relative_path: str,
        sha256: str,
        size_bytes: int,
        completed_at: str,
    ) -> None:
        with connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE report_artifacts
                SET status = 'ready', relative_path = ?, sha256 = ?,
                    size_bytes = ?, completed_at = ?, error_code = NULL
                WHERE id = ?
                """,
                (relative_path, sha256, size_bytes, completed_at, artifact_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("报告工件记录不存在")

    def mark_report_failed(self, *, artifact_id: str, error_code: str, completed_at: str) -> None:
        with connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE report_artifacts
                SET status = 'failed', relative_path = NULL, sha256 = NULL,
                    size_bytes = NULL, completed_at = ?, error_code = ?
                WHERE id = ?
                """,
                (completed_at, error_code, artifact_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("报告工件记录不存在")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _links(calculation_id: str) -> dict[str, str]:
    return {
        "self": f"/api/v1/calculations/{calculation_id}",
        "html_report": f"/calculations/{calculation_id}/report",
        "pdf": f"/api/v1/calculations/{calculation_id}/report.pdf",
    }
