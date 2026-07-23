# 系统架构设计

文档版本：0.1.0  
适用阶段：Phase 0 设计；指导 Phase 1 实现

## 1. 架构目标与约束

系统部署在 2 核、1.9 GB 内存的 Ubuntu 24.04.4 LTS 主机，与现有服务共存。首版采用单 FastAPI Web 进程、Jinja2、原生 JavaScript/CSS 和 SQLite；不引入前端构建链、消息队列、缓存服务或独立数据库服务。计算必须确定、可复现、可版本化。

## 2. 逻辑架构

```text
浏览器
  └─ HTTP/HTML/JSON
      └─ FastAPI 单 worker
          ├─ Web 层：页面、静态资源、安全头、错误页
          ├─ API 层：模块发现、校验、计算、报告查询
          ├─ 应用服务：SI 规范化、计算编排、快照保存、报告编排
          ├─ 模块注册表
          │   ├─ winch_drum@1.x（方案 A）
          │   └─ future: transmission_check@1.x（方案 B）
          ├─ 确定性计算内核（纯 Python，无网络/无数据库副作用）
          ├─ Jinja2 HTML 报告 + 受限 PDF 渲染适配器
          └─ SQLite + 本地受控报告目录
```

边界原则：路由不包含工程公式；计算内核不访问数据库、文件、网络、时钟或大模型；保存成功后报告只读取快照，不重新执行计算。

## 3. 建议代码结构（Phase 1）

```text
app/
  main.py
  core/             # 配置、错误、单位、精度、版本、注册表
  web/              # HTML 路由、API 路由、依赖、安全
  services/         # calculate、snapshot、report
  modules/
    base.py         # 模块协议
    winch_drum/
      module.py
      schemas.py
      calculator.py
      warnings.py
      report.py
      formulas.py
  persistence/      # SQLite repositories、迁移
  templates/
  static/
tests/
docs/
data/
reports/
```

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

注册表在应用启动时显式导入允许的模块并检查 ID 唯一、版本存在及契约完整。不得扫描和执行用户上传代码。核心路由只依赖协议，通过 `module_id` 查找实现。

### 4.1 方案 B 接入

方案 B 建议使用 `module_id=transmission_check`，拥有独立输入/结果 schema、公式目录、警告和报告片段。它复用单位、快照、API、报告外壳和测试契约，不复用方案 A 的业务模型。若未来需要“方案 A 结果传入方案 B”，应通过显式、版本化的 DTO 和用户确认完成，禁止直接读另一模块内部表或 Python 对象。

接入步骤：实现协议 → 注册模块 → 增加数据库 schema 标识但不加专属结果列 → 契约测试 → API/HTML 自动发现 → 独立工程审核 → 发布新模型版本。

## 5. 请求与数据流

1. API/表单接收原始值和显示单位。
2. Pydantic 执行类型、有限数、长度和基础范围校验。
3. 模块执行跨字段校验，区分阻断错误与警告。
4. 单位层转换为 SI，并记录换算因子。
5. `calculate()` 产生全精度结果、逐步公式记录和结果分类。
6. 警告引擎追加稳定代码；应用层组装不可变快照。
7. 一个短事务保存计算主记录与 JSON 快照。
8. 返回 JSON 或渲染 HTML。PDF 请求从快照构建，限并发 1，采用临时文件后原子改名。

## 6. 精度、版本与确定性

- 内核使用 Python `Decimal` 或经测试的 IEEE-754 float；Phase 1 必须择一并在模型版本中冻结。建议几何与功率使用 float、比较采用明确容差，持久化保留足够有效位；不得对中间结果作展示舍入。
- 展示舍入集中在报告格式层；JSON 可同时返回 raw value 和 formatted value。
- 变更公式、单位语义、默认值、边界、舍入前算法或警告判定时，递增 `calculation_model_version`。
- 仅修改文案/样式且数值语义不变，可只递增应用版本。
- 老快照始终保留原版本；不得后台静默重算。

## 7. SQLite 与并发

- 单 Web worker，避免多进程内存复制与 SQLite 写争用。
- 启用 WAL、foreign keys、busy timeout；事务短小，计算和 PDF 渲染不放在事务内。
- 每请求独立连接/会话；失败回滚。
- PDF 通过进程内 `Semaphore(1)` 限制并发。单 worker 重启后不承诺排队任务恢复；MVP 使用同步、受超时保护的生成方式。
- 不将大型 PDF 二进制写入 SQLite，只保存相对路径、哈希、大小和状态。

## 8. 安全与故障隔离

- 限制请求体、字段长度、数值范围和报告生成频率；拒绝 NaN/Infinity。
- Jinja2 自动转义；富文本不接受用户 HTML；下载使用数据库 ID 映射，禁止路径拼接。
- 设置 CSP、`X-Content-Type-Options`、`Referrer-Policy`；生产环境 HTTPS 由既有反向代理终止。
- 容器使用非 root 用户、只读应用文件系统（数据/报告/临时目录单独可写）、最小镜像和固定依赖版本。
- 不暴露 SQLite 与管理端口；Docker Compose 不接管或修改现有服务网络，端口默认仅绑定 `127.0.0.1`。
- 健康检查只做轻量进程/数据库可访问检查，不触发计算或 PDF。

## 9. 可观测性

- 结构化日志字段：request_id、module_id、model_version、duration_ms、status、warning_count；不记录完整用户输入。
- 指标可先从日志获得：请求量、错误率、计算延迟、PDF 延迟、数据库大小、报告目录大小和磁盘余量。
- `/health/live` 只确认进程；`/health/ready` 检查注册表和 SQLite 可执行轻量查询。

## 10. 资源预算

建议初始限制（上线前以压测调整）：Web 容器内存上限 512 MiB、预留 128 MiB；CPU 上限 1 核；单 worker；PDF 并发 1、超时 30 s；请求体上限 256 KiB。Docker JSON 日志每文件 10 MiB、最多 3 个。报告保留期与总容量需确认，默认设计目标为 500 MiB 软上限。应用不主动占用 Swap 作为容量设计的一部分。

资源超限时优先拒绝/延迟 PDF，不影响计算页面与同机服务。任何上限都必须在目标主机上结合现有服务基线复核。

## 11. 架构验收

- 用契约测试证明第二模块可注册且无需更改核心计算路由。
- 用相同快照重复生成 HTML/PDF，关键字段一致。
- 并发触发多个 PDF 时实际同时渲染数不超过 1。
- 容器限制生效；压力测试期间主机可用内存和现有服务健康无明显恶化。
- SQLite 备份、恢复、WAL 清理和磁盘不足故障均有演练记录。
