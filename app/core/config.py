"""Environment-backed application settings with conservative local defaults."""

from __future__ import annotations

import os
import shutil
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PERSISTENT_USAGE_CACHE_SECONDS = 5.0


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
    persistent_calculation_stop_fraction: float = 0.95
    persistent_min_free_bytes: int = 512 * 1024 * 1024
    public_base_url: str | None = None
    _capacity_cache: dict[str, float | int] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )
    _capacity_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.request_body_limit_bytes <= 0:
            raise ValueError("request_body_limit_bytes 必须大于 0")
        if self.pdf_timeout_seconds <= 0 or self.pdf_max_size_bytes <= 0:
            raise ValueError("PDF 超时和大小限制必须大于 0")
        if self.persistent_capacity_bytes <= 0:
            raise ValueError("持久化容量必须大于 0")
        if not 0 < self.persistent_stop_fraction <= 1:
            raise ValueError("持久化停止阈值必须在 (0, 1] 内")
        if not self.persistent_stop_fraction < self.persistent_calculation_stop_fraction <= 1:
            raise ValueError("计算停止阈值必须大于 PDF 停止阈值且不超过 1")
        if self.persistent_min_free_bytes < 0:
            raise ValueError("持久化最小剩余空间不得小于 0")
        if self.public_base_url is not None:
            parsed = urlsplit(self.public_base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("public_base_url 必须是无路径、查询参数和片段的 HTTP(S) 站点根地址")

    @classmethod
    def from_environment(cls) -> Settings:
        configured_path = os.getenv("DESIGN_AGENT_DB_PATH")
        database_path = Path(configured_path) if configured_path else PROJECT_ROOT / "data" / "app.sqlite3"
        configured_reports = os.getenv("DESIGN_AGENT_REPORTS_DIR")
        reports_dir = Path(configured_reports) if configured_reports else PROJECT_ROOT / "reports"
        configured_public_url = os.getenv("DESIGN_AGENT_PUBLIC_BASE_URL", "").strip().rstrip("/")
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
            persistent_calculation_stop_fraction=float(
                os.getenv("DESIGN_AGENT_PERSISTENT_CALCULATION_STOP_FRACTION", "0.95")
            ),
            persistent_min_free_bytes=int(os.getenv("DESIGN_AGENT_PERSISTENT_MIN_FREE_BYTES", str(512 * 1024 * 1024))),
            public_base_url=configured_public_url or None,
        )

    def persistent_used_bytes(self, *, refresh: bool = False) -> int:
        """Return unique bytes currently owned by the database and report roots."""

        now = monotonic()
        with self._capacity_lock:
            checked_at = self._capacity_cache.get("checked_at")
            cached_bytes = self._capacity_cache.get("used_bytes")
            if (
                not refresh
                and isinstance(checked_at, float)
                and isinstance(cached_bytes, int)
                and now - checked_at <= _PERSISTENT_USAGE_CACHE_SECONDS
            ):
                return cached_bytes
            try:
                files: set[Path] = set()
                for suffix in ("", "-wal", "-shm"):
                    candidate = Path(f"{self.database_path}{suffix}")
                    files.add(candidate.resolve())
                if self.reports_dir.is_dir():
                    files.update(path.resolve() for path in self.reports_dir.rglob("*"))
                used_bytes = sum(_regular_file_size(path) for path in files)
            except OSError:
                used_bytes = self.persistent_capacity_bytes
            self._capacity_cache.update(checked_at=now, used_bytes=used_bytes)
            return used_bytes

    def persistent_filesystems_have_room(self, reserve_bytes: int = 0) -> bool:
        roots = {self.database_path.parent.resolve(), self.reports_dir.resolve()}
        try:
            return all(
                shutil.disk_usage(_nearest_existing_path(root)).free >= self.persistent_min_free_bytes + reserve_bytes
                for root in roots
            )
        except OSError:
            return False

    def allows_pdf_write(self) -> bool:
        stop_bytes = int(self.persistent_capacity_bytes * self.persistent_stop_fraction)
        return self.persistent_used_bytes(
            refresh=True
        ) + self.pdf_max_size_bytes <= stop_bytes and self.persistent_filesystems_have_room(self.pdf_max_size_bytes)

    def allows_calculation_write(self) -> bool:
        stop_bytes = int(self.persistent_capacity_bytes * self.persistent_calculation_stop_fraction)
        return self.persistent_used_bytes() < stop_bytes and self.persistent_filesystems_have_room()


def _nearest_existing_path(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _regular_file_size(path: Path) -> int:
    """Return a file's size while tolerating concurrent temporary-file cleanup."""

    try:
        file_stat = path.stat()
    except FileNotFoundError:
        return 0
    return file_stat.st_size if stat.S_ISREG(file_stat.st_mode) else 0
