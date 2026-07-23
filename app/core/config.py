"""Environment-backed application settings with conservative local defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    request_body_limit_bytes: int = 1024 * 1024
    auto_migrate_database: bool = True
    reports_dir: Path = PROJECT_ROOT / "reports"
    pdf_timeout_seconds: float = 30.0
    pdf_max_size_bytes: int = 20 * 1024 * 1024
    persistent_capacity_bytes: int = 5 * 1024 * 1024 * 1024
    persistent_stop_fraction: float = 0.85

    def __post_init__(self) -> None:
        if self.request_body_limit_bytes <= 0:
            raise ValueError("request_body_limit_bytes 必须大于 0")
        if self.pdf_timeout_seconds <= 0 or self.pdf_max_size_bytes <= 0:
            raise ValueError("PDF 超时和大小限制必须大于 0")
        if self.persistent_capacity_bytes <= 0:
            raise ValueError("持久化容量必须大于 0")
        if not 0 < self.persistent_stop_fraction <= 1:
            raise ValueError("持久化停止阈值必须在 (0, 1] 内")

    @classmethod
    def from_environment(cls) -> Settings:
        configured_path = os.getenv("DESIGN_AGENT_DB_PATH")
        database_path = Path(configured_path) if configured_path else PROJECT_ROOT / "data" / "app.sqlite3"
        configured_reports = os.getenv("DESIGN_AGENT_REPORTS_DIR")
        reports_dir = Path(configured_reports) if configured_reports else PROJECT_ROOT / "reports"
        auto_migrate = os.getenv("DESIGN_AGENT_AUTO_MIGRATE", "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        return cls(
            database_path=database_path.resolve(),
            auto_migrate_database=auto_migrate,
            reports_dir=reports_dir.resolve(),
            pdf_timeout_seconds=float(os.getenv("DESIGN_AGENT_PDF_TIMEOUT_SECONDS", "30")),
            pdf_max_size_bytes=int(os.getenv("DESIGN_AGENT_PDF_MAX_SIZE_BYTES", str(20 * 1024 * 1024))),
            persistent_capacity_bytes=int(
                os.getenv(
                    "DESIGN_AGENT_PERSISTENT_CAPACITY_BYTES",
                    str(5 * 1024 * 1024 * 1024),
                )
            ),
            persistent_stop_fraction=float(os.getenv("DESIGN_AGENT_PERSISTENT_STOP_FRACTION", "0.85")),
        )
