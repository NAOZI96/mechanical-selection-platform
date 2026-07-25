# API 规格

文档版本：0.5.0
API 版本：`v1`  
已注册模块：`winch_drum` + 8 个 Phase 7 受控工程工作表

## 1. 通用约定

- 基础路径：`/api/v1`；JSON 使用 UTF-8、snake_case 和 ISO 8601 UTC 时间。
- 所有工程字段使用明确带单位的名称。请求采用显示单位字段；响应同时提供原始输入、SI 输入和带单位结果。
- 数值只接受 JSON number，不接受数值字符串、NaN 或 Infinity。
- 计算成功状态：`completed` 或 `completed_with_warnings`；字段可部分不可计算时，用 `null + classification=review_required`，不得伪造 0。
- 相同输入不保证返回相同 calculation ID，但在相同 `calculation_model_version` 下应有相同规范化结果。
- 错误结构统一，HTTP 状态码不混入工程警告。
- `available=true` 只表示模块软件可进入；工程发布状态以 `release_status` 为准。当前 `winch_drum=engineering_review`，其余八模块均为 `internal_testing`。

## 2. 端点

### 2.1 健康检查

- `GET /health/live`：进程存活，不访问重资源。
- `GET /health/ready`：注册表非空、SQLite 关键表及 `001`～`005` 迁移清单齐全并可执行 `SELECT 1`，且固定 PDF 字体、报告目录和临时目录存在。该端点是浅层就绪检查，不执行 `PRAGMA quick_check`、目录写探针、计算或 PDF 试渲染。

### 2.1A Web 页面

- `GET /`：机械智选平台主页；展示运行时已注册模块，支持按模块名称/说明/能力搜索和按分类筛选。
- `GET /modules/{module_id}`：九个已注册模块的统一页面入口，例如 `/modules/winch_drum`、`/modules/transmission_check`。
- `HEAD /`、`HEAD /modules/{module_id}`：供可用性探针和爬虫做轻量状态检查。
- `GET|HEAD /docs`、`GET|HEAD /redoc`：同一份服务端渲染的 CSP-safe API 参考；不加载 CDN、不执行内联脚本，端点清单由当前 OpenAPI schema 生成。
- `GET /openapi.json`：FastAPI 生成的当前 API schema，供机器读取。
- `GET /robots.txt`：允许抓取；生产环境配置公共站点根地址后附带 sitemap 地址。
- `GET /sitemap.xml`：只在生产环境配置公共站点根地址时返回；首页始终可列入，模块 URL 只在对应 `release_status=released` 时列入。

主页的软件可用状态、工程发布状态和页面入口来自运行时注册表；规划模块不进入此 API，也不生成伪入口。浏览器请求不存在的页面时返回带请求 ID 的 HTML 404，API 客户端仍收到统一 JSON 错误。模块页面使用原生 JavaScript 调用统一计算 API；测试金样必须由用户显式载入并标明“非推荐参数”。页面不得自行实现公式或绕过后端 Pydantic 校验。

### 2.2 模块发现

`GET /api/v1/modules`

返回已启用模块的 `module_id`、名称、模块版本、计算模型版本、说明、分类、页面入口、软件可用状态和 `release_status`。`entry_path` 仅在模块注册了受信任的 Jinja2 页面模板时返回，否则为 `null`。

当前注册表应返回以下 9 个 ID：

| `module_id` | `release_status` |
|---|---|
| `winch_drum` | `engineering_review` |
| `transmission_check` | `internal_testing` |
| `gear_drive` | `internal_testing` |
| `shaft_bearing` | `internal_testing` |
| `lead_screw` | `internal_testing` |
| `synchronous_belt` | `internal_testing` |
| `motor_drive` | `internal_testing` |
| `stepper_motor` | `internal_testing` |
| `pneumatic_cylinder` | `internal_testing` |

`GET /api/v1/modules/{module_id}/schema`

返回 `module_id`、`release_status`、增强后的 `input_schema`、`result_schema`、`result_labels` 和 `example_input`。输入 schema 含字段单位、分组、约束和中文标签；显式验证算例只用于软件验证，不是项目默认或推荐参数。该 schema 用于页面生成辅助，但后端 Pydantic 模型仍是校验权威。

### 2.3 创建计算

`POST /api/v1/modules/{module_id}/calculations`

