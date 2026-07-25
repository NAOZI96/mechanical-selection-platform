# 机械智选（Design Agent）

面向机械设计人员的轻量级、可审计计算与初选平台。项目使用确定性 Python 代码执行工程计算，保留输入、单位换算、公式步骤、模型版本、假设、警告与报告，帮助工程师进行方案比较和初步选型。

> 当前状态：平台已在本地注册 9 个确定性计算模块。`winch_drum` 处于 `engineering_review`；新增的 8 个受控工程工作表处于 `internal_testing`，已具备可直接试用的产品界面、统一 API、不可变快照及同源 HTML/PDF 报告，但尚未完成制造、采购或安全工程放行。既有 `winch_drum` 版本已完成目标主机回环部署；当前九模块候选版及迁移 `005_calculation_release_status.sql` 尚未远程部署，公共 Caddy/TLS 仍受 ICP 备案/接入门禁阻断。

## 项目目标

- 使用可追溯、可重复的确定性计算，避免不可解释的工程结论。
- 内部统一采用 SI 单位，显示层负责单位转换。
- 明确区分理论计算、工程初选、建议结果和待人工校核项。
- 通过模块注册机制扩展新的机械计算工具，业务计算与 Web、数据库和报告渲染解耦。
- 以平台主页统一组织已注册与规划中的机械模块，并把“软件可运行”和“工程已放行”作为两个独立状态。
- 在 2 核 CPU、1.9 GB 内存的服务器上以单 Web worker 低资源运行。

## 已注册模块

`winch_drum` 是首发模块，当前工程发布状态为 `engineering_review`，面向绞车与卷筒的初步计算，范围包括：

- 设计拉力、理论负载功率和最低所需电机功率；
- 卷筒芯径、排绳节距和可用宽度；
- 按层离散的容绳量与部分末层计算；
- 空卷/满卷工作直径、卷筒转速和参考减速比；
- 静态保持制动力矩参考值；
- 输入、公式、假设、警告、模型版本及报告快照。

本模块不覆盖钢丝绳强度、卷筒结构强度、疲劳寿命、动态冲击、热平衡、排绳质量、品牌型号数据库或采购级自动选型。完整边界见[计算规格](docs/CALCULATION_SPEC.md)。

Phase 7 新增 8 个 `internal_testing` 受控工程工作表：

| 模块 ID | 工作表范围 |
|---|---|
| `transmission_check` | 1～4 级正向稳态传动链的速比、效率、转速、转矩与功率审计 |
| `gear_drive` | 标准直齿外啮合基础几何、名义啮合力、节线速度与用户给定限值比较 |
| `shaft_bearing` | 用户给定 X、Y、p 下的轴承 L10 基本额定寿命及实心圆轴名义应力 |
| `lead_screw` | 等效方牙模型的提升/下降转矩、效率、自锁、功率与 Euler 理论临界载荷 |
| `synchronous_belt` | 同步带速比、节径、带速、设计功率、近似带长与啮合齿数 |
| `motor_drive` | 两个明确稳态工作段的连续、峰值、RMS 转矩与功率折算 |
| `stepper_motor` | 刚性传动下的惯量折算、恒加速转矩、脉冲频率与曲线工作点比较 |
| `pneumatic_cylinder` | 双作用单杆气缸理论伸缩力、负载余量、扫掠体积与理想参考状态耗气量 |

这些模块不是产品目录或自动选型器。用户必须填写工况、依据来源以及适用时的候选额定值；系统不会虚构标准系数或制造商数据。需求边界见[八模块需求基线](docs/MODULE_REQUIREMENTS.md)，公式与测试追溯分别见[八模块计算规格](docs/EXPANDED_MODULES_CALCULATION_SPEC.md)和[八模块公式测试矩阵](docs/EXPANDED_FORMULA_TEST_MATRIX.md)。

## 计划技术栈

- FastAPI
- Jinja2
- 原生 JavaScript 与 CSS
- SQLite
- Docker Compose
- 确定性 Python 计算内核

项目不计划在当前阶段引入 React、Vue、Redis、Celery、PostgreSQL 或多 worker 架构。

## 设计原则

1. 工程公式与 Web 路由、数据库访问和 PDF 渲染严格解耦。
2. `calculator.py` 保持纯计算，不依赖网络、数据库、文件系统、时钟或 Web 上下文。
3. 容绳量使用逐层离散模型，不以总体积估算替代。
4. 默认值和经验系数必须注明来源；未确认参数不生成伪精确结果。
5. HTML、PDF、API 和数据库结果来自同一不可变计算快照。
6. 修改公式、单位语义或默认规则时，同步更新计算规格、模型版本和测试。

## 文档导航

