"""Shared contracts for independently versioned engineering modules."""

from .reporting import build_engineering_report_context
from .schema import (
    AssumptionRecord,
    CalculationStatus,
    EngineeringInputBase,
    EngineeringResultBase,
    FactorAtLeastOne,
    FormulaStep,
    Fraction,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    ResultClassification,
    ScalarResult,
    SourceStatus,
    WarningRecord,
    WarningSeverity,
    calculation_status,
)

__all__ = [
    "AssumptionRecord",
    "CalculationStatus",
    "EngineeringInputBase",
    "EngineeringResultBase",
    "FactorAtLeastOne",
    "FormulaStep",
    "Fraction",
    "NonNegativeFloat",
    "PositiveFloat",
    "PositiveInt",
    "ResultClassification",
    "ScalarResult",
    "SourceStatus",
    "WarningRecord",
    "WarningSeverity",
    "build_engineering_report_context",
    "calculation_status",
]
