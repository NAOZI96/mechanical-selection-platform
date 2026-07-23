# API 规格

文档版本：0.1.0  
API 版本：`v1`  
首发模块：`winch_drum`

## 1. 通用约定

- 基础路径：`/api/v1`；JSON 使用 UTF-8、snake_case 和 ISO 8601 UTC 时间。
- 所有工程字段使用明确带单位的名称。请求采用显示单位字段；响应同时提供原始输入、SI 输入和带单位结果。
- 数值只接受 JSON number，不接受数值字符串、NaN 或 Infinity。
- 计算成功状态：`completed` 或 `completed_with_warnings`；字段可部分不可计算时，用 `null + classification=review_required`，不得伪造 0。
- 相同输入不保证返回相同 calculation ID，但在相同 `calculation_model_version` 下应有相同规范化结果。
- 错误结构统一，HTTP 状态码不混入工程警告。

## 2. 端点

### 2.1 健康检查

- `GET /health/live`：进程存活，不访问重资源。
- `GET /health/ready`：注册表有效、SQLite 可执行轻量查询。

### 2.2 模块发现

`GET /api/v1/modules`

返回已启用模块的 `module_id`、名称、模块版本、计算模型版本、说明和可用状态。

`GET /api/v1/modules/{module_id}/schema`

返回表单字段、单位、必填性、约束、默认行为、枚举、帮助文字和结果定义。该 schema 用于页面生成辅助，但后端 Pydantic 模型仍是校验权威。

### 2.3 创建计算

`POST /api/v1/modules/winch_drum/calculations`

请求体：

```json
{
  "input": {
    "rated_line_pull_kn": 100,
    "rope_diameter_mm": 20,
    "rope_speed_m_per_min": 12,
    "target_rope_capacity_m": 300,
    "service_factor": 1.2,
    "total_efficiency": 0.85,
    "motor_rated_speed_rpm": 1470,
    "motor_type": "三相异步电动机",
    "drum_core_diameter_mm": 400,
    "drum_face_length_mm": 800,
    "max_layers": 6,
    "pitch_factor": 1.05,
    "side_margin_mm": 20,
    "reeving_ratio": 1,
    "brake_safety_factor": 1.5,
    "duty_class": "用户填写，仅提示",
    "approved_core_ratio": null,
    "dead_wraps": 0,
    "allow_forward_efficiency_as_reverse_approx": false
  },
  "assumption_sources": {
    "service_factor": "待工程师确认",
    "pitch_factor": "待工程师确认",
    "brake_safety_factor": "待工程师确认"
  }
}
```

示例数值只用于说明 JSON 形状，不是项目推荐默认值。

响应 `201 Created`：

```json
{
  "calculation_id": "uuid",
  "module_id": "winch_drum",
  "module_version": "1.0.0",
  "calculation_model_version": "winch_drum.calc.1.0.0",
  "status": "completed_with_warnings",
  "created_at": "2026-07-22T00:00:00Z",
  "input_original": {},
  "input_si": {},
  "results": {
    "design_line_pull_n": {
      "value": 120000.0,
      "unit": "N",
      "classification": "calculated",
      "formula_ids": ["FORCE-001"]
    },
    "suggested_motor_power_w": {
      "value": null,
      "unit": "W",
      "classification": "review_required",
      "reason": "未配置经批准的电机标准功率系列及工作制规则",
      "formula_ids": ["POWER-003"]
    },
    "layer_details": []
  },
  "warnings": [
    {
      "code": "W_MOTOR_SELECTION_INCOMPLETE",
      "severity": "high",
      "message": "电机工作制、启动和热容量尚未校核。",
      "affected_fields": ["suggested_motor_power_w"]
    }
  ],
  "links": {
    "self": "/api/v1/calculations/uuid",
    "html_report": "/calculations/uuid/report",
    "pdf": "/api/v1/calculations/uuid/report.pdf"
  }
}
```

`layer_details[]` 至少含：`layer_number`、`working_diameter_m`、`turn_length_m`、`full_turns`、`used_turns`、`gross_capacity_m`、`usable_capacity_m` 和 `cumulative_usable_capacity_m`。

