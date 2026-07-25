"""Standard external spur-gear geometry and nominal mesh-force module."""

from .calculator import (
    CALCULATION_MODEL_VERSION,
    MODULE_ID,
    MODULE_NAME,
    MODULE_VERSION,
    REPORT_TEMPLATE_VERSION,
    calculate,
)
from .reporting import build_report_context
from .schema import GearDriveInput, GearDriveResult

Input = GearDriveInput
Result = GearDriveResult

__all__ = [
    "CALCULATION_MODEL_VERSION",
    "GearDriveInput",
    "GearDriveResult",
    "Input",
    "MODULE_ID",
    "MODULE_NAME",
    "MODULE_VERSION",
    "REPORT_TEMPLATE_VERSION",
    "Result",
    "build_report_context",
    "calculate",
]
