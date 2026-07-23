# 机械智选（Design Agent）

面向机械设计人员的轻量级、可审计计算与初选平台。项目使用确定性 Python 代码执行工程计算，保留输入、单位换算、公式步骤、模型版本、假设、警告与报告，帮助工程师进行方案比较和初步选型。

> 当前状态：**C-01～C-09 决策已进入模型 `winch_drum.calc.1.1.0`**。纯计算核心、FastAPI/Jinja2、SQLite 快照、中文页面、同源 HTML/PDF 报告以及目标 Docker 主机的回环部署、负载和恢复门禁均已完成。专项机械校核与公共代理/域名未批准，因此发布状态保持 `internal_testing`。

## 项目目标

- 使用可追溯、可重复的确定性计算，避免不可解释的工程结论。
- 内部统一采用 SI 单位，显示层负责单位转换。
- 明确区分理论计算、工程初选、建议结果和待人工校核项。
- 通过模块注册机制扩展新的机械计算工具，业务计算与 Web、数据库和报告渲染解耦。
- 在 2 核 CPU、1.9 GB 内存的服务器上以单 Web worker 低资源运行。

## 首发模块：`winch_drum`

首发模块面向绞车与卷筒的初步计算，规划范围包括：

- 设计拉力、理论负载功率和最低所需电机功率；
- 卷筒芯径、排绳节距和可用宽度；
- 按层离散的容绳量与部分末层计算；
- 空卷/满卷工作直径、卷筒转速和参考减速比；
- 静态保持制动力矩参考值；
- 输入、公式、假设、警告、模型版本及报告快照。

本模块不覆盖钢丝绳强度、卷筒结构强度、疲劳寿命、动态冲击、热平衡、排绳质量、品牌型号数据库或采购级自动选型。完整边界见[计算规格](docs/CALCULATION_SPEC.md)。

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
| [API 规格](docs/API_SPEC.md) | API 端点、请求响应、校验和版本策略 |
| [数据模型](docs/DATA_MODEL.md) | SQLite 表、快照结构和一致性约束 |
| [测试计划](docs/TEST_PLAN.md) | 金样、边界、性质、API、PDF 和资源测试 |
| [公式测试矩阵](docs/FORMULA_TEST_MATRIX.md) | 37 个公式 ID 的正常、边界和不可计算证据 |
| [发布门禁](docs/ENGINEERING_CONFIRMATIONS.md) | 状态化的机械、产品、软件和质量安全门禁 |
| [部署设计](docs/DEPLOYMENT.md) | 单 worker 部署、资源限制、备份和恢复 |
| [实施任务](TASKS.md) | 分阶段任务、出口门禁和待确认事项 |

## 当前进度

- [x] Phase 0：形成设计与决策基线。
- [x] Phase 1：工程骨架与本地单 worker 资源基线完成。
- [x] Phase 2：完成计算、校验、中文界面和逐公式自动化验证。
- [x] Phase 3：实现同源 HTML/PDF 报告及低资源部署候选。
- [x] Phase 4：完成目标主机回环部署、监测、备份恢复和软件验收。

具体完成状态以 [TASKS.md](TASKS.md) 为准。

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
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前已实现：

- Pydantic 输入校验和显示单位到 SI 的显式转换；
- 逐层绳中心线螺旋容绳计算；
- 用户给定尺寸校核，以及采用批准 D/d 或显式项目初选 D/d 时的有限候选搜索；
- 功率、转速、参考速比、静态制动力矩、计算步骤和警告代码；
- 显式模块注册、统一 schema/计算/快照 API 和健康端点；
- SQLite WAL、外键、忙等待、迁移、在线备份和错误回滚；
- 从已保存报告 DTO 渲染的同源 HTML/PDF 报告；
- PDF 串行限流、超时隔离、原子落盘、SHA-256、大小与总容量保护；
- 固定 ReportLab、Noto Sans SC 字体/许可及报告模板版本；
- 非 root、只读根文件系统、单 worker、回环端口和资源限制的 Docker Compose 候选；
- 带字段帮助、来源状态、高等级警告、结果等级和逐层表的中文计算页面；
- 37 个公式 ID 的可追溯测试矩阵；
- 共 70 项金样、边界、容量、单位、重复性、API、页面、数据库、PDF 和模块契约测试。

本地资源基线：1000 次计算无错误，计算 p95 30.489 ms；连续 20 份 PDF 无错误，p95 594.880 ms；5 个并发 PDF 请求为 1 个成功、4 个受控 `429`；父进程与渲染子进程合计峰值 RSS 149,626,880 B，结束后无临时文件。

目标 Docker 主机基线：1000 次计算 p95 23.895 ms，20 份 PDF p95 1.108 s，5 并发仍为 1×`200` + 4×`429`；Web cgroup 峰值 186,097,664 B、交换区 0、无 OOM/重启，在线备份与隔离恢复通过。完整证据见 [Phase 4 验收记录](docs/PHASE4_ACCEPTANCE.md)。

## 免责声明

本项目输出仅用于机械方案计算、比较和初步选型，不替代适用标准核查、结构强度与安全校核、制造商确认、设计审批或具备资质的工程师签字。任何带有 `preliminary`、`review_required` 或“待确认”标记的参数，均不得直接作为制造、采购或安全决策依据。
