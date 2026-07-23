"""Repeatable local resource smoke test for the Phase 3 release candidate."""

from __future__ import annotations

import argparse
import gc
import json
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean
from typing import Any

import psutil
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.test_api import valid_payload


class MemoryMonitor:
    def __init__(self) -> None:
        self._process = psutil.Process()
        self._stop = threading.Event()
        self.peak_rss_bytes = 0
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def __enter__(self) -> MemoryMonitor:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _sample(self) -> None:
        while not self._stop.wait(0.025):
            rss = self._process.memory_info().rss
            for child in self._process.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            self.peak_rss_bytes = max(self.peak_rss_bytes, rss)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calculations", type=int, default=1000)
    parser.add_argument("--pdfs", type=int, default=20)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.calculations < 1 or arguments.pdfs < 5:
        raise SystemExit("calculations 必须 >=1，pdfs 必须 >=5")

    process = psutil.Process()
    initial_rss = process.memory_info().rss
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        settings = Settings(
            database_path=root / "benchmark.sqlite3",
            reports_dir=root / "reports",
        )
        app = create_app(settings)
        calculation_latencies: list[float] = []
        pdf_latencies: list[float] = []
        with MemoryMonitor() as monitor, TestClient(app) as client:
            for index in range(arguments.calculations):
                payload = valid_payload()
                payload["input"]["target_rope_capacity_m"] = 300 + (index % 10)  # type: ignore[index]
                started = time.perf_counter()
                response = client.post(
                    "/api/v1/modules/winch_drum/calculations",
                    json=payload,
                )
                calculation_latencies.append(time.perf_counter() - started)
                if response.status_code != 201:
                    raise RuntimeError(response.text)

            pdf_links: list[str] = []
            for index in range(arguments.pdfs):
                payload = valid_payload()
                payload["input"]["target_rope_capacity_m"] = 320 + index  # type: ignore[index]
                created = client.post(
                    "/api/v1/modules/winch_drum/calculations",
                    json=payload,
                ).json()
                started = time.perf_counter()
                response = client.get(created["links"]["pdf"])
                pdf_latencies.append(time.perf_counter() - started)
                if response.status_code != 200 or not response.content.startswith(b"%PDF-"):
                    raise RuntimeError(response.text)
                pdf_links.append(str(created["links"]["pdf"]))

            concurrent_links: list[str] = []
            for index in range(5):
                payload = valid_payload()
                payload["input"]["target_rope_capacity_m"] = 400 + index  # type: ignore[index]
                created = client.post(
                    "/api/v1/modules/winch_drum/calculations",
                    json=payload,
                ).json()
                concurrent_links.append(str(created["links"]["pdf"]))
            with ThreadPoolExecutor(max_workers=5) as executor:
                concurrent_statuses = list(
                    executor.map(
                        lambda link: client.get(link).status_code,
                        concurrent_links,
                    )
                )
        gc.collect()
        final_rss = process.memory_info().rss
        result: dict[str, Any] = {
            "calculations": arguments.calculations,
            "calculation_error_count": 0,
            "calculation_p95_ms": round(_percentile(calculation_latencies, 0.95) * 1000, 3),
            "calculation_mean_ms": round(mean(calculation_latencies) * 1000, 3),
            "pdfs": arguments.pdfs,
            "pdf_error_count": 0,
            "pdf_p95_ms": round(_percentile(pdf_latencies, 0.95) * 1000, 3),
            "pdf_mean_ms": round(mean(pdf_latencies) * 1000, 3),
            "concurrent_pdf_statuses": sorted(concurrent_statuses),
            "concurrent_render_successes": concurrent_statuses.count(200),
            "concurrent_busy_responses": concurrent_statuses.count(429),
            "initial_rss_bytes": initial_rss,
            "peak_parent_plus_children_rss_bytes": monitor.peak_rss_bytes,
            "final_rss_bytes": final_rss,
            "rss_growth_bytes": final_rss - initial_rss,
            "temporary_pdf_files_remaining": len(list((settings.reports_dir / ".tmp").glob("*"))),
        }
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(serialized)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized + "\n", encoding="utf-8")
    if result["calculation_p95_ms"] >= 500:
        raise SystemExit("计算 p95 超过 500 ms")
    if result["pdf_p95_ms"] >= 10_000:
        raise SystemExit("PDF p95 超过 10 s")
    if result["peak_parent_plus_children_rss_bytes"] >= 512 * 1024 * 1024:
        raise SystemExit("峰值 RSS 超过 512 MiB")
    if result["concurrent_render_successes"] != 1 or result["concurrent_busy_responses"] != 4:
        raise SystemExit("PDF 并发门禁未严格限制为 1")
    if result["temporary_pdf_files_remaining"] != 0:
        raise SystemExit("PDF 临时文件未清理")


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile + 0.999999) - 1))
    return ordered[index]


if __name__ == "__main__":
    main()
