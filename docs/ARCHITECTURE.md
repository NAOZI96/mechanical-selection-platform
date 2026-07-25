# 系统架构设计

文档版本：0.5.0
适用阶段：Phase 8 九模块产品候选版、发布状态数据治理与工程发布门禁

## 1. 架构目标与约束

系统部署在 2 核、1.9 GB 内存的 Ubuntu 24.04.4 LTS 主机，与现有服务共存。首版采用单 FastAPI Web 进程、Jinja2、原生 JavaScript/CSS 和 SQLite；不引入前端构建链、消息队列、缓存服务或独立数据库服务。计算必须确定、可复现、可版本化。

## 2. 逻辑架构

```text
浏览器
  └─ HTTP/HTML/JSON
      └─ FastAPI 单 worker
          ├─ Web 层：可筛选平台主页、统一模块页面、CSP-safe 文档、静态资源、安全/缓存头、错误页
          ├─ API 层：模块发现、校验、计算、报告查询
          ├─ 应用服务：SI 规范化、计算编排、快照保存、报告编排
          ├─ 模块注册表
          │   ├─ winch_drum（engineering_review）
          │   ├─ transmission_check / gear_drive / shaft_bearing / lead_screw
          │   └─ synchronous_belt / motor_drive / stepper_motor / pneumatic_cylinder
          │      （以上八模块均为 internal_testing）
          ├─ 确定性计算内核（纯 Python，无网络/无数据库副作用）
          ├─ Jinja2 HTML 报告 + 受限 PDF 渲染适配器
          └─ SQLite + 本地受控报告目录
```

边界原则：路由不包含工程公式；计算内核不访问数据库、文件、网络、时钟或大模型；保存成功后报告只读取快照，不重新执行计算。

## 3. 当前代码结构

```text
app/
  main.py
  core/             # 环境配置与应用级公共设施
  services/         # 确定性计算编排与不可变快照组装
  modules/
    catalog.py      # 注册模块与只读规划模块合并后的主页目录
    registry.py     # 可注入的显式模块注册表
    expanded_registry.py   # 八模块注册元数据与显式验证算例
    engineering_common/    # 八模块公共输入来源、结果、警告和报告映射契约
    winch_drum/
      schema.py
      calculator.py
      optimizer.py
      assumptions.py
      reporting.py
    transmission_check/    # 下列目录均保持 schema/calculator/reporting 解耦
    gear_drive/
    shaft_bearing/
    lead_screw/
    synchronous_belt/
    motor_drive/
    stepper_motor/
    pneumatic_cylinder/
  persistence/      # SQLite 连接、迁移、repository 与在线备份
  reporting/        # 不可变 DTO、HTML/PDF 映射、ReportLab 渲染和受限子进程
  templates/
  static/
  assets/fonts/     # 固定 Noto Sans SC 字体与许可
scripts/            # 资源基线与部署辅助检查
tests/
docs/
data/
```

平台主页使用 Jinja2 从运行时注册表生成可进入的软件模块，并提供原生 JavaScript 名称/说明/能力搜索、分类筛选、结果计数和空结果提示；当前九个规划 ID 均已由同 ID 注册模块替换。主页无需第三方动画运行库、外部 CDN 或前端构建链。`available` 只表示已注册且有页面入口，`release_status` 独立表示 `internal_testing|engineering_review|released`，不得把软件可运行误写成工程放行。规划项不进入计算 API，也没有模块页面入口。

`/docs` 与 `/redoc` 由同一个 Jinja2 模板服务端渲染，端点清单来自 `app.openapi()`；页面无需内联或第三方脚本，可在严格 CSP 下直接阅读。模块页面仍使用 Jinja2 外壳和同源原生 JavaScript 调用统一 API；公式、SI 换算、工程校验和警告只存在于后端模块。

计算事务物化 snapshot schema v4 和 report context schema v4，并保存计算当时的工程发布状态；HTML 与 PDF 只消费该快照/DTO。PDF 由受超时控制的单独 Python 子进程生成，完成后原子写入 `reports/`，SQLite 只保存状态、相对路径、哈希和大小。当前模板版本为 `winch_drum.report.1.2.1` 及八模块各自的 `*.report.1.0.1`。

## 4. 模块注册契约

每个模块实现同一协议：