| 文档 | 内容 |
|---|---|
| [产品需求](docs/PRD.md) | 产品目标、MVP 范围、输入输出和验收标准 |
| [系统架构](docs/ARCHITECTURE.md) | 分层架构、模块注册、数据流和资源预算 |
| [计算规格](docs/CALCULATION_SPEC.md) | 输入口径、SI 转换、公式、结果分类和警告 |
| [八模块需求基线](docs/MODULE_REQUIREMENTS.md) | 八个受控工作表的需求、边界、依赖和发布门槛 |
| [八模块计算规格](docs/EXPANDED_MODULES_CALCULATION_SPEC.md) | 八模块公式、输入语义、结果和适用限制 |
| [API 规格](docs/API_SPEC.md) | API 端点、请求响应、校验和版本策略 |
| [数据模型](docs/DATA_MODEL.md) | SQLite 表、快照结构和一致性约束 |
| [测试计划](docs/TEST_PLAN.md) | 金样、边界、性质、API、PDF 和资源测试 |
| [首发模块公式测试矩阵](docs/FORMULA_TEST_MATRIX.md) | `winch_drum` 37 个公式 ID 的正常、边界和不可计算证据 |
| [八模块公式测试矩阵](docs/EXPANDED_FORMULA_TEST_MATRIX.md) | 八模块公式 ID、金样和自动化证据 |
| [发布门禁](docs/ENGINEERING_CONFIRMATIONS.md) | 状态化的机械、产品、软件和质量安全门禁 |
| [部署设计](docs/DEPLOYMENT.md) | 单 worker 部署、资源限制、备份和恢复 |
| [实施任务](TASKS.md) | 分阶段任务、出口门禁和待确认事项 |

## 当前进度

- [x] Phase 0：形成设计与决策基线。
- [x] Phase 1：工程骨架与本地单 worker 资源基线完成。
- [x] Phase 2：完成计算、校验、中文界面和逐公式自动化验证。
- [x] Phase 3：实现同源 HTML/PDF 报告及低资源部署候选。
- [x] Phase 4：完成目标主机回环部署、监测、备份恢复和软件验收。
- [x] Phase 5：完成平台主页、注册表驱动的模块入口和后续模块目录预留。
- [x] Phase 6：完成差异化品牌、SEO/爬虫基础、HTML 404、HEAD 探针、公网反向代理和 D/d 高风险校核。
- [x] Phase 7：完成八个受控工程工作表的软件实现、注册、统一页面/API/快照/HTML/PDF 接入和本地回归。
- [x] Phase 8：完成九模块产品化目录筛选、CSP-safe API 文档、安全/缓存响应头、发布状态快照治理及旧报告兼容边界。
- [ ] Phase 7 工程门禁：逐模块确认标准版本、项目系数、制造商候选数据、独立复算和机械审核，再逐项提升发布状态。
- [ ] Phase 8 部署门禁：备份目标库、应用迁移 `005`，再完成九模块候选版的目标机功能、资源、恢复与既有服务影响复验。
- [ ] 公网门禁：由域名主体完成或确认腾讯云 ICP 首次备案、接入备案或新增服务，再复测国内外 HTTPS、搜索引擎抓取和外部监控。

具体完成状态以 [TASKS.md](TASKS.md) 为准。

## 公网部署状态

- 应用容器只绑定宿主机 `127.0.0.1:18080`，由 Caddy 终止 TLS 并反向代理；不直接暴露应用管理端口。
- Caddy 已配置 3 秒上游连接窗口、10 秒响应头超时和友好 `503`，服务器本机通过 SNI 访问返回 HTTP/2 `200`。
- DNS 当前只有 A 记录，没有错误 AAAA；应用提供 canonical、Open Graph、favicon、`robots.txt`、`sitemap.xml`、HEAD 和 HTML 404。
- 外部请求仍被云平台域名访问门禁拦截：HTTP 被改写到腾讯云 webblock 页面，HTTPS 在 ClientHello/SNI 后被复位。完成 ICP 备案或接入前，不能把本机健康检查等同于公网可访问。
- 公网诊断、回滚点和后续备案复测要求见[部署设计](docs/DEPLOYMENT.md)。

## 开发与验证状态

项目需要 Python 3.12+。Windows 本地开发环境可按以下方式建立：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

启动单 worker 本地服务：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --workers 1 --host 127.0.0.1 --port 8000
```

执行格式、静态检查和测试：

```powershell
.\.venv\Scripts\python.exe -m ruff format --check app scripts tests
.\.venv\Scripts\python.exe -m ruff check .
node --check app/static/calculator.js
node --check app/static/engineering-calculator.js
node --check app/static/home-animation.js
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前已实现：

