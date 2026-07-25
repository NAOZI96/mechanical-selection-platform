"""Snapshot-only report mapping for the synchronous-belt module."""

from __future__ import annotations

from typing import Any

from app.modules.engineering_common import build_engineering_report_context
from app.reporting.models import ReportContext

from .constants import (
    ASSUMPTION_LABELS,
    INPUT_LABELS,
    MODULE_NAME,
    RESULT_LABELS,
    UNCHECKED_LABELS,
)


def build_report_context(snapshot: dict[str, Any]) -> ReportContext:
    return build_engineering_report_context(
        snapshot,
        module_name=MODULE_NAME,
        input_labels=INPUT_LABELS,
        result_labels=RESULT_LABELS,
        unchecked_labels=UNCHECKED_LABELS,
        assumption_labels=ASSUMPTION_LABELS,
    )


__all__ = ["build_report_context"]