| 成员 | 要求 |
|---|---|
| `module_id` | 稳定、小写 snake_case；方案 A 为 `winch_drum`。 |
| `module_name` | 面向用户的中文名称。 |
| `module_version` | 模块接口/行为 SemVer。 |
| `calculation_model_version` | 公式与默认规则版本；成功快照必须保存。 |
| `input_model` | Pydantic 输入模型，显示单位语义明确。 |
| `validate_business()` | 跨字段及工程可计算性校验。 |
| `normalize_si()` | 生成不可变 SI 输入。 |
| `calculate()` | 纯函数式确定性计算，返回未格式化结果和步骤。 |
| `generate_warnings()` | 基于输入/结果产生稳定警告代码。 |
| `build_report_context()` | 只把快照映射为报告上下文，不重新计算。 |
| `test_cases` | 单元、边界、性质和金样测试。 |
| `summary` / `category` | 主页与模块发现 API 使用的简短说明和分类。 |
| `web_template` | 可选、受信任的 Jinja2 相对模板路径；存在时开放统一模块页面入口。 |
| `capabilities` / `icon_key` | 主页展示元数据，不参与工程计算。 |
| `release_status` | `internal_testing`、`engineering_review` 或 `released`；与软件入口状态分离。 |
| `input_labels` / `result_labels` | 中文展示元数据，不改变 Pydantic 字段或数值语义。 |
| `example_input` | 由用户显式载入的验证算例；必须标明不是项目推荐参数。 |

注册表在应用启动时显式导入允许的模块并检查 ID 唯一、版本存在及契约完整。不得扫描和执行用户上传代码。核心路由只依赖协议，通过 `module_id` 查找实现。

### 4.1 八模块接入现状

`transmission_check` 以及另外七个扩展模块已经按同一注册契约实现。每个模块拥有独立输入/结果 schema、公式目录、警告和报告映射，复用公共来源状态、快照、API 与报告外壳，不复用 `winch_drum` 的业务模型。八模块需求和非范围见 [`MODULE_REQUIREMENTS.md`](MODULE_REQUIREMENTS.md)，精确公式和测试证据分别见 [`EXPANDED_MODULES_CALCULATION_SPEC.md`](EXPANDED_MODULES_CALCULATION_SPEC.md) 与 [`EXPANDED_FORMULA_TEST_MATRIX.md`](EXPANDED_FORMULA_TEST_MATRIX.md)。

软件接入链已经完成：实现协议 → 注册模块与页面元数据 → 复用通用 JSON 快照且不加专属结果列 → 契约测试 → API/主页/统一模块路径自动发现。后续仍须逐模块完成标准/制造商数据确认、独立工程审核和目标主机复验，才能提升 `release_status`。若未来需要模块间数据传递，应通过显式、版本化 DTO 和用户确认完成，禁止直接读取另一模块内部表或 Python 对象。

## 5. 请求与数据流

1. API/表单接收原始值和显示单位。
2. Pydantic 执行类型、有限数、长度和基础范围校验。
3. 模块执行跨字段校验，区分阻断错误与警告。
4. 单位层转换为 SI，并记录换算因子。
5. `calculate()` 产生全精度结果、逐步公式记录和结果分类。
6. 警告引擎追加稳定代码；应用层组装不可变快照，并将当前注册模块的 `release_status` 写入 schema v4 报告上下文。
7. 一个短事务保存计算主记录、可空发布状态列与 JSON 快照。
8. 返回 JSON 或渲染 HTML。PDF 请求先验证匹配模板版本的缓存相对路径、大小和 SHA-256；没有有效缓存时只允许从 schema v4 报告 DTO 构建，限并发 1，采用临时文件、大小/容量校验、SHA-256 后原子改名。

## 6. 精度、版本与确定性

- 内核冻结使用经边界与溢出测试的 IEEE-754 float；几何整圈比较采用明确的 `1e-12` 量级容差，持久化保留未舍入值，不允许 NaN/Infinity。
- 展示舍入集中在报告格式层；JSON 可同时返回 raw value 和 formatted value。
- 变更公式、单位语义、默认值、边界、舍入前算法或警告判定时，递增 `calculation_model_version`。
- 仅修改文案/样式且数值语义不变，可只递增应用版本。
- 老快照始终保留原版本；不得后台静默重算。旧行缺少当时发布状态时读取为 `legacy_unknown`，不得用当前注册表状态回填。
- 模块当前发布状态是注册时元数据；新计算同时冻结当次状态。改变注册状态必须有工程门禁证据，不改变历史快照中的模型版本、发布状态或计算结果。

## 7. SQLite 与并发