- Pydantic 输入校验和显示单位到 SI 的显式转换；
- 逐层绳中心线螺旋容绳计算；
- 用户给定尺寸校核，以及采用批准 D/d 或显式项目初选 D/d 时的有限候选搜索；
- 实际第一层绳中心直径 D/d 低于当前最小值时，返回实际比值、要求直径和建议最小芯径的高风险警告；
- 功率、转速、参考速比、静态制动力矩、计算步骤和警告代码；
- 显式模块注册、统一 schema/计算/快照 API 和健康端点；
- 九个已注册模块的独立 Pydantic 输入、确定性计算内核、来源状态、警告与模型版本；
- 面向实际试用的产品主页、统一 `/modules/{module_id}` 页面入口，以及按模块名称/说明/能力搜索和按分类筛选的九模块目录；
- 八模块通用受控工作台，可显式载入非推荐验证算例，并从同一快照读取 API、HTML 与 PDF；
- `/docs` 与 `/redoc` 提供服务端渲染、无内联脚本且无需第三方 CDN 的 CSP-safe API 参考，并从当前 OpenAPI schema 生成端点列表；
- 全站使用无外部依赖的系统字体栈，统一标题、正文、工程数字、表单、卡片和报告的字号层级与阅读节奏；
- SQLite WAL、外键、忙等待、`001`～`005` 有序迁移、在线备份和错误回滚；迁移 `005` 以可空列保存计算时发布状态并兼容旧记录；
- 新计算写入 snapshot schema v4 与 report context schema v4，从已保存报告 DTO 渲染同源 HTML/PDF 报告；
- PDF 串行限流、超时隔离、原子落盘、SHA-256、大小与总容量保护；
- 固定 ReportLab、Noto Sans SC 字体/许可及报告模板版本（`winch_drum.report.1.2.1`，八模块各为 `*.report.1.0.1`）；
- 启动时验证报告目录/临时目录可写和固定字体可用；`/health/ready` 仅做注册表、迁移表与报告运行目录的浅层就绪检查，不执行完整 SQLite 完整性检查或 PDF 渲染；
- 应用统一返回 CSP、点击劫持、MIME 嗅探、来源与权限安全头；计算/报告响应 `no-store`，静态资源可缓存一天，其余页面 `no-cache`；
- 旧库中发布状态为空的记录读取为 `legacy_unknown`：HTML 仍按内部测试边界展示；经路径、大小和 SHA-256 校验的旧缓存 PDF 仍可下载并带遗留告警，未缓存或缓存失效的旧 PDF 不允许用当前状态重建并返回 `409 LEGACY_RELEASE_STATUS_MISSING`；
- 非 root、只读根文件系统、单 worker、回环端口和资源限制的 Docker Compose 候选；
- 带字段帮助、来源状态、高等级警告、结果等级和逐层表的中文计算页面；右侧等待、计算中和结果状态互斥，计算完成后不会残留等待提示；
- 结果页明确区分“当前方案不可行”“参数存在高风险”和待校核项，不将局部容量满足表述为整机合格；
- 差异化品牌、首页工程定位、canonical、Open Graph、favicon、`robots.txt`、`sitemap.xml`、HEAD 和 HTML 404；
- 绳索、载荷和环境记录采用中文默认值及可自定义的中文备选词库；
- 报告提供返回计算页与 PDF 下载入口，字段/等级/来源中文展示，公式按表达式、代入值和结果分层呈现；
- `winch_drum` 37 个公式 ID 的可追溯测试矩阵，以及八模块独立公式矩阵；
- 当前候选版 126 项本地回归全部通过，覆盖金样、边界、派生数值安全、公式库存防漂移、产品目录、API 文档、安全头、受控 500 错误页、schema v4、迁移 `005`、旧报告兼容、数据库、PDF 和模块契约。

本地资源基线：1000 次计算无错误，计算 p95 30.489 ms；连续 20 份 PDF 无错误，p95 594.880 ms；5 个并发 PDF 请求为 1 个成功、4 个受控 `429`；父进程与渲染子进程合计峰值 RSS 149,626,880 B，结束后无临时文件。

目标 Docker 主机基线：1000 次计算 p95 23.895 ms，20 份 PDF p95 1.108 s，5 并发仍为 1×`200` + 4×`429`；Web cgroup 峰值 186,097,664 B、交换区 0、无 OOM/重启，在线备份与隔离恢复通过。完整证据见 [Phase 4 验收记录](docs/PHASE4_ACCEPTANCE.md)。

以上目标机基线来自既有 `winch_drum` 部署，不代表当前九模块候选版已经远程部署或完成目标机资源复验。当前候选版新增可空迁移 `005_calculation_release_status.sql`，部署前必须先做 SQLite 在线备份并受控应用迁移；没有新增常驻服务，工程公式与计算模型版本未改变。

## 免责声明

本项目输出仅用于机械方案计算、比较和初步选型，不替代适用标准核查、结构强度与安全校核、制造商确认、设计审批或具备资质的工程师签字。任何带有 `preliminary`、`review_required` 或“待确认”标记的参数，均不得直接作为制造、采购或安全决策依据。
