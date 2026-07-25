# 部署设计

文档版本：0.5.0

目标：腾讯云 Ubuntu 24.04.4 LTS，2 核、1.9 GB 内存、约 10 GB Swap、50 GB 系统盘
状态：Phase 4 首发模块目标机回环部署、容器实测和恢复演练已通过；公共 Caddy 代理与 TLS 已配置，域名在中国大陆服务器上的备案/接入状态仍须在腾讯云控制台关闭门禁。当前 Phase 8 九模块候选版及迁移 `005_calculation_release_status.sql` 仅完成本地实现与回归，未执行远程部署、数据库迁移或目标机资源复验。

## 1. 部署边界

- 使用一个 Docker Compose 项目，只包含一个 Web 服务；SQLite 是文件，不另起数据库容器。
- Web 固定运行一个 worker：`python -m uvicorn app.main:app --workers 1 --host 0.0.0.0 --port 8000`。
- 默认只绑定宿主机 `127.0.0.1` 的未占用高位端口，由现有反向代理按独立域名/路径转发；上线前必须盘点端口、网络、磁盘和现有 Compose 项目。
- 不修改青龙、OpenClaw、Mihomo 或其他容器的网络、端口、卷、重启策略和配置。
- 不把约 10 GB Swap 当作可用应用内存；Swap 只用于突发保护，持续换页视为容量失败。
- 九模块仍复用同一 FastAPI 单 worker、SQLite 和受限 PDF 子进程。当前候选版新增一个通用可空迁移 `005_calculation_release_status.sql`，没有新增数据库服务、消息队列或其他常驻服务，也没有改变工程公式或计算模型版本。

## 2. 容器与目录

默认宿主机专用目录（实际路径在目标机只读盘点后确认）：

```text
/opt/mechanical-selector/
  compose.yaml
  .env                 # 0600，不进版本库
  data/app.sqlite3
  reports/
  backups/
```

镜像内应用只读；长期 Web 容器只挂载 `data`、`reports` 和其中的 `reports/.tmp` 受控临时目录，不挂载 `backups`，因此运行时 Web 无法改写备份。`backups` 只在受控迁移命令的一次性 `docker compose run` 容器中显式以读写 bind mount 挂入。容器使用固定 UID/GID 的非 root 用户；数据库、报告、备份不得放在镜像可写层。应用启动时必须找到固定 Noto Sans SC 字体，并能创建临时目录且完成写入/删除探针；任一失败均拒绝启动。

## 3. Compose 资源策略

`compose.yaml` 已冻结以下候选值；每个新镜像都必须在目标机验证实际生效：

| 项目 | 初始建议 | 说明 |
|---|---:|---|
| Web worker | 1 | 硬约束。 |
| 内存上限 | 512 MiB | 上线前依据 PDF 引擎实测；另设 128 MiB reservation（Compose 支持方式需验证）。 |
| memory+swap 上限 | 512 MiB | 与内存上限相同，容器不得使用 Swap。 |
| CPU 上限 | 1.0 CPU | 给既有服务保留资源。 |
| PID 限制 | 128 | 防止子进程失控；PDF 方案确定后复核。 |
| 请求体 | 1 MiB | 应用已限制；反向代理需配置相同或更小上限。 |
| PDF 并发 | 1 | 进程内信号量；超时 30 s。 |
| 日志 | 10 MiB × 5 | Docker `json-file` 轮转，避免填盘。 |
| 重启 | `unless-stopped` | 配合有退避的 Docker 行为；避免外层重复守护。 |

PDF 使用 ReportLab 子进程，不启动浏览器或常驻 PDF 服务。镜像包含固定 Noto Sans SC 可变字体、OFL 许可和第三方声明；更新字体必须同步更新哈希、视觉样张和模板版本。

## 4. SQLite 配置