九个已注册模块都使用该通用路径。以下仍以 `winch_drum` 请求体说明首发模块的具体字段：

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
    "force_input_location": "drum_rope_end",
    "speed_input_location": "drum_rope_end",
    "force_input_type": "rated",
    "pulley_efficiency": 1.0,
    "brake_safety_factor": 1.5,
    "duty_class": "用户填写，仅提示",
    "approved_core_ratio": null,
    "minimum_dd_ratio": 20,
    "dead_wraps": 3,
    "backdrive_efficiency": null,
    "allow_forward_efficiency_as_reverse_approx": false,
    "assumption_sources": {
      "service_factor": "pending_confirmation",
      "pitch_factor": "pending_confirmation",
      "brake_safety_factor": "pending_confirmation"
    }
  }
}
```

示例数值只用于说明 JSON 形状，不是项目推荐默认值。

响应 `201 Created`：

```json
{
  "calculation_id": "uuid",
  "module_id": "winch_drum",
  "module_version": "1.2.0",
  "calculation_model_version": "winch_drum.calc.1.2.0",
  "release_status": "engineering_review",
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
      "value": 30000.0,
      "unit": "W",
      "classification": "preliminary",
      "reason": "按 project_default_iec_kw 冻结系列向上选档；启动和热容量待校核",
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
  "snapshot_schema_version": 4,
  "report_context": {
    "schema_version": 4,
    "release_status": "engineering_review",
    "release_status_label": "工程审核中"
  },
  "links": {
    "self": "/api/v1/calculations/uuid",
    "html_report": "/calculations/uuid/report",
    "pdf": "/api/v1/calculations/uuid/report.pdf"
  }
}
```

`layer_details[]` 至少含：`layer_number`、`center_diameter_m`、`turn_length_m`、`full_turns`、`used_turns`、`gross_capacity_m`、`usable_capacity_m` 和 `cumulative_usable_capacity_m`。

容量结果还应含 `capacity_satisfied`。若不足，`actual_layers`、`capacity_at_actual_layers_m`、`full_working_diameter_m`、`full_drum_speed_rpm` 和 `reference_ratio_full` 为 null；另返回 `evaluated_layers=max_layers`、`capacity_at_max_layers_m`、`capacity_shortfall_m`、`max_layer_working_diameter_m`、`max_layer_drum_speed_rpm` 和 `reference_ratio_max_layer`。

### 2.4 查询计算与报告

- `GET /api/v1/calculations/{calculation_id}`：返回保存的快照，不重算。
- `GET /calculations/{calculation_id}/report`：Jinja2 HTML 报告。
- `GET /api/v1/calculations/{calculation_id}/report.pdf`：先校验同 calculation/template artifact 的受控相对路径、文件大小和 SHA-256；有效缓存直接下载。没有有效缓存时，只允许从 schema v4 报告 DTO 同步生成，限并发 1。繁忙固定返回 `429 PDF_BUSY` 和 `Retry-After: 2`；超时、容量或渲染失败返回受控 `503`。

HTML 报告按快照中的 `module_id` 返回对应计算页，并提供下载同一计算记录 PDF 的明确入口。HTML/PDF 从计算时持久化的同一份未舍入报告 DTO 渲染，包含原始/SI 输入、关键结果、公式、来源、警告、版本和免责声明；`winch_drum` 另含逐层容量表。面向用户的字段、结果等级、来源状态和专项校核项使用中文展示。公式审计按公式编号、表达式、代入值和结果分层显示，展示优化不改变保存的表达式、变量或计算值。PDF 使用固定字体/模板版本，生成文件经大小、SHA-256、原子落盘和缓存完整性校验。

新计算的 snapshot schema 和 report context schema 均为 v4，并保存计算当时的 `release_status`。迁移前旧行的发布状态读取为 `legacy_unknown`：

- HTML 报告仍可读取旧 DTO，或在旧记录没有 DTO 时仅从已保存快照映射展示；不得重新运行计算器，并统一按“未记录（按内部测试边界处理）”显示。
- 与旧快照模板版本匹配且路径、大小、SHA-256 均有效的缓存 PDF 可继续下载；响应带 `X-Engineering-Release-Status: legacy_unknown`、`X-Legacy-Release-Status-Missing: true`、HTTP `Warning: 299 ...`，下载文件名前缀为 `legacy-`。
- 旧快照没有有效缓存 PDF 时返回 `409 LEGACY_RELEASE_STATUS_MISSING`；缓存文件缺失、大小或 SHA-256 不符时先将 artifact 标记为失败，再按同一 `409` 规则处理。系统不得用当前注册表的发布状态重建旧 PDF。

MVP 不提供任意目录文件名，不接受模板路径，不把 calculation ID 直接拼入文件系统路径。

### 2.5 响应安全与缓存

应用响应统一包含 `X-Request-ID`、`Content-Security-Policy`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`、`X-Frame-Options: DENY` 和禁用相机/定位/麦克风的 `Permissions-Policy`。CSP 只允许同源脚本和样式，并禁止插件对象、外部 base URI 与框架嵌入。`DESIGN_AGENT_PUBLIC_BASE_URL` 为 HTTPS 时额外返回一年期 HSTS。

缓存策略按路径冻结：

| 路径 | `Cache-Control` | 附加限制 |
|---|---|---|
| `/static/*` | `public, max-age=86400` | 静态文件 URL 变更时应更新查询版本。 |
| 所有含 `/calculations` 的 API、HTML 与 PDF 路径 | `no-store` | `X-Robots-Tag: noindex, nofollow, noarchive`。 |
| 其他页面/API（含 `/docs`） | `no-cache` | 客户端可保存但每次必须重新验证。 |

