"""FastAPI application factory for the mechanical selector."""

from __future__ import annotations

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


def create_app(settings: Settings | None = None, registry: ModuleRegistry | None = None) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    active_registry = registry or default_registry()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if app_settings.auto_migrate_database:
            initialize_database(app_settings.database_path)
        elif not database_is_ready(app_settings.database_path):
            raise RuntimeError("数据库缺失或迁移未完成；生产环境必须先执行受控迁移")
        yield

    app = FastAPI(title="机械智选 · WinchCalc Engineering", version="0.4.0", lifespan=lifespan)
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
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        return response

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

    def module_or_404(module_id: str):
        try:
            return active_registry.get(module_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="计算模块不存在") from exc

    @app.get("/", response_class=HTMLResponse)
    @app.head("/", response_class=HTMLResponse, include_in_schema=False)
    def home_page(request: Request):
        catalog = build_module_catalog(active_registry)
        available_modules = tuple(item for item in catalog if item.status == "available")
        planned_modules = tuple(item for item in catalog if item.status == "planned")
        featured_module = next(
            (item for item in available_modules if item.featured),
            available_modules[0] if available_modules else None,
        )
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "available_modules": available_modules,
                "planned_modules": planned_modules,
                "featured_module": featured_module,
                "available_count": len(available_modules),
                "planned_count": len(planned_modules),
                "public_base_url": app_settings.public_base_url,
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
            {"module": module, "public_base_url": app_settings.public_base_url},
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
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{base_url}/</loc><priority>1.0</priority></url>"
            f"<url><loc>{base_url}/modules/winch_drum</loc><priority>0.9</priority></url>"
            "</urlset>"
        )
        return Response(content=body, media_type="application/xml")

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        if not active_registry.list() or not database_is_ready(app_settings.database_path):
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
            }
            for module in active_registry.list()
        ]

    @app.get("/api/v1/modules/{module_id}/schema")
    def module_schema(module_id: str) -> dict[str, Any]:
        module = module_or_404(module_id)
        return {
            "module_id": module.module_id,
            "input_schema": module.input_model.model_json_schema(),
            "result_schema": module.result_model.model_json_schema(),
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
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"winch-drum-{calculation_id}.pdf",
            headers={
                "ETag": f'"{artifact["sha256"]}"',
                "X-Report-SHA256": str(artifact["sha256"]),
                "X-Report-Template-Version": str(artifact["template_version"]),
            },
        )

    return app


def _error(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id, "details": []}},
    )


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


app = create_app()
