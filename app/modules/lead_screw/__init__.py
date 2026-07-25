"""Equivalent square-thread sliding lead-screw module."""

from .calculator import (
    CALCULATION_MODEL_VERSION,
    MODULE_ID,
    MODULE_NAME,
    MODULE_VERSION,
    REPORT_TEMPLATE_VERSION,
    calculate,
)
from .reporting import build_report_context
from .schema import LeadScrewInput, LeadScrewResult

Input = LeadScrewInput
Result = LeadScrewResult

__all__ = [
    "CALCULATION_MODEL_VERSION",
    "Input",
    "LeadScrewInput",
    "LeadScrewResult",
    "MODULE_ID",
    "MODULE_NAME",
    "MODULE_VERSION",
    "REPORT_TEMPLATE_VERSION",
    "Result",
    "build_report_context",
    "calculate",
]
