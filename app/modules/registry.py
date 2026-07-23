"""Explicit registry for deterministic calculation modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from .winch_drum.assumptions import (
    CALCULATION_MODEL_VERSION,
    MODULE_ID,
    MODULE_NAME,
    MODULE_VERSION,
)
from .winch_drum.calculator import calculate as calculate_winch_drum
from .winch_drum.schema import WinchDrumInput, WinchDrumResult


@dataclass(frozen=True)
class ModuleDefinition:
    module_id: str
    module_name: str
    module_version: str
    calculation_model_version: str
    input_model: type[BaseModel]
    result_model: type[BaseModel]
    calculate: Callable[[BaseModel], BaseModel]


_MODULES: dict[str, ModuleDefinition] = {}


def register_module(module: ModuleDefinition) -> None:
    """Register one module and reject incomplete or duplicate definitions."""

    if not module.module_id or not module.module_id.isidentifier() or module.module_id.lower() != module.module_id:
        raise ValueError("module_id 必须是非空的小写标识符")
    if module.module_id in _MODULES:
        raise ValueError(f"重复的 module_id: {module.module_id}")
    if not module.module_version or not module.calculation_model_version:
        raise ValueError("模块版本和计算模型版本不能为空")
    _MODULES[module.module_id] = module


def get_module(module_id: str) -> ModuleDefinition:
    """Return a registered module or raise a stable lookup error."""

    try:
        return _MODULES[module_id]
    except KeyError as exc:
        raise KeyError(f"未注册的计算模块: {module_id}") from exc


def list_modules() -> tuple[ModuleDefinition, ...]:
    """List registered modules in deterministic module-id order."""

    return tuple(_MODULES[key] for key in sorted(_MODULES))


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
        input_model=WinchDrumInput,
        result_model=WinchDrumResult,
        calculate=_calculate_registered_winch,
    )
)
