"""PDF artifact state machine, cache validation, limits, and subprocess isolation."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import PROJECT_ROOT, Settings
from app.persistence.repository import CalculationRepository

from .models import ReportContext

PDF_FONT_PATH = PROJECT_ROOT / "app" / "assets" / "fonts" / "NotoSansSC-VF.ttf"


class ReportServiceError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds


class PdfReportService:
    """Generate at most one PDF at a time and preserve artifact integrity."""

    def __init__(self, repository: CalculationRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings
        self._semaphore = threading.BoundedSemaphore(value=1)
        self._reports_root = settings.reports_dir.resolve()
        self._temporary_root = self._reports_root / ".tmp"

    def validate_runtime(self) -> None:
        """Fail startup when the persisted report runtime is unavailable."""

        if not PDF_FONT_PATH.is_file():
            raise RuntimeError("PDF 中文字体缺失")
        try:
            self._temporary_root.mkdir(parents=True, exist_ok=True)
            probe_path = self._temporary_root / f".ready-{uuid4()}"
            probe_path.write_bytes(b"ready")
            probe_path.unlink()
        except OSError as exc:
            raise RuntimeError("报告目录不可写") from exc

    def is_ready(self) -> bool:
        return PDF_FONT_PATH.is_file() and self._reports_root.is_dir() and self._temporary_root.is_dir()

    def get_or_generate(self, snapshot: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        cached = self._validated_cached_artifact(snapshot)
        if cached is not None:
            return cached
        report_payload = snapshot.get("report_context")
        if not isinstance(report_payload, dict) or int(report_payload.get("schema_version", 0)) < 4:
            raise ReportServiceError(
                status_code=409,
                code="LEGACY_RELEASE_STATUS_MISSING",
                message="旧快照未记录计算时的工程发布状态；请查看 HTML 报告并重新计算后生成新版 PDF",
            )
        if not self._semaphore.acquire(blocking=False):
            raise ReportServiceError(
                status_code=429,
                code="PDF_BUSY",
                message="PDF 渲染器正忙，请稍后重试",
                retry_after_seconds=2,
            )
        try:
            cached = self._validated_cached_artifact(snapshot)
            if cached is not None:
                return cached
            return self._generate(snapshot)
        finally:
            self._semaphore.release()

    def _validated_cached_artifact(
        self,
        snapshot: dict[str, Any],
    ) -> tuple[Path, dict[str, Any]] | None:
        artifact = self._repository.get_report_artifact(
            snapshot["calculation_id"],
            snapshot["report_template_version"],
        )
        if artifact is None or artifact["status"] != "ready":
            return None
        path = self._safe_artifact_path(artifact.get("relative_path"))
        if (
            path is not None
            and path.is_file()
            and path.stat().st_size == artifact["size_bytes"]
            and _sha256_file(path) == artifact["sha256"]
        ):
            return path, artifact
        self._repository.mark_report_failed(
            artifact_id=str(artifact["id"]),
            error_code="PDF_CACHE_INTEGRITY_FAILED",
            completed_at=_utc_now(),
        )
        return None

    def _generate(self, snapshot: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        report_payload = snapshot.get("report_context")
        if report_payload is None:
            raise ReportServiceError(
                status_code=503,
                code="REPORT_CONTEXT_MISSING",
                message="该旧快照没有可验证的持久化报告上下文",
            )
        report_context = ReportContext.model_validate(report_payload)
        artifact_id: str | None = None
        final_path: Path | None = None
        context_path: Path | None = None
        output_path: Path | None = None
        moved_to_final = False
        error_code = "PDF_GENERATION_FAILED"
        try:
            self._check_capacity()
            self._temporary_root.mkdir(parents=True, exist_ok=True)
            artifact_id = self._repository.begin_report_artifact(
                artifact_id=str(uuid4()),
                calculation_id=snapshot["calculation_id"],
                template_version=snapshot["report_template_version"],
                created_at=_utc_now(),
            )
            relative_path = Path("artifacts") / f"{artifact_id}.pdf"
            final_path = (self._reports_root / relative_path).resolve()
            if not final_path.is_relative_to(self._reports_root):
                raise AssertionError("内部报告路径越界")
            context_path = self._temporary_root / f"{artifact_id}.json"
            output_path = self._temporary_root / f"{artifact_id}.pdf"
            context_path.write_text(
                json.dumps(
                    report_context.model_dump(mode="json"),
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            self._run_worker(context_path, output_path)
            if not output_path.is_file() or _file_prefix(output_path, 5) != b"%PDF-":
                error_code = "PDF_INVALID_OUTPUT"
                raise RuntimeError("PDF 渲染器未生成有效文件")
            size_bytes = output_path.stat().st_size
            if size_bytes <= 0 or size_bytes > self._settings.pdf_max_size_bytes:
                error_code = "PDF_SIZE_LIMIT"
                raise RuntimeError("PDF 文件超过大小限制")
            sha256 = _sha256_file(output_path)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(output_path, final_path)
            moved_to_final = True
            self._repository.mark_report_ready(
                artifact_id=artifact_id,
                relative_path=relative_path.as_posix(),
                sha256=sha256,
                size_bytes=size_bytes,
                completed_at=_utc_now(),
            )
            artifact = self._repository.get_report_artifact(
                snapshot["calculation_id"],
                snapshot["report_template_version"],
            )
            if artifact is None:
                raise RuntimeError("PDF 工件状态写入后无法读取")
            return final_path, artifact
        except subprocess.TimeoutExpired as exc:
            error_code = "PDF_TIMEOUT"
            self._repository.mark_report_failed(
                artifact_id=artifact_id,
                error_code=error_code,
                completed_at=_utc_now(),
            )
            raise ReportServiceError(
                status_code=503,
                code=error_code,
                message="PDF 生成超时，计算快照仍已保留",
                retry_after_seconds=5,
            ) from exc
        except ReportServiceError:
            raise
        except Exception as exc:
            if moved_to_final and final_path is not None:
                final_path.unlink(missing_ok=True)
            if artifact_id is not None:
                self._repository.mark_report_failed(
                    artifact_id=artifact_id,
                    error_code=error_code,
                    completed_at=_utc_now(),
                )
            raise ReportServiceError(
                status_code=503,
                code=error_code,
                message="PDF 生成失败，计算快照仍已保留",
            ) from exc
        finally:
            if context_path is not None:
                context_path.unlink(missing_ok=True)
            if output_path is not None:
                output_path.unlink(missing_ok=True)

    def _run_worker(self, context_path: Path, output_path: Path) -> None:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "app.reporting.pdf_worker",
                "--context",
                str(context_path),
                "--output",
                str(output_path),
                "--font",
                str(PDF_FONT_PATH),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            timeout=self._settings.pdf_timeout_seconds,
        )

    def _check_capacity(self) -> None:
        self._reports_root.mkdir(parents=True, exist_ok=True)
        used_bytes = sum(path.stat().st_size for path in self._reports_root.rglob("*") if path.is_file())
        stop_bytes = int(self._settings.persistent_capacity_bytes * self._settings.persistent_stop_fraction)
        if used_bytes + self._settings.pdf_max_size_bytes > stop_bytes:
            raise ReportServiceError(
                status_code=503,
                code="REPORT_CAPACITY_LIMIT",
                message="报告目录已达到持久化停止阈值，计算功能仍可继续使用",
            )

    def _safe_artifact_path(self, relative_path: Any) -> Path | None:
        if not isinstance(relative_path, str) or not relative_path:
            return None
        candidate = (self._reports_root / relative_path).resolve()
        return candidate if candidate.is_relative_to(self._reports_root) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_prefix(path: Path, size: int) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
