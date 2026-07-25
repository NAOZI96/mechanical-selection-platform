"""Strict, auditable DTOs shared by the post-MVP engineering modules.

This package contains software contracts only.  It intentionally defines no
mechanical standard values, product ratings, material allowables, service
factors, or manufacturer curves.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class SourceStatus(str, Enum):
    USER_INPUT = "user_input"
    PROJECT_SETTING = "project_setting"
    STANDARD_CONFIRMED = "standard_confirmed"
    MANUFACTURER_DATA = "manufacturer_data"
    PENDING_CONFIRMATION = "pending_confirmation"


class CalculationStatus(str, Enum):
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"


class ResultClassification(str, Enum):
    CALCULATED = "calculated"
    PRELIMINARY = "preliminary"
    REVIEW_REQUIRED = "review_required"
    INFORMATIONAL = "informational"


class WarningSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    BLOCKING = "blocking"


# These are numerical-safety limits for the software, not engineering limits.
PositiveFloat = Annotated[StrictFloat, Field(gt=0, le=1.0e15)]
NonNegativeFloat = Annotated[StrictFloat, Field(ge=0, le=1.0e15)]
Fraction = Annotated[StrictFloat, Field(gt=0, le=1)]
FactorAtLeastOne = Annotated[StrictFloat, Field(ge=1, le=1.0e6)]
PositiveInt = Annotated[StrictInt, Field(ge=1, le=1_000_000_000)]


class EngineeringInputBase(BaseModel):
    """Common provenance fields required by every engineering worksheet."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    basis_source_status: SourceStatus = Field(
        title="计算依据来源状态",
        description="说明本次系数、额定值或产品数据的来源状态；待确认时结果不会被包装成工程放行结论。",
        examples=[SourceStatus.MANUFACTURER_DATA.value],
        json_schema_extra={"group": "依据与边界"},
    )
    basis_reference: Annotated[StrictStr, Field(min_length=1, max_length=256)] = Field(
        title="计算依据或数据版本",
        description="填写项目文件、标准版本/条款或制造商样本编号；不能留空。",
        examples=["验证算例：用户输入，非项目推荐值"],
        json_schema_extra={"group": "依据与边界"},
    )

    @field_validator("basis_reference")
    @classmethod
    def strip_reference(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("计算依据或数据版本不能为空")
        return normalized


class AssumptionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    key: str
    value: float | int | bool | str | None
    unit: str | None = None
    source_status: SourceStatus
    note: str


class WarningRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    code: Annotated[str, Field(min_length=3, max_length=96, pattern=r"^[A-Z0-9_]+$")]
    severity: WarningSeverity
    title: Annotated[str, Field(min_length=1, max_length=128)]
    message: Annotated[str, Field(min_length=1, max_length=1024)]
    affected_result: tuple[str, ...] = ()
    recommended_action: Annotated[str, Field(min_length=1, max_length=1024)]

    @property
    def affected_fields(self) -> tuple[str, ...]:
        return self.affected_result


class FormulaStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    sequence: PositiveInt
    formula_id: Annotated[str, Field(min_length=3, max_length=96, pattern=r"^[A-Z0-9_]+-[0-9]{3}$")]
    expression: Annotated[str, Field(min_length=1, max_length=512)]
    variables: dict[str, float | int | bool | str]
    result_value: float | int | bool
    unit: Annotated[str, Field(max_length=32)]
    classification: ResultClassification


class ScalarResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    value: float | int | bool | str | None
    unit: Annotated[str, Field(max_length=32)]
    classification: ResultClassification
    formula_ids: tuple[str, ...]
    reason: str | None = None

    @model_validator(mode="after")
    def validate_unknown_result(self) -> ScalarResult:
        if self.value is None:
            if self.classification is not ResultClassification.REVIEW_REQUIRED:
                raise ValueError("未知结果必须标记为 review_required")
            if not self.reason:
                raise ValueError("未知结果必须说明原因")
        return self


class EngineeringResultBase[SIModelT: BaseModel](BaseModel):
    """Public result envelope consumed by the generic service and reports."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    module_id: str
    module_version: str
    calculation_model_version: str
    status: CalculationStatus
    input_si: SIModelT
    unchecked_items: tuple[str, ...]
    calculation_steps: tuple[FormulaStep, ...]
    warnings: tuple[WarningRecord, ...]
    assumptions: tuple[AssumptionRecord, ...]
    disclaimer: str


def calculation_status(warnings: tuple[WarningRecord, ...] | list[WarningRecord]) -> CalculationStatus:
    """Derive the persisted status from stable engineering warnings."""

    return CalculationStatus.COMPLETED_WITH_WARNINGS if warnings else CalculationStatus.COMPLETED
