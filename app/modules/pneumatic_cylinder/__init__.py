"""Public contract for deterministic pneumatic-cylinder calculations."""

from .calculator import calculate
from .constants import (
    CALCULATION_MODEL_VERSION,
    MODULE_ID,
    MODULE_NAME,
    MODULE_VERSION,
    REPORT_TEMPLATE_VERSION,
)
from .reporting import build_report_context
from .schema import Input, PneumaticCylinderInput, PneumaticCylinderResult, Result

__all__ = [
    "CALCULATION_MODEL_VERSION",
    "Input",
    "MODULE_ID",
    "MODULE_NAME",
    "MODULE_VERSION",
    "PneumaticCylinderInput",
    "PneumaticCylinderResult",
    "REPORT_TEMPLATE_VERSION",
    "Result",
    "build_report_context",
    "calculate",
]
