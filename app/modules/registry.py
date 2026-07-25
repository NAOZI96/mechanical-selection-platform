"""Explicit registry for deterministic calculation modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.reporting.models import ReportContext

from .expanded_registry import EXPANDED_MODULE_SPECS
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
    summary: str = "确定性机械工程计算模块"
    category: str = "工程计算"
    web_template: str | None = None
    icon_key: str = "module"
    capabilities: tuple[str, ...] = ()
    catalog_order: int = 100
    featured: bool = False
    release_status: Literal["internal_testing", "engineering_review", "released"] = "internal_testing"
    input_labels: tuple[tuple[str, str], ...] = ()
    result_labels: tuple[tuple[str, str], ...] = ()
    unchecked_labels: tuple[tuple[str, str], ...] = ()
    assumption_labels: tuple[tuple[str, str], ...] = ()
    example_input: tuple[tuple[str, object], ...] = ()


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
        required_result_fields = {
            "module_id",
            "module_version",
            "calculation_model_version",
            "status",
            "input_si",
            "unchecked_items",
            "assumptions",
            "calculation_steps",
            "warnings",
            "disclaimer",
        }
        missing_result_fields = required_result_fields.difference(module.result_model.model_fields)
        if missing_result_fields:
            missing = "、".join(sorted(missing_result_fields))
            raise ValueError(f"模块结果缺少公共快照字段: {missing}")
        if not callable(module.calculate):
            raise TypeError("模块 calculate 必须可调用")
        if not callable(module.build_report_context):
            raise TypeError("模块 build_report_context 必须可调用")
        if not module.summary.strip() or not module.category.strip():
            raise ValueError("模块摘要和分类不能为空")
        if module.web_template:
            normalized_template = module.web_template.replace("\\", "/")
            if (
                normalized_template.startswith("/")
                or ".." in normalized_template.split("/")
                or not normalized_template.endswith(".html")
            ):
                raise ValueError("模块页面模板必须是 templates 目录内的 HTML 相对路径")
        if module.catalog_order < 0:
            raise ValueError("模块目录顺序不能为负数")
        if module.release_status not in {"internal_testing", "engineering_review", "released"}:
            raise ValueError("模块发布状态无效")
        unknown_example_fields = {key for key, _ in module.example_input}.difference(module.input_model.model_fields)
        if unknown_example_fields:
            unknown = "、".join(sorted(unknown_example_fields))
            raise ValueError(f"模块验证算例包含未知输入字段: {unknown}")
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
        summary="完成拉力、功率、逐层容绳、转速速比与静态制动力矩的可追溯计算。",
        category="起重与牵引",
        web_template="calculator.html",
        icon_key="winch",
        capabilities=("逐层离散容绳", "电机功率初选", "静态制动参考", "HTML / PDF 报告"),
        catalog_order=10,
        featured=True,
        release_status="engineering_review",
    )
)

for expanded_spec in EXPANDED_MODULE_SPECS:
    register_module(
        ModuleDefinition(
            module_id=expanded_spec.module_id,
            module_name=expanded_spec.module_name,
            module_version=expanded_spec.module_version,
            calculation_model_version=expanded_spec.calculation_model_version,
            report_template_version=expanded_spec.report_template_version,
            input_model=expanded_spec.input_model,
            result_model=expanded_spec.result_model,
            calculate=expanded_spec.calculate,
            build_report_context=expanded_spec.build_report_context,
            summary=expanded_spec.summary,
            category=expanded_spec.category,
            web_template="engineering_calculator.html",
            icon_key=expanded_spec.icon_key,
            capabilities=expanded_spec.capabilities,
            catalog_order=expanded_spec.catalog_order,
            release_status="internal_testing",
            input_labels=expanded_spec.input_labels,
            result_labels=expanded_spec.result_labels,
            unchecked_labels=expanded_spec.unchecked_labels,
            assumption_labels=expanded_spec.assumption_labels,
            example_input=expanded_spec.example_input,
        )
    )
