"""Low-memory ReportLab renderer for persisted report contexts."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import ReportContext

FONT_NAME = "NotoSansSC"


def render_pdf(
    report: ReportContext,
    output_path: Path,
    font_path: Path,
) -> None:
    """Render one complete report without reading calculation code or storage."""

    if not font_path.is_file():
        raise FileNotFoundError(f"PDF 中文字体不存在: {font_path}")
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
    styles = _styles()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=report.title,
        author="机械智选",
        subject=f"{report.module_id} / {report.calculation_model_version}",
        pageCompression=1,
    )
    story: list[Any] = [
        Paragraph("MECHANICAL DESIGN CALCULATION", styles["eyebrow"]),
        Paragraph(_safe(report.title), styles["title"]),
        Spacer(1, 3 * mm),
        _metadata_table(report, styles),
        Spacer(1, 4 * mm),
        Paragraph("工程警告", styles["h2"]),
    ]
    if report.warnings:
        for warning in report.warnings:
            story.append(_warning_block(warning, styles))
            story.append(Spacer(1, 1.5 * mm))
    else:
        story.append(Paragraph("本快照没有记录警告。", styles["body"]))

    story.extend(
        [
            Paragraph("关键结果", styles["h2"]),
            _result_table(report, styles),
            PageBreak(),
            Paragraph("用户原始输入", styles["h2"]),
            _input_table(report.original_inputs, styles),
            Paragraph("SI 标准化输入", styles["h2"]),
            _input_table(report.si_inputs, styles),
        ]
    )
    if report.layer_rows:
        story.extend(
            [
                Paragraph("逐层容绳量", styles["h2"]),
                _layer_table(report, styles),
            ]
        )
    story.append(Paragraph("公式与换算审计步骤", styles["h2"]))
    for step in report.steps:
        story.append(_formula_block(step, styles))
        story.append(Spacer(1, 1.8 * mm))

    story.append(Paragraph("默认值、来源与假设", styles["h2"]))
    for item in report.assumptions:
        key = item.get("key_display", item.get("key", ""))
        source_status = item.get("source_status_display", item.get("source_status", ""))
        value_line = ""
        if "value_display" in item:
            unit = f" {_safe(item.get('unit_display', ''))}" if item.get("unit_display") else ""
            value_line = f"<br/><font color='#475569'>记录值：{_safe(item.get('value_display', ''))}{unit}</font>"
        story.append(
            Paragraph(
                (f"<b>{_safe(key)} / {_safe(source_status)}</b>{value_line}<br/>{_safe(item.get('note', ''))}"),
                styles["small"],
            )
        )
        story.append(Spacer(1, 1.2 * mm))

    story.extend(
        [
            Paragraph("未完成专项校核", styles["h2"]),
            Paragraph(_safe("、".join(report.unchecked_items)), styles["body"]),
            Spacer(1, 4 * mm),
            Table(
                [
                    [Paragraph("<b>免责声明</b>", styles["body"])],
                    [
                        Paragraph(
                            "本报告只读取计算时保存的不可变报告上下文，不重新执行工程公式。" + _safe(report.disclaimer),
                            styles["small"],
                        )
                    ],
                ],
                colWidths=[180 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7ed")),
                        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#b45309")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
        ]
    )
    document.build(
        story,
        onFirstPage=lambda canvas, doc: _page_footer(canvas, doc, report),
        onLaterPages=lambda canvas, doc: _page_footer(canvas, doc, report),
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCN",
            parent=base["Title"],
            fontName=FONT_NAME,
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#172033"),
            alignment=TA_CENTER,
            spaceAfter=2 * mm,
        ),
        "eyebrow": ParagraphStyle(
            "EyebrowCN",
            parent=base["Normal"],
            fontName=FONT_NAME,
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
            spaceAfter=1 * mm,
        ),
        "h2": ParagraphStyle(
            "Heading2CN",
            parent=base["Heading2"],
            fontName=FONT_NAME,
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#173f4f"),
            spaceBefore=5 * mm,
            spaceAfter=2.2 * mm,
        ),
        "body": ParagraphStyle(
            "BodyCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=8.2,
            leading=12,
            textColor=colors.HexColor("#172033"),
        ),
        "small": ParagraphStyle(
            "SmallCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=7.2,
            leading=10.5,
            textColor=colors.HexColor("#172033"),
            wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "TableHeaderCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=7.2,
            leading=9,
            textColor=colors.HexColor("#172033"),
            wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "TableCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=6.8,
            leading=9,
            textColor=colors.HexColor("#172033"),
            wordWrap="CJK",
        ),
        "warning": ParagraphStyle(
            "WarningCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=7.5,
            leading=11,
            textColor=colors.HexColor("#7f1d1d"),
            wordWrap="CJK",
        ),
        "formula_header": ParagraphStyle(
            "FormulaHeaderCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=7.6,
            leading=10,
            textColor=colors.HexColor("#0f5c74"),
            wordWrap="CJK",
        ),
        "formula_badge": ParagraphStyle(
            "FormulaBadgeCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=6.8,
            leading=9,
            textColor=colors.HexColor("#475569"),
            alignment=TA_RIGHT,
        ),
        "formula_expression": ParagraphStyle(
            "FormulaExpressionCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=8.2,
            leading=12,
            textColor=colors.HexColor("#172033"),
            wordWrap="CJK",
        ),
        "formula_detail": ParagraphStyle(
            "FormulaDetailCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=6.8,
            leading=10,
            textColor=colors.HexColor("#334155"),
            wordWrap="CJK",
        ),
        "formula_result": ParagraphStyle(
            "FormulaResultCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=7.4,
            leading=10,
            textColor=colors.HexColor("#0f5c74"),
            alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            "FooterCN",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=6.5,
            leading=8,
            textColor=colors.HexColor("#64748b"),
        ),
    }


def _metadata_table(report: ReportContext, styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        ["计算 ID", report.calculation_id, "状态", report.status_label or report.status],
        ["模块 / 版本", f"{report.module_id} / {report.module_version}", "计算时间 UTC", report.calculation_created_at],
        ["计算模型", report.calculation_model_version, "报告模板", report.report_template_version],
    ]
    rows = [[Paragraph(_safe(value), styles["small"]) for value in row] for row in data]
    return Table(
        rows,
        colWidths=[25 * mm, 65 * mm, 25 * mm, 65 * mm],
        style=_grid_style(header=False),
    )


def _result_table(report: ReportContext, styles: dict[str, ParagraphStyle]) -> LongTable:
    rows: list[list[Paragraph]] = [
        [_p(value, styles["table_header"]) for value in ("项目", "值", "单位", "等级", "公式")]
    ]
    for item in report.result_rows:
        label = _safe(item.label)
        value = item.display_value
        if item.reason:
            value = f"{_safe(value)}<br/><font color='#9a3412'>{_safe(item.reason)}</font>"
            value_cell = Paragraph(value, styles["table"])
        else:
            value_cell = _p(value, styles["table"])
        rows.append(
            [
                Paragraph(label, styles["table"]),
                value_cell,
                _p(item.unit, styles["table"]),
                _p(item.classification_label or item.classification, styles["table"]),
                _p("、".join(item.formula_ids), styles["table"]),
            ]
        )
    return LongTable(
        rows,
        colWidths=[47 * mm, 40 * mm, 20 * mm, 31 * mm, 42 * mm],
        repeatRows=1,
        splitByRow=1,
        style=_grid_style(header=True),
    )


def _input_table(rows: Any, styles: dict[str, ParagraphStyle]) -> LongTable:
    data = [[_p("字段", styles["table_header"]), _p("值", styles["table_header"])]]
    data.extend([_p(row.label, styles["table"]), _p(row.display_value, styles["table"])] for row in rows)
    return LongTable(
        data,
        colWidths=[62 * mm, 118 * mm],
        repeatRows=1,
        splitByRow=1,
        style=_grid_style(header=True),
    )


def _layer_table(report: ReportContext, styles: dict[str, ParagraphStyle]) -> LongTable:
    fields = (
        ("layer_number", "层"),
        ("center_diameter_m", "中心直径 m"),
        ("turn_length_m", "每圈 m"),
        ("full_turns", "完整圈"),
        ("usable_turns", "可用圈"),
        ("used_capacity_m", "使用 m"),
        ("cumulative_used_capacity_m", "累计 m"),
    )
    rows = [[_p(label, styles["table_header"]) for _, label in fields]]
    rows.extend([_p(_display(layer.get(field)), styles["table"]) for field, _ in fields] for layer in report.layer_rows)
    return LongTable(
        rows,
        colWidths=[13 * mm, 31 * mm, 29 * mm, 22 * mm, 22 * mm, 30 * mm, 33 * mm],
        repeatRows=1,
        splitByRow=1,
        style=_grid_style(header=True),
    )


def _warning_block(warning: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    content = Paragraph(
        (
            f"<b>{_safe(warning.get('code', ''))} / "
            f"{_safe(warning.get('severity_label', warning.get('severity', '')))}</b><br/>"
            f"{_safe(warning.get('message', ''))}<br/>"
            f"<font color='#475569'>{_safe(warning.get('recommended_action', ''))}</font>"
        ),
        styles["warning"],
    )
    return Table(
        [[content]],
        colWidths=[180 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#dc2626")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )


def _formula_block(step: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    formula_id = _safe(step.get("formula_id", ""))
    group_label = _safe(step.get("group_label", "公式"))
    classification = _safe(step.get("classification_label", step.get("classification", "")))
    expression = _safe(step.get("expression_display", step.get("expression", "")))
    variables = step.get("variables_display")
    if variables is None:
        variables_text = _display(step.get("variables", {}))
    else:
        variables_text = "；".join(f"{item.get('label', '')}={item.get('value', '')}" for item in variables)
    result = _safe(step.get("result_display", step.get("result_value", "")))
    unit = _safe(step.get("unit_display", step.get("unit", "")))
    rows = [
        [
            Paragraph(f"<b>{formula_id}</b> · {group_label}", styles["formula_header"]),
            Paragraph(classification, styles["formula_badge"]),
        ],
        [Paragraph(expression, styles["formula_expression"]), ""],
        [
            Paragraph(
                f"<font color='#64748b'>代入值</font><br/>{_safe(variables_text)}",
                styles["formula_detail"],
            ),
            "",
        ],
        [
            Paragraph("<font color='#64748b'>计算结果</font>", styles["formula_detail"]),
            Paragraph(f"<b>{result}</b> {unit}", styles["formula_result"]),
        ],
    ]
    return Table(
        rows,
        colWidths=[135 * mm, 45 * mm],
        style=TableStyle(
            [
                ("SPAN", (0, 1), (1, 1)),
                ("SPAN", (0, 2), (1, 2)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2f5")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("BACKGROUND", (0, 2), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#b8c3ce")),
                ("LINEABOVE", (0, 1), (-1, 1), 0.35, colors.HexColor("#dbe4ec")),
                ("LINEABOVE", (0, 2), (-1, 2), 0.35, colors.HexColor("#dbe4ec")),
                ("LINEABOVE", (0, 3), (-1, 3), 0.35, colors.HexColor("#dbe4ec")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("ALIGN", (1, 3), (1, 3), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )


def _grid_style(*, header: bool) -> TableStyle:
    commands: list[tuple[Any, ...]] = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b8c3ce")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef3")))
        commands.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#64748b")))
    return TableStyle(commands)


def _page_footer(canvas: Any, document: Any, report: ReportContext) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 6.5)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(15 * mm, 9 * mm, f"{report.calculation_id} · {report.calculation_model_version}")
    canvas.drawRightString(195 * mm, 9 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def _p(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe(value), style)


def _safe(value: Any) -> str:
    return escape("" if value is None else str(value))


def _display(value: Any) -> str:
    if value is None:
        return "待确认"
    if isinstance(value, float):
        return format(value, ".12g")
    if isinstance(value, dict):
        return "；".join(f"{key}={_display(item)}" for key, item in sorted(value.items()))
    if isinstance(value, (list, tuple)):
        return "、".join(_display(item) for item in value)
    return str(value)