容量结果还应含 `capacity_satisfied`。若不足，`actual_layers` 与 `capacity_at_actual_layers_m` 为 null，另返回 `evaluated_layers=max_layers`、`capacity_at_max_layers_m`、`capacity_shortfall_m` 和最大层工作直径/转速。

### 2.4 查询计算与报告

- `GET /api/v1/calculations/{calculation_id}`：返回保存的快照，不重算。
- `GET /calculations/{calculation_id}/report`：Jinja2 HTML 报告。
- `GET /api/v1/calculations/{calculation_id}/report.pdf`：若已有且哈希/模板版本匹配则下载；否则从快照同步生成，限并发 1。繁忙返回 `429` 或 `503` 并带 `Retry-After`，实现前二选一并冻结契约。

MVP 不提供任意目录文件名，不接受模板路径，不把 calculation ID 直接拼入文件系统路径。

## 3. 校验规则与错误

### 3.1 HTTP 状态

| 状态 | 场景 |
|---:|---|
| 400 | JSON 格式或请求语义无法解析。 |
| 404 | 模块、计算或报告不存在。 |
| 409 | 幂等键冲突或报告状态冲突（若 Phase 1 启用幂等键）。 |
| 413 | 请求体超过限制。 |
| 422 | 字段或跨字段校验失败。 |
| 429 | 频率/PDF 并发限制。 |
| 500 | 未预期内部错误；不泄漏堆栈。 |
| 503 | 数据库/磁盘/PDF 渲染器暂不可用。 |

错误体：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "输入未通过校验",
    "request_id": "uuid",
    "details": [
      {
        "field": "drum_face_length_mm",
        "code": "INSUFFICIENT_USABLE_WIDTH",
        "message": "卷筒面长扣除两侧余量后必须至少容纳一圈。"
      }
    ]
  }
}
```

### 3.2 阻断与非阻断

- 类型、非有限数、非正值、`total_efficiency > 1`、非整数层数、`B-2b <= 0` 为阻断错误。
- 已知芯径与面长但容量不足：计算可保存为 `completed_with_warnings`，返回最大容量和缺口；报告显著标红，不给出“满足”结论。
- 缺芯径且无批准 D/d：依赖几何字段返回 `review_required`；功率等独立结果仍可保存。
- 缺反向效率且未显式允许近似：高速轴制动力矩为 `review_required`，低速轴静态参考仍返回。

## 4. 结果、公式步骤与报告上下文

响应中的每个标量结果至少包括 `value`、`unit`、`classification`、`formula_ids`。公式过程快照内部还应包含：公式文本、符号、SI 代入值、未舍入结果和执行顺序。

HTML/PDF 使用独立报告 DTO，字段包括：

- 标题、计算 ID、模块/模型版本、生成时间；
- 原始输入与 SI 输入；
- 关键结果汇总；
- 逐层表；
- 公式与代入过程；
- 假设、默认值来源、警告；
- 适用范围和免责声明。

报告模板禁止调用 `calculate()`；它只能消费保存的快照。

## 5. 兼容与版本策略

- `/api/v1` 只在破坏 HTTP 契约时升级大版本。
- `module_version` 标识模块接口和用户可见行为。
- `calculation_model_version` 标识数值模型、输入语义、默认值和警告规则。
- 增加可选字段可保持 API v1；改变字段语义、公式或默认值必须更新计算模型版本，并保留读取旧快照能力。
- 方案 B 使用相同通用端点 `/api/v1/modules/transmission_check/calculations`，其专属输入/结果由注册模块 schema 决定。

## 6. API 验收

- OpenAPI schema 与本文件字段、必填性和示例一致。
- 所有 422 错误能定位到字段或跨字段规则。
- 相同模型版本和 SI 输入的结果 JSON（除 ID/时间）稳定一致。
- `null` 结果必带 `review_required` 与原因，0 值不得代表未知。
- HTML/PDF 与 GET calculation 的关键值源自同一快照。