- `journal_mode=WAL`、`foreign_keys=ON`、合理 `busy_timeout`；具体值在性能测试后冻结。
- 数据库写事务只覆盖快照落库，不包含计算和 PDF。
- 定期检查 `PRAGMA integrity_check`（频率需确认）并监控主库/WAL 大小。
- 备份使用 SQLite 在线备份 API 或确认过的 `.backup`，禁止在写入时简单复制主文件而遗漏 WAL。
- 部署/迁移前备份；恢复在独立临时目录验证后再切换，保留回滚点。

## 5. 内存控制

- 单进程、单 worker；不预加载大型数据集，不常驻浏览器进程。
- PDF 限并发 1，生成完释放对象并清理临时文件；为单次报告限制表格层数（业务上 `z_max<=100`）。
- 报告图片不使用 base64 大对象；静态资源小型化，避免在请求中复制 PDF 多份。
- 设置容器内存上限并监控 OOMKilled、RSS、主机 MemAvailable、Swap in/out。
- 压测需与现有服务基线对比；若余量不足，默认关闭 PDF 或降低容器上限/访问频率，而非挤占现有服务。

## 6. 磁盘控制

- Docker 日志轮转；应用日志只输出结构化摘要，不打印完整快照。
- 报告采用内容/记录 ID 管理，生成失败的临时文件及时清理。
- 项目持久化容量上限 5 GiB；达到 85% 停止新 PDF，但仍允许计算和读取已有报告。
- 先清理可再生 PDF，再考虑历史计算；MVP 默认不自动删除计算快照。
- 备份需有上限与轮换策略。初始候选为每日 7 份 + 每周 4 份，但必须根据实际数据增速和恢复目标确认。
- 监控系统盘剩余空间；建议剩余低于 5 GiB 或 15%（取较大者）时停止 PDF/备份写入并报警，阈值上线前结合现有服务确认。

## 7. 网络、安全和秘密

- 仅反向代理对外；应用端口绑定回环地址。复用现有代理前先只读确认配置，不覆盖。
- HTTPS、请求大小、基础限流和安全头由代理与应用共同落实。
- 应用冻结返回同源 CSP、`nosniff`、`no-referrer`、`DENY` frame policy 和最小权限策略；`DESIGN_AGENT_PUBLIC_BASE_URL` 为 HTTPS 时返回一年期 HSTS。代理不得放宽这些头。
- 静态资源响应 `public, max-age=86400`；计算/报告路径响应 `no-store` 与 `noindex, nofollow, noarchive`；其他页面/API 响应 `no-cache`。静态资源变更必须同步更新 URL 查询版本。
- 生产环境通过 `.env` 设置 `DESIGN_AGENT_PUBLIC_BASE_URL`，用于 canonical、Open Graph URL、`robots.txt` 和 `sitemap.xml`；仓库不写死实际域名。
- 模块页面只有在 `release_status=released` 后才进入生产 sitemap；`internal_testing` 与 `engineering_review` 页面不得因软件可进入而被标记为工程已发布。
- `.env` 仅保存随机密钥和部署配置，权限 0600；不把秘密写入镜像、仓库或日志。
- 备份目录不属于长期 Web 运行时权限边界；禁止为方便迁移把 `/backups` 重新加入 `web.volumes`，迁移完成后一次性容器和临时挂载必须消失。
- 固定基础镜像摘要/依赖版本，构建时生成依赖清单；定期安全更新需先在预发布回归。
- 容器 `read_only`、`no-new-privileges`、删除不需要的 Linux capabilities；健康检查不暴露内部信息。

## 8. 发布流程

1. 在非生产环境构建固定版本镜像并完成单元、金样、API、PDF 和资源测试；记录镜像 ID/摘要。
2. 盘点目标机 CPU/内存/Swap/磁盘、端口、Docker 网络及既有服务基线；任何冲突先停止发布。
3. 备份数据库和当前 Compose/环境配置；记录镜像摘要、应用版本和模型版本。
4. 新库或已有库都先运行受控迁移命令；已有库必须指定备份目录。当前候选版必须应用到 `005_calculation_release_status.sql`。生产 Web 设置 `DESIGN_AGENT_AUTO_MIGRATE=false`，启动时只接受与镜像迁移清单完全一致的数据库。
5. 启动单个新容器，确认启动日志已通过字体/报告目录写探针，再检查 live/ready、日志、内存、数据库写读和一份受控 PDF。
6. 配置代理路由并小流量验证；观察至少一个约定窗口再完成发布。
7. 失败时恢复旧镜像/配置；数据库发生不兼容迁移时按已演练备份恢复。