- 单 Web worker，避免多进程内存复制与 SQLite 写争用。
- 启用 WAL、foreign keys、busy timeout；事务短小，计算和 PDF 渲染不放在事务内。
- 每请求独立连接/会话；失败回滚。
- 有序迁移当前为 `001`～`005`；`005_calculation_release_status.sql` 只增加允许为空的受约束 `release_status` 列，以保留迁移前记录“当时状态未知”的事实。生产环境先在线备份再迁移，Web 启动时只接受完整迁移清单。
- PDF 通过进程内 `BoundedSemaphore(1)` 限制并发；额外请求立即返回受控 `429`。单 worker 同步等待受 30 s 超时保护的渲染子进程，失败不会删除计算快照。
- 不将大型 PDF 二进制写入 SQLite，只保存相对路径、哈希、大小和状态。
- 有效遗留缓存 PDF 可在完整性校验后继续下载并带 `legacy_unknown` 响应标记；旧快照没有有效缓存时返回 `409 LEGACY_RELEASE_STATUS_MISSING`，不进入渲染子进程。

## 8. 安全与故障隔离

- 限制请求体、字段长度、数值范围和报告生成频率；拒绝 NaN/Infinity。
- Jinja2 自动转义；富文本不接受用户 HTML；下载使用数据库 ID 映射，禁止路径拼接。
- 设置仅允许同源脚本/样式的 CSP、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`、`X-Frame-Options: DENY` 和最小化 `Permissions-Policy`；配置 HTTPS 公共根地址时启用一年期 HSTS，TLS 仍由既有反向代理终止。
- 静态资源响应 `public, max-age=86400`；所有计算/报告路径响应 `no-store` 并禁止搜索引擎索引；其余页面/API 响应 `no-cache`。每个响应携带请求 ID。
- 容器使用非 root 用户、只读应用文件系统（数据/报告/临时目录单独可写）、最小镜像和固定依赖版本。
- 不暴露 SQLite 与管理端口；Docker Compose 不接管或修改现有服务网络，端口默认仅绑定 `127.0.0.1`。
- 应用启动先验证固定 PDF 字体存在，并创建报告临时目录、执行写入/删除探针；失败即不接收流量。健康端点保持浅层，不触发计算、完整数据库检查或 PDF 试渲染。

## 9. 可观测性

- 结构化日志字段：request_id、module_id、model_version、duration_ms、status、warning_count；不记录完整用户输入。
- 指标可先从日志获得：请求量、错误率、计算延迟、PDF 延迟、数据库大小、报告目录大小和磁盘余量。
- `/health/live` 只确认进程；`/health/ready` 检查注册表非空、SQLite 关键表/完整迁移清单及 `SELECT 1`，以及固定字体、报告根目录和临时目录存在。它不替代启动时写探针、`PRAGMA quick_check`、备份恢复或报告冒烟。

## 10. 资源预算

冻结部署限制：Web 容器内存上限 512 MiB、预留 128 MiB，memory+swap 上限同为 512 MiB（即容器交换区为 0）；CPU 上限 1 核；单 worker；PDF 并发 1、超时 30 s；请求体上限 1 MiB；单 PDF 20 MiB；持久化总容量 5 GiB、85% 停止新 PDF。Docker JSON 日志每文件 10 MiB、最多 5 个。

本地基线中，1000 次计算 p95 30.489 ms、连续 20 份 PDF p95 594.880 ms，父进程与 PDF 子进程合计峰值 RSS 149,626,880 B；5 个并发 PDF 请求只有 1 个渲染，其余受控 `429`。目标 Docker 主机复验为计算 p95 23.895 ms、PDF p95 1.108 s、Web cgroup 峰值 186,097,664 B、容器交换区 0，既有服务保持健康。资源超限时优先拒绝 PDF，不影响计算页面与同机服务。

## 11. 架构验收

- 九个模块均可由统一发现/schema/计算/快照/HTML/PDF 路径访问，八个扩展模块无需复制核心路由。
- 八个扩展模块之间以及与 `winch_drum` 之间不直接导入业务计算实现。
- 用相同快照重复生成 HTML/PDF，关键字段一致。
- 并发触发多个 PDF 时实际同时渲染数不超过 1。
- 容器限制生效；压力测试期间主机可用内存和现有服务健康无明显恶化。
- SQLite 备份、恢复、WAL 清理和磁盘不足故障均有演练记录。
- `/docs` 与 `/redoc` 在严格 CSP 下无需外部/内联脚本即可阅读；安全头和三类缓存策略有逐路由回归。
- snapshot/report context schema v4 保存计算时发布状态；有效遗留缓存 PDF 可读，无有效缓存时稳定返回 409 且不重算。

当前 Phase 8 候选版新增可空迁移 `005_calculation_release_status.sql`，但没有新增常驻服务，也没有改变工程公式或计算模型版本。该候选版尚未执行远程部署；既有 Phase 4 资源与恢复数据只证明当时采用迁移 `001`～`004` 的 `winch_drum` 镜像，不能替代迁移 `005` 与当前九模块版本的目标机复验。
