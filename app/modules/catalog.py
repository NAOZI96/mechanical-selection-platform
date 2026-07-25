"""Read-only homepage catalog built from registered and planned modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .registry import ModuleRegistry

CatalogStatus = Literal["available", "planned"]


@dataclass(frozen=True)
class ModuleCatalogItem:
    module_id: str
    module_name: str
    summary: str
    category: str
    icon_key: str
    capabilities: tuple[str, ...]
    status: CatalogStatus
    status_label: str
    entry_path: str | None
    module_version: str | None
    calculation_model_version: str | None
    catalog_order: int
    featured: bool = False
    engineering_release_status: str | None = None
    engineering_release_label: str | None = None


PLANNED_MODULES: tuple[ModuleCatalogItem, ...] = (
    ModuleCatalogItem(
        module_id="transmission_check",
        module_name="机械传动快速校核",
        summary="面向传动链的速比、扭矩、效率与关键接口校核。",
        category="传动系统",
        icon_key="transmission",
        capabilities=("速比链", "扭矩传递", "效率核算"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=20,
    ),
    ModuleCatalogItem(
        module_id="gear_drive",
        module_name="齿轮传动设计",
        summary="预留齿轮参数初选、几何关系和载荷校核工作流。",
        category="传动系统",
        icon_key="gear",
        capabilities=("参数初选", "几何关系", "载荷校核"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=30,
    ),
    ModuleCatalogItem(
        module_id="shaft_bearing",
        module_name="轴与轴承初选",
        summary="预留轴系载荷整理、轴承候选与寿命校核接口。",
        category="轴系部件",
        icon_key="bearing",
        capabilities=("载荷整理", "轴承初选", "寿命校核"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=40,
    ),
    ModuleCatalogItem(
        module_id="lead_screw",
        module_name="丝杆传动选型",
        summary="预留丝杆导程、推力、速度和驱动需求计算。",
        category="直线传动",
        icon_key="screw",
        capabilities=("导程匹配", "推力计算", "驱动需求"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=50,
    ),
    ModuleCatalogItem(
        module_id="synchronous_belt",
        module_name="同步带传动选型",
        summary="预留带型、带轮、中心距和传动能力的初选流程。",
        category="挠性传动",
        icon_key="belt",
        capabilities=("带型初选", "轮径匹配", "中心距校核"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=60,
    ),
    ModuleCatalogItem(
        module_id="motor_drive",
        module_name="电机与驱动功率",
        summary="预留稳态功率、工作制、启动和热容量选型链路。",
        category="驱动与执行",
        icon_key="motor",
        capabilities=("功率计算", "工作制", "启动校核"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=70,
    ),
    ModuleCatalogItem(
        module_id="stepper_motor",
        module_name="步进电机选型",
        summary="预留运动需求、负载惯量、转矩转速与安全余量校核。",
        category="驱动与执行",
        icon_key="stepper",
        capabilities=("运动需求", "惯量匹配", "转矩转速"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=80,
    ),
    ModuleCatalogItem(
        module_id="pneumatic_cylinder",
        module_name="气缸选型",
        summary="预留缸径、行程、推力、耗气量与安装条件初选。",
        category="驱动与执行",
        icon_key="cylinder",
        capabilities=("缸径初选", "推力校核", "耗气量"),
        status="planned",
        status_label="规划中",
        entry_path=None,
        module_version=None,
        calculation_model_version=None,
        catalog_order=90,
    ),
)


def build_module_catalog(registry: ModuleRegistry) -> tuple[ModuleCatalogItem, ...]:
    """Merge registered modules with roadmap placeholders without exposing placeholders as APIs."""

    registered: dict[str, ModuleCatalogItem] = {}
    for module in registry.list():
        registered[module.module_id] = ModuleCatalogItem(
            module_id=module.module_id,
            module_name=module.module_name,
            summary=module.summary,
            category=module.category,
            icon_key=module.icon_key,
            capabilities=module.capabilities,
            status="available",
            status_label="可用",
            entry_path=f"/modules/{module.module_id}" if module.web_template else None,
            module_version=module.module_version,
            calculation_model_version=module.calculation_model_version,
            catalog_order=module.catalog_order,
            featured=module.featured,
            engineering_release_status=module.release_status,
            engineering_release_label={
                "internal_testing": "内部测试",
                "engineering_review": "工程审核中",
                "released": "工程已放行",
            }[module.release_status],
        )

    catalog = list(registered.values())
    catalog.extend(item for item in PLANNED_MODULES if item.module_id not in registered)
    return tuple(sorted(catalog, key=lambda item: (item.catalog_order, item.module_id)))
