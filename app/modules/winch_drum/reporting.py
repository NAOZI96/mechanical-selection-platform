"""Report mapping for saved winch-drum snapshots."""

from __future__ import annotations

from typing import Any

from app.reporting.context import build_report_context
from app.reporting.models import ReportContext

from .assumptions import MODULE_NAME


def build_winch_drum_report_context(snapshot: dict[str, Any]) -> ReportContext:
    """Map a saved snapshot without invoking the calculator."""

    return build_report_context(snapshot, module_name=MODULE_NAME)