不使用会影响其他 Compose 项目的全局清理命令，不执行 `docker system prune`，不复用含义不明的卷或网络。

推荐命令顺序（只操作本项目 Compose）：

```bash
mkdir -p data reports backups
sudo chown -R 10001:10001 data reports backups
docker compose build web
docker compose run --rm --volume "$(pwd)/backups:/backups:rw" web python -m app.persistence.migrate --apply --backup-dir /backups
docker compose run --rm web python -m app.persistence.migrate --check
docker compose up -d web
docker compose ps
curl --fail http://127.0.0.1:${DESIGN_AGENT_BIND_PORT:-18080}/health/live
curl --fail http://127.0.0.1:${DESIGN_AGENT_BIND_PORT:-18080}/health/ready
```

首次新库没有可备份文件；迁移器直接建库。已有非空库若未提供 `--backup-dir` 会拒绝执行。上述 `/backups` bind 只存在于一次性迁移容器；长期 `web` 服务的 Compose 定义不得含该挂载。不得通过临时开启生产自动迁移绕过该门禁。`/health/ready` 只验证关键表/迁移清单、`SELECT 1`、字体及报告目录存在，不执行 `PRAGMA quick_check`、目录写探针或 PDF 试渲染；它不能替代迁移前备份、启动日志检查和功能冒烟。

## 9. 备份与恢复目标（C-08 已确认）

- RPO 24 小时；RTO 4 小时。
- 普通记录保留 90 天、PDF 30 天；每日备份 7 份、每周备份 8 份，长期保留项目不自动删除。
- 项目持久化上限 5 GB：70% 告警，85% 停止新 PDF。
- 系统盘 75% 告警，85% 停止 PDF/上传，90% 停止新增历史，只保留健康检查和清理。
- 单请求 JSON 1 MB、单 PDF 20 MB；日志单文件 10 MB、最多 5 个轮转。自动清理必须留日志。
- 备份范围：SQLite 一致性备份、迁移版本、部署配置（去除秘密）、报告清单；重要 PDF 可选纳入。
- 至少每季度在隔离目录做恢复演练，并核对记录数、抽样 input hash、报告生成和应用 ready。

## 10. 部署验收

- `docker compose config` 可解析，只有一个应用服务和一个 worker。
- `web` 的长期挂载仅包含数据与报告目录，不含 `/backups`；迁移一次性容器退出后无残留容器或备份挂载。
- 容器资源、日志轮转、PID、只读文件系统和回环端口限制可观测生效。
- 目标机峰值测试无 OOM、无持续 Swap 增长，既有服务健康不受影响。
- 数据库在线备份和恢复演练成功；磁盘满、数据库只读、PDF 超时均返回受控错误。
- 数据库迁移清单精确到 `005`；新计算持久化发布状态，迁移前记录读取为 `legacy_unknown`。
- 与旧模板匹配且路径/大小/SHA-256 有效的遗留缓存 PDF 可下载并带 legacy 标记；旧记录没有有效缓存时返回 `409 LEGACY_RELEASE_STATUS_MISSING` 且不启动 PDF 渲染。
- `/docs` 和 `/redoc` 在严格 CSP 下无需 CDN/内联脚本即可阅读；安全头与三类缓存策略逐路由验证。
- 停止/升级本项目不会停止、重建或修改其他容器。

## 11. 本次目标机验收

2026-07-23 已在目标 Ubuntu 24.04.4 LTS 主机完成独立 Compose 回环部署。镜像、迁移、健康检查、关键计算、中文 PDF、1000 次计算/20 份 PDF/5 并发、资源采样、既有服务回归、在线备份和隔离恢复均通过；详见 [`PHASE4_ACCEPTANCE.md`](PHASE4_ACCEPTANCE.md)。该次验收时应用只监听 `127.0.0.1:18080`，未修改现有青龙、Mihomo、OpenClaw，也未配置公共代理。

