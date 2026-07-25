# Phase 4 目标主机验收记录

日期：2026-07-23

范围：`winch_drum` 软件在目标 Ubuntu 主机上的独立 Docker Compose 回环部署、负载、故障隔离、备份恢复和既有服务回归。本文不构成机械专项计算批准或公共发布授权。

## 1. 部署前盘点

- 主机：Ubuntu 24.04.4 LTS，2 CPU，物理内存 2,063,245,312 B。
- 部署前系统盘使用率 56%，可用 22,385,971,200 B。
- Docker 29.5.1、Docker Compose v5.1.3 可用。
- `127.0.0.1:18080` 未占用，`/opt/mechanical-selector` 不存在。
- 既有青龙容器为 healthy、重启计数 0；Mihomo 与 OpenClaw 进程运行。
- 部署未停止、重建或修改上述既有服务。

## 2. 镜像与运行约束

- 应用镜像 ID：`sha256:ba189f1050329205fdb17db4caee9730f2221ab00e2406260c17cfaa0fb62a43`。
- 镜像大小：73,625,230 B；运行用户：`10001:10001`。
- 单 worker；只读根文件系统；删除全部 Linux capabilities；`no-new-privileges`。
- CPU 上限 1 核，内存上限 512 MiB、预留 128 MiB、容器交换区上限 0，PID 上限 128。
- 端口只映射 `127.0.0.1:18080 -> 8000`。
- Docker 日志轮转 10 MiB × 5。

构建阶段只为本项目单次构建临时使用现有 `127.0.0.1:7890` HTTP 代理；未修改 Mihomo 或 Docker daemon 配置。

## 3. 迁移与功能冒烟

- 当次镜像所含的 `001_initial.sql`～`004_report_context.sql` 全部应用，独立 `--check` 返回 `DATABASE_MIGRATIONS=READY`。这是 2026-07-23 的历史证据，不包含后续 `005_calculation_release_status.sql`。
- `/health/ready` 返回 `{"status":"ready"}`，容器健康状态 healthy、重启 0、OOM false。
- 金样设计拉力为 120000 N；HTML 与 API 模型版本/关键值一致。
- PDF 为 9 页、93,814 B，文件魔数、响应 SHA-256 与下载文件一致；二次请求返回相同二进制。
- PDF 中文标题、`winch_drum.calc.1.1.0`、免责声明和 120000 均可提取。
- 容量不足用例中 full 直径/转速/速比均为 null，只返回 max-layer 对应值。

## 4. 目标容器负载

| 项目 | 结果 |
|---|---:|
| 顺序计算 | 1000 次，0 错误 |
| 计算平均 / p95 | 19.371 / 23.895 ms |
| 顺序 PDF | 20 份，0 错误 |
| PDF 平均 / p95 | 1,088.035 / 1,107.966 ms |
| 5 个并发 PDF | 1×200，4×429 |
| Web cgroup memory peak | 186,097,664 B |
| Web cgroup swap peak | 0 B |
| OOM / 重启 | false / 0 |
| 报告临时文件残留 | 0 |

负载期间 Docker 采样到的 Web 内存峰值约 114,085,069 B；主机最小 `MemAvailable` 为 873,144,320 B。主机 Swap 已被其他长期进程使用，采样窗口内总使用量波动约 10.3 MB，但本项目 cgroup 的 `memory.swap.current` 与 `memory.swap.peak` 均为 0。

## 5. 持久化与恢复

- 负载后主库含 1027 条计算、22 份 ready PDF、0 份 failed PDF。
- 报告临时目录为空。
- SQLite 在线备份大小 67,506,176 B，SHA-256：
  `c9b2c9f035d1c8df519d9c55fea3658bda99fdbfd9a0b4985212e2ffa2c0b640`。
- 将备份复制到隔离、可写恢复目录后，迁移检查为 READY、`quick_check=ok`，并核对出 1027 条计算及 22 份 ready PDF。
- 首次把 WAL 模式备份挂为只读目录时，SQLite 因不能创建共享内存文件而拒绝打开；改用真实恢复所需的隔离可写数据目录后通过。该失败路径未接触生产主库。

## 6. 既有服务与发布边界

- 验收后青龙仍为 healthy、重启计数 0；Mihomo active；OpenClaw 运行。
- 应用保持回环监听，没有公开端口、域名或反向代理变更。
- 软件验收为 `pass`；总状态仍为 `internal_testing`。
- 转为 `released` 仍需关闭钢丝绳、卷筒结构、动态/热制动、电机启动/热容量、正式标准条款与制造商数据等专项校核。
- 如需公网访问，必须另行提供并批准域名、TLS、代理路径和访问控制策略。

当前九模块候选版新增迁移 `005`、snapshot/report context schema v4、报告模板 patch 版本与旧 PDF 兼容策略；这些内容必须在新一轮目标机备份、迁移、冒烟、资源和恢复复验中单独取证，不能引用本文替代。