## 3. 校验规则与错误

### 3.1 HTTP 状态

| 状态 | 场景 |
|---:|---|
| 400 | JSON 格式或请求语义无法解析。 |
| 411 | 带请求体的方法缺少 `Content-Length`。 |
| 404 | 模块、计算或报告不存在。 |
| 409 | `LEGACY_RELEASE_STATUS_MISSING`：旧快照没有可验证缓存 PDF，且缺少生成新版 PDF 所需的计算时发布状态。 |
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
- 实际第一层绳中心直径 D/d 低于 `minimum_dd_ratio`：返回 `W_DD_RATIO_BELOW_MINIMUM` 高风险警告，包含实际比值、要求直径和按 `D=D_core+d` 反求的建议最小芯径；页面不得据此输出整机“设计合格”。
- 缺芯径且无批准 D/d：采用显式项目初选比 20；相关几何结果为 `preliminary` 并产生 D/d/标准条款警告。
- 缺反向效率且未显式允许近似：高速轴制动力矩为 `review_required`，低速轴静态参考仍返回。
- 八个扩展模块要求填写总依据状态和依据引用；凡工程系数、额定能力或制造商候选数据参与判断，必须同时提交对应来源状态与引用。缺少可计算输入返回 422；未提供可选候选额定值时保持基础计算并把相应选型结论列为待校核，不伪造通过值。

## 4. 结果、公式步骤与报告上下文

响应中的每个标量结果至少包括 `value`、`unit`、`classification`、`formula_ids`。公式过程快照内部还应包含：公式文本、符号、SI 代入值、未舍入结果和执行顺序。

HTML/PDF 使用独立报告 DTO，字段包括：

- 标题、计算 ID、模块/模型版本、生成时间；
- 计算当时的工程发布状态及中文标签；旧记录为空时为 `legacy_unknown`；
- 原始输入与 SI 输入；
- 关键结果汇总；
- 逐层表；
- 公式与代入过程；
- 假设、默认值来源、警告；
- 适用范围和免责声明。

报告模板禁止调用 `calculate()`；它只能消费保存的快照。

计算页的绳索类型、绳索结构、绳索材料、载荷谱和环境类型采用中文默认文本，并通过 HTML `datalist` 提供中文备选库。备选库不是工程枚举或合格性判定；用户仍可输入项目实际文本，后端继续按 Pydantic 非空、去首尾空白和长度上限校验，报告按保存值原样展示这些自由文本。

请求体上限为 1 MiB；`POST/PUT/PATCH` 必须提供可解析的 `Content-Length`。单份 PDF 上限 20 MiB，项目持久化容量默认 5 GiB，达到 85% 后停止新 PDF、仍保留计算和已有报告读取。

## 5. 兼容与版本策略

- `/api/v1` 只在破坏 HTTP 契约时升级大版本。
- `module_version` 标识模块接口和用户可见行为。
- `calculation_model_version` 标识数值模型、输入语义、默认值和警告规则。
- `snapshot_schema_version=4` 与报告上下文 `schema_version=4` 表示已冻结计算时发布状态；版本升级不触发旧快照重算。
- 当前报告模板版本为 `winch_drum.report.1.2.1`，八个扩展模块分别为对应的 `*.report.1.0.1`；模板版本参与 PDF artifact 缓存键。
- 增加可选字段可保持 API v1；改变字段语义、公式或默认值必须更新计算模型版本，并保留读取旧快照能力。
- 八个扩展模块均使用相同通用端点；每个模块的专属输入/结果由其注册 Pydantic schema 决定。需求、公式和证据见 [`MODULE_REQUIREMENTS.md`](MODULE_REQUIREMENTS.md)、[`EXPANDED_MODULES_CALCULATION_SPEC.md`](EXPANDED_MODULES_CALCULATION_SPEC.md) 和 [`EXPANDED_FORMULA_TEST_MATRIX.md`](EXPANDED_FORMULA_TEST_MATRIX.md)。

## 6. API 验收

- OpenAPI schema 与本文件字段、必填性和示例一致。
- 所有 422 错误能定位到字段或跨字段规则。
- 相同模型版本和 SI 输入的结果 JSON（除 ID/时间）稳定一致。
- `null` 结果必带 `review_required` 与原因，0 值不得代表未知。
- HTML/PDF 与 GET calculation 的关键值源自同一快照。
- `/docs` 和 `/redoc` 在严格 CSP 下可读且没有内联/外部脚本；安全头与三类缓存策略逐路由验证。
- 新快照保存计算时发布状态；`legacy_unknown` 的有效缓存 PDF 可读，无有效缓存时稳定返回 `409` 且不启动渲染器。
- 模块发现精确返回 9 个注册 ID 及上述发布状态；每个模块的页面、schema、POST、GET、HTML 和 PDF 路径均有本地回归。
