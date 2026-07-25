"""Deterministic one-to-four-stage transmission-chain module."""

from .calculator import (
    CALCULATION_MODEL_VERSION,
    MODULE_ID,
    MODULE_NAME,
    MODULE_VERSION,
    REPORT_TEMPLATE_VERSION,
    calculate,
)
from .reporting import build_report_context
from .schema import TransmissionCheckInput, TransmissionCheckResult

Input = TransmissionCheckInput
Result = TransmissionCheckResult

__all__ = [
    "CALCULATION_MODEL_VERSION",
    "Input",
    "MODULE_ID",
    "MODULE_NAME",
    "MODULE_VERSION",
    "REPORT_TEMPLATE_VERSION",
    "Result",
    "TransmissionCheckInput",
    "TransmissionCheckResult",
    "build_report_context",
    "calculate",
]