## 12. 公网代理与可访问性复测

2026-07-24 在用户批准处理外部访问问题后完成：

- DNS 仅有一个 A 记录，没有 AAAA 或 CNAME；80/443 均由 Caddy 监听；
- Caddy 已取得有效的 Let's Encrypt 证书，服务器本机通过 SNI 访问返回 HTTP/2 200；
- 反向代理仍只访问 `127.0.0.1:18080`，增加 3 s 连接窗口、10 s 响应头超时和 503 友好错误；
- 应用补充首页/模块 HEAD、HTML 404、favicon、canonical、Open Graph、`robots.txt` 和 `sitemap.xml`；
- 外部 TCP 抓包显示 ClientHello 到达主机后连接立即被复位，而本机同证书/TLS 链路正常；固定解析到服务器 IP 的 HTTP 请求被腾讯云改写为指向 `dnspod.qcloud.com/static/webblock.html` 的 302。故障位于腾讯云域名访问门禁，不在应用、Caddy 或证书链。必须由域名主体在腾讯云控制台确认并完成 ICP 首次备案、接入备案或新增服务后再做国内外复测。不得通过临时开放不受控端口或绕过备案替代正式处理。

## 13. 当前九模块候选版部署边界

当前候选版包含 `transmission_check`、`gear_drive`、`shaft_bearing`、`lead_screw`、`synchronous_belt`、`motor_drive`、`stepper_motor` 和 `pneumatic_cylinder`，并完成产品主页、CSP-safe 文档、安全/缓存头和发布状态快照治理，但仍只完成本地软件实现：

- 沿用通用 JSON 快照和报告表，不增加模块专属列；新增通用可空迁移 `005_calculation_release_status.sql`；
- 新计算写入 snapshot schema v4 / report context schema v4；报告模板为 `winch_drum.report.1.2.1` 和八模块 `*.report.1.0.1`；
- 沿用同一 Web worker、Jinja2、原生 JavaScript/CSS 和按请求启动的受限 PDF 子进程，没有新增常驻服务；
- 本地 Compose 候选已移除长期 Web 的 `/backups` 挂载；尚未修改目标机上的 Compose、Caddy、青龙、OpenClaw、Mihomo 或其他现有服务；
- 没有构建/推送当前候选版生产镜像，也没有执行远程切换、迁移 `005` 或公网复测；
- Phase 4 的性能与恢复数据是历史有效证据，但不能代表九模块镜像已通过相同资源门禁。

九模块远程部署前，除第 8～10 节流程外，还必须：

1. 确认注册表精确返回 9 个模块及正确 `release_status`，并阻止未放行模块进入 sitemap；
2. 确认长期 Web 仅挂载 data/reports；通过第 8 节的一次性迁移容器临时挂载 backups，对目标库做 SQLite 在线备份，在隔离环境演练 `005` 后受控应用迁移并确认迁移清单完整；
3. 验证迁移前 `winch_drum` 快照 HTML 可读：有效旧缓存 PDF 带 `legacy_unknown` 标记可下载，无有效缓存时稳定返回 409 且不重算；
4. 对九个模块分别完成计算、GET schema v4 快照、HTML 和 PDF 冒烟，确认报告返回对应模块页面和计算时发布状态；
5. 验证首页筛选、CSP-safe `/docs`/`/redoc`、安全头、缓存头、启动报告目录/字体检查及浅层 `/health/ready`；
6. 重跑 1000 次代表性混合计算、20 份混合模块 PDF、5 并发 PDF 和资源采样；
7. 复核数据库/报告容量、备份恢复、临时文件清理以及青龙、Mihomo、OpenClaw 健康状态；
8. 机械门禁未关闭的模块继续保持 `internal_testing` 或 `engineering_review`，不得仅因部署成功提升为 `released`。
