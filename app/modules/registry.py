"""Explicit registry for deterministic calculation modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.reporting.models import ReportContext

from .winch_drum.assumptions import (
    CALCULATION_MODEL_VERSION,
    MODULE_ID,
    MODULE_NAME,
    MODULE_VERSION,
    REPORT_TEMPLATE_VERSION,
)
from .winch_drum.calculator import calculate as calculate_winch_drum
from .winch_drum.reporting import build_winch_drum_report_context
from .winch_drum.schema import WinchDrumInput, WinchDrumResult


@dataclass(frozen=True)
class ModuleDefinition:
    module_id: str
    module_name: str
    module_version: str
    calculation_model_version: str
    report_template_version: str
    input_model: type[BaseModel]
    result_model: type[BaseModel]
    calculate: Callable[[BaseModel], BaseModel]
    build_report_context: Callable[[dict[str, object]], ReportContext]


class ModuleRegistry:
    """Explicit, injectable registry used by both the app and contract tests."""

    def __init__(self) -> None:
        self._modules: dict[str, ModuleDefinition] = {}

    def register(self, module: ModuleDefinition) -> None:
        if not module.module_id or not module.module_id.isidentifier() or module.module_id.lower() != module.module_id:
            raise ValueError("module_id 必须是非空的小写标识符")
        if module.module_id in self._modules:
            raise ValueError(f"重复的 module_id: {module.module_id}")
        if not module.module_version or not module.calculation_model_version or not module.report_template_version:
            raise ValueError("模块版本、计算模型版本和报告模板版本不能为空")
        if not issubclass(module.input_model, BaseModel) or not issubclass(module.result_model, BaseModel):
            raise TypeError("模块输入和结果必须是 Pydantic BaseModel")
        if not callable(module.calculate):
            raise TypeError("模块 calculate 必须可调用")
        if not callable(module.build_report_context):
            raise TypeError("模块 build_report_context 必须可调用")
        self._modules[module.module_id] = module

    def get(self, module_id: str) -> ModuleDefinition:
        try:
            return self._modules[module_id]
        except KeyError as exc:
            raise KeyError(f"未注册的计算模块: {module_id}") from exc

    def list(self) -> tuple[ModuleDefinition, ...]:
        return tuple(self._modules[key] for key in sorted(self._modules))


_REGISTRY = ModuleRegistry()


def default_registry() -> ModuleRegistry:
    """Return the process-wide explicitly populated application registry."""

    return _REGISTRY


def register_module(module: ModuleDefinition) -> None:
    """Register one module and reject incomplete or duplicate definitions."""

    _REGISTRY.register(module)


def get_module(module_id: str) -> ModuleDefinition:
    """Return a registered module or raise a stable lookup error."""

    return _REGISTRY.get(module_id)


def list_modules() -> tuple[ModuleDefinition, ...]:
    """List registered modules in deterministic module-id order."""

    return _REGISTRY.list()


def _calculate_registered_winch(data: BaseModel) -> BaseModel:
    if not isinstance(data, WinchDrumInput):
        raise TypeError("winch_drum 需要 WinchDrumInput")
    result: WinchDrumResult = calculate_winch_drum(data)
    return result


register_module(
    ModuleDefinition(
        module_id=MODULE_ID,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        calculation_model_version=CALCULATION_MODEL_VERSION,
        report_template_version=REPORT_TEMPLATE_VERSION,
        input_model=WinchDrumInput,
        result_model=WinchDrumResult,
        calculate=_calculate_registered_winch,
        build_report_context=build_winch_drum_report_context,
    )
)
