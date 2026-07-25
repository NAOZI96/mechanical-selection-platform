"""Bearing basic-life and solid-shaft nominal-stress module."""

from .calculator import (
    CALCULATION_MODEL_VERSION,
    MODULE_ID,
    MODULE_NAME,
    MODULE_VERSION,
    REPORT_TEMPLATE_VERSION,
    calculate,
)
from .reporting import build_report_context
from .schema import ShaftBearingInput, ShaftBearingResult

Input = ShaftBearingInput
Result = ShaftBearingResult

__all__ = [
    "CALCULATION_MODEL_VERSION",
    "Input",
    "MODULE_ID",
    "MODULE_NAME",
    "MODULE_VERSION",
    "REPORT_TEMPLATE_VERSION",
    "Result",
    "ShaftBearingInput",
    "ShaftBearingResult",
    "build_report_context",
    "calculate",
]
