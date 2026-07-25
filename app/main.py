"""FastAPI application factory for the mechanical selector."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from html import escape
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import PROJECT_ROOT, Settings
from app.modules.catalog import build_module_catalog
from app.modules.registry import ModuleRegistry, default_registry
from app.persistence.database import database_is_ready, initialize_database
from app.persistence.repository import CalculationRepository
from app.reporting.context import build_report_context
from app.reporting.models import ReportContext
from app.reporting.service import PdfReportService, ReportServiceError
from app.services.calculations import CalculationService

LOGGER = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, registry: ModuleRegistry | None = None) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    active_registry = registry or default_registry()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if app_settings.auto_migrate_database:
            initialize_database(app_settings.database_path)
        elif not database_is_ready(app_settings.database_path):
            raise RuntimeError("数据库缺失或迁移未完成；生产环境必须先执行受控迁移")
        report_service.validate_runtime()
        yield

    app = FastAPI(
        title="机械智选 · Mechanical Selection Platform",
        version="0.5.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = app_settings
    repository = CalculationRepository(app_settings.database_path)
    service = CalculationService(repository, active_registry.get)
    report_service = PdfReportService(repository, app_settings)
    app.state.report_service = report_service
    templates = Jinja2Templates(directory=PROJECT_ROOT / "app" / "templates")
    app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")

    @app.middleware("http")
    async def request_controls(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        body_method = request.method in {"POST", "PUT", "PATCH"}
        if body_method and content_length is None:
            response = _error(
                411,
                "CONTENT_LENGTH_REQUIRED",
                "带请求体的接口必须提供 Content-Length",
                request_id,
            )
        else:
            try:
                request_too_large = bool(content_length and int(content_length) > app_settings.request_body_limit_bytes)
            except ValueError:
                request_too_large = True
            if request_too_large:
                response = _error(
                    413,
                    "REQUEST_TOO_LARGE",
                    f"请求体超过 {app_settings.request_body_limit_bytes} 字节限制",
                    request_id,
                )
            else:
                response = await call_next(request)
        return _apply_response_controls(response, request, app_settings)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        return _validation_error(request.state.request_id, exc.errors())

    @app.exception_handler(HTTPException)
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        messages = {
            404: "请求的资源不存在",
            501: "该功能尚未实现",
            503: "服务暂不可用",
        }
        detail_message = str(exc.detail) if exc.detail else ""
        display_message = (
            messages.get(exc.status_code, "请求失败")
            if detail_message in {"", "Not Found", "Service Unavailable"}
            else detail_message
        )
        if request.method in {"GET", "HEAD"} and "text/html" in request.headers.get("accept", ""):
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "status_code": exc.status_code,
                    "message": display_message,
                    "request_id": request.state.request_id,
                },
                status_code=exc.status_code,
            )
        return _error(
            exc.status_code,
            f"HTTP_{exc.status_code}",
            display_message,
            request.state.request_id,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        LOGGER.exception(
            "Unhandled application error request_id=%s path=%s",
            request.state.request_id,
            request.url.path,
            exc_info=exc,
        )
        message = "服务处理请求时发生错误，请使用请求 ID 联系维护人员"
        if request.method in {"GET", "HEAD"} and "text/html" in request.headers.get("accept", ""):
            response = templates.TemplateResponse(
                request,
                "error.html",
                {
                    "status_code": 500,
                    "message": message,
                    "request_id": request.state.request_id,
                },
                status_code=500,
            )
        else:
            response = _error(
                500,
                "INTERNAL_SERVER_ERROR",
                message,
                request.state.request_id,
            )
        return _apply_response_controls(response, request, app_settings)

    def module_or_404(module_id: str):
        try:
            return active_registry.get(module_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="计算模块不存在") from exc

    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    @app.head("/docs", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
    @app.head("/redoc", response_class=HTMLResponse, include_in_schema=False)
    def api_documentation(request: Request):
        descriptions = {
            ("GET", "/api/v1/modules"): "发现已注册模块、软件入口与工程发布状态。",
            ("GET", "/api/v1/modules/{module_id}/schema"): "读取模块输入契约、中文标签、单位和验证算例。",
            ("POST", "/api/v1/modules/{module_id}/calculations"): "严格校验输入，执行确定性计算并保存不可变快照。",
            ("GET", "/api/v1/calculations/{calculation_id}"): "按计算 ID 读取已保存快照，不重新执行公式。",
            ("GET", "/calculations/{calculation_id}/report"): "读取快照并呈现同源 HTML 工程报告。",
            ("GET", "/api/v1/calculations/{calculation_id}/report.pdf"): "生成或读取同源 PDF 工程报告。",
            ("GET", "/health/live"): "进程存活探针。",
            ("GET", "/health/ready"): "模块注册表和数据库就绪探针。",
        }
        endpoints: list[dict[str, Any]] = []
        for path, operations in app.openapi().get("paths", {}).items():
            for method, operation in operations.items():
                upper_method = method.upper()
                if upper_method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                endpoints.append(
                    {
                        "method": upper_method,
                        "path": path,
                        "summary": descriptions.get(
                            (upper_method, path),
                            str(operation.get("summary") or "平台接口"),
                        ),
                        "tags": tuple(str(tag) for tag in operation.get("tags", ())),
                    }
                )
        method_order = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}
        endpoints.sort(key=lambda item: (item["path"], method_order[item["method"]]))
        return templates.TemplateResponse(
            request,
            "api_docs.html",
            {
                "endpoints": endpoints,
                "platform_version": app.version,
            },
        )

    @app.get("/", response_class=HTMLResponse)
    @app.head("/", response_class=HTMLResponse, include_in_schema=False)
    def home_page(request: Request):
        catalog = build_module_catalog(active_registry)
        available_modules = tuple(item for item in catalog if item.status == "available")
        planned_modules = tuple(item for item in catalog if item.status == "planned")
        module_categories = tuple(dict.fromkeys(item.category for item in available_modules))
        featured_module = next(
            (item for item in available_modules if item.featured),
            available_modules[0] if available_modules else None,
        )
        release_counts = {
            status: sum(item.engineering_release_status == status for item in available_modules)
            for status in ("internal_testing", "engineering_review", "released")
        }
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "module_catalog": catalog,
                "available_modules": available_modules,
                "planned_modules": planned_modules,
                "featured_module": featured_module,
                "available_count": len(available_modules),
                "planned_count": len(planned_modules),
                "module_categories": module_categories,
                "release_counts": release_counts,
                "public_base_url": app_settings.public_base_url,
                "platform_version": app.version,
            },
        )

    @app.get("/modules/{module_id}", response_class=HTMLResponse)
    @app.head("/modules/{module_id}", response_class=HTMLResponse, include_in_schema=False)
    def module_page(module_id: str, request: Request):
        module = module_or_404(module_id)
        if not module.web_template:
            raise HTTPException(status_code=501, detail="该模块尚未配置网页界面")
        return templates.TemplateResponse(
            request,
            module.web_template,
            {
                "module": module,
                "public_base_url": app_settings.public_base_url,
                "platform_version": app.version,
            },
        )

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots() -> str:
        lines = ["User-agent: *", "Allow: /"]
        if app_settings.public_base_url:
            lines.extend(("", f"Sitemap: {app_settings.public_base_url}/sitemap.xml"))
        return "\n".join(lines) + "\n"

    @app.get("/sitemap.xml", response_class=Response)
    def sitemap() -> Response:
        if not app_settings.public_base_url:
            raise HTTPException(status_code=404, detail="未配置公共站点地址")
        base_url = escape(app_settings.public_base_url, quote=True)
        module_urls = "".join(
            f"<url><loc>{base_url}/modules/{module.module_id}</loc><priority>0.9</priority></url>"
            for module in active_registry.list()
            if module.web_template and module.release_status == "released"
        )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{base_url}/</loc><priority>1.0</priority></url>"
            f"{module_urls}"
            "</urlset>"
        )
        return Response(content=body, media_type="application/xml")

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        if (
            not active_registry.list()
            or not database_is_ready(app_settings.database_path, verify_integrity=False)
            or not report_service.is_ready()
        ):
            raise HTTPException(status_code=503, detail="应用尚未就绪")
        return {"status": "ready"}

    @app.get("/api/v1/modules")
    def modules() -> list[dict[str, Any]]:
        return [
            {
                "module_id": module.module_id,
                "module_name": module.module_name,
                "module_version": module.module_version,
                "calculation_model_version": module.calculation_model_version,
                "description": module.summary,
                "category": module.category,
                "entry_path": f"/modules/{module.module_id}" if module.web_template else None,
                "available": True,
                "release_status": module.release_status,
            }
            for module in active_registry.list()
        ]

    @app.get("/api/v1/modules/{module_id}/schema")
    def module_schema(module_id: str) -> dict[str, Any]:
        module = module_or_404(module_id)
        input_schema = module.input_model.model_json_schema()
        _enrich_input_schema(input_schema, module.input_labels, module.example_input)
        return {
            "module_id": module.module_id,
            "release_status": module.release_status,
            "input_schema": input_schema,
            "result_schema": module.result_model.model_json_schema(),
            "result_labels": dict(module.result_labels),
            "unchecked_labels": dict(module.unchecked_labels),
            "assumption_labels": dict(module.assumption_labels),
            "example_input": dict(module.example_input),
        }

    @app.post("/api/v1/modules/{module_id}/calculations", status_code=201)
    def create_calculation(module_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        module_or_404(module_id)
        raw_input = payload.get("input")
        if not isinstance(raw_input, dict):
            return _validation_error(
                request.state.request_id,
                [{"loc": ("body", "input"), "msg": "必须提供 input 对象", "type": "missing"}],
            )
        if "assumption_sources" in payload:
            raw_input = {**raw_input, "assumption_sources": payload["assumption_sources"]}
        try:
            return service.create(module_id, raw_input, request.state.request_id)
        except ValidationError as exc:
            return _validation_error(request.state.request_id, exc.errors())

    @app.get("/api/v1/calculations/{calculation_id}")
    def get_calculation(calculation_id: str) -> dict[str, Any]:
        snapshot = service.get(calculation_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="计算记录不存在")
        return snapshot

    @app.get("/calculations/{calculation_id}/report", response_class=HTMLResponse)
    def html_report(calculation_id: str, request: Request):
        snapshot = service.get(calculation_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="计算记录不存在")
        persisted_context = snapshot.get("report_context")
        report_context = (
            ReportContext.model_validate(persisted_context)
            if persisted_context is not None
            else build_report_context(snapshot, module_name=snapshot["module_id"])
        )
        return templates.TemplateResponse(
            request,
            "calculation_report.html",
            {"report": report_context},
        )

    @app.get("/api/v1/calculations/{calculation_id}/report.pdf")
    def pdf_report(calculation_id: str, request: Request):
        snapshot = service.get(calculation_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="计算记录不存在")
        try:
            path, artifact = report_service.get_or_generate(snapshot)
        except ReportServiceError as exc:
            response = _error(
                exc.status_code,
                exc.code,
                exc.message,
                request.state.request_id,
            )
            if exc.retry_after_seconds is not None:
                response.headers["Retry-After"] = str(exc.retry_after_seconds)
            return response
        legacy_release_status = snapshot["release_status"] == "legacy_unknown"
        response_headers = {
            "ETag": f'"{artifact["sha256"]}"',
            "X-Report-SHA256": str(artifact["sha256"]),
            "X-Report-Template-Version": str(artifact["template_version"]),
            "X-Engineering-Release-Status": str(snapshot["release_status"]),
            "X-Legacy-Release-Status-Missing": str(legacy_release_status).lower(),
        }
        if legacy_release_status:
            response_headers["Warning"] = '299 - "Legacy report: engineering release status was not recorded"'
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"{'legacy-' if legacy_release_status else ''}{snapshot['module_id']}-{calculation_id}.pdf",
            headers=response_headers,
        )

    return app


def _error(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id, "details": []}},
    )


def _apply_response_controls(response: Response, request: Request, settings: Settings) -> Response:
    request_id = request.state.request_id
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    elif "/calculations" in request.url.path:
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    else:
        response.headers.setdefault("Cache-Control", "no-cache")
    if settings.public_base_url and settings.public_base_url.startswith("https://"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


def _validation_error(request_id: str, errors: list[dict[str, Any]]) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in error.get("loc", ()) if part != "body"),
            "code": str(error.get("type", "VALIDATION_ERROR")).upper(),
            "message": error.get("msg", "输入未通过校验"),
        }
        for error in errors
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "输入未通过校验",
                "request_id": request_id,
                "details": details,
            }
        },
    )


def _enrich_input_schema(
    schema: dict[str, Any],
    input_labels: tuple[tuple[str, str], ...],
    example_input: tuple[tuple[str, object], ...],
) -> None:
    """Add user-facing metadata without changing Pydantic validation."""

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return
    labels = dict(input_labels)
    examples = dict(example_input)
    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        if field_name in labels:
            field_schema["title"] = labels[field_name]
        field_schema.setdefault(
            "description",
            "按实际工况或已确认的候选数据填写；工程系数和额定能力必须与所填依据版本一致。",
        )
        unit = _display_unit_from_field_name(field_name)
        if unit:
            field_schema.setdefault("unit", unit)
        field_schema.setdefault("group", _input_group(field_name))
        if field_name in examples:
            field_schema["examples"] = [examples[field_name]]


def _display_unit_from_field_name(field_name: str) -> str | None:
    exact_units = {
        "driver_teeth": "齿",
        "driven_teeth": "齿",
        "pinion_teeth": "齿",
        "gear_teeth": "齿",
        "full_steps_per_revolution": "整步/r",
        "microstep_divisor": "微步/整步",
        "lead_mm_per_revolution": "mm/r",
    }
    if field_name in exact_units:
        return exact_units[field_name]
    suffixes = (
        ("_mm_per_revolution", "mm/r"),
        ("_kg_m2", "kg·m²"),
        ("_m3_min", "m³/min"),
        ("_m_per_s", "m/s"),
        ("_m_s", "m/s"),
        ("_rad_s2", "rad/s²"),
        ("_rad_s", "rad/s"),
        ("_n_m", "N·m"),
        ("_mpa", "MPa"),
        ("_gpa", "GPa"),
        ("_pa", "Pa"),
        ("_rpm", "r/min"),
        ("_mm", "mm"),
        ("_deg", "°"),
        ("_kw", "kW"),
        ("_w", "W"),
        ("_n", "N"),
        ("_s", "s"),
        ("_hz", "Hz"),
        ("_l_min", "L/min"),
        ("_percent", "%"),
        ("_m", "m"),
    )
    for suffix, unit in suffixes:
        if field_name.endswith(suffix):
            return unit
    return None


def _input_group(field_name: str) -> str:
    if field_name.startswith(("basis_", "candidate_")) or "source_status" in field_name or "reference" in field_name:
        return "依据与候选数据"
    if any(token in field_name for token in ("efficiency", "factor", "coefficient", "exponent", "ratio")):
        return "工程系数与模型"
    return "工况与几何"


app = create_app()
