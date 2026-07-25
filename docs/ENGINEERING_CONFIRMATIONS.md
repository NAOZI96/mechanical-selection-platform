# 状态化发布门禁

本文件只记录状态及通过条件，不记录个人信息或进度日期。

## 当前状态

- `winch_drum` 工程发布状态：`engineering_review`
- 八个扩展模块工程发布状态：`internal_testing`
- 机械计算审核：`conditional_pass`（仅适用于已完成条件审核的首发模块范围）
- 产品范围确认：`confirmed`
- 首发模块软件验收：`pass`（本地与目标 Docker 主机的功能、报告、资源、备份和恢复门禁通过）
- Phase 8 软件验收：`local_pass`（九模块产品界面/API/schema v4/HTML/PDF/旧数据兼容已实现，125 项本地回归已通过）
- 当前九模块候选版远程部署：`not_deployed`
- 质量与安全发布：`internal_only`
- 总发布状态：`internal_testing`

## 转为 released 的必要条件

`winch_drum` 机械计算必须与 `CALCULATION_SPEC.md` 一致，单位、滑轮倍率、第一层中心直径 D/d、死圈/工作绳长、实际槽数优先和两个系数的单次作用均通过独立复算。八个扩展模块必须与 [`MODULE_REQUIREMENTS.md`](MODULE_REQUIREMENTS.md)、[`EXPANDED_MODULES_CALCULATION_SPEC.md`](EXPANDED_MODULES_CALCULATION_SPEC.md) 和 [`EXPANDED_FORMULA_TEST_MATRIX.md`](EXPANDED_FORMULA_TEST_MATRIX.md) 一致，并分别关闭参数、标准、制造商数据和专项校核门禁。

所有模块的软件必须通过单元、边界、公式回归、API、同源 HTML/PDF、重复一致、持久化恢复、非法输入和 PDF 失败隔离测试。公开试用还要求九模块版本完成目标主机备份恢复、日志轮转、磁盘阈值、密钥检查、网络暴露检查、资源复验及至少一组独立人工复算。软件计算成功、生成报告或部署成功均不会自动提升工程发布状态。

## 八模块专项门禁

| 模块 | 当前状态 | 提升状态前必须关闭 |
|---|---|---|
| `transmission_check` | `internal_testing` | 各级速比/效率来源、额定与峰值边界、反驱/热容量适用性、独立机械复算 |
| `gear_drive` | `internal_testing` | 齿形/精度/材料/润滑、齿根与接触强度、正式标准条款、制造商校核 |
| `shaft_bearing` | `internal_testing` | 轴承 X/Y/p 和额定数据、可靠度/润滑/载荷谱、轴疲劳/挠度/临界转速/应力集中 |
| `lead_screw` | `internal_testing` | 螺纹型式、摩擦/支承/材料来源、螺纹强度/磨损/临界转速、供应商确认 |
| `synchronous_belt` | `internal_testing` | 制造商手册版本、带型/带宽/修正系数、张紧/寿命/轴载荷 |
| `motor_drive` | `internal_testing` | 加减速惯量、启动/峰值/热容量、工作制、供电与制造商完整曲线 |
| `stepper_motor` | `internal_testing` | 惯性加速传动损耗口径、完整转矩速度曲线、驱动器/电压、共振/失步裕量、热与定位精度 |
| `pneumatic_cylinder` | `internal_testing` | 摩擦/压降/缓冲/速度、安装/侧载/屈曲、阀管路、制造商额定值 |

## 全平台尚未关闭的门禁

- `winch_drum`：钢丝绳强度与寿命、绳端固定结构、卷筒结构、动态/应急制动与热容量、电机启动/惯量/热容量、环境适应性、正式标准版本与条款、制造商产品数据。
- 八模块：上表列出的逐模块工程证据、独立审核金样和适用范围签署。
- 软件/运维：目标库在线备份与迁移 `005`、九模块版本目标主机资源、备份恢复、遗留 PDF 缓存、PDF 并发和既有服务影响复验。
- 公网：ICP 首次备案/接入或新增服务关闭后，重新验证国内外 HTTPS、搜索引擎抓取和外部监控。

当前候选版新增可空迁移 `005_calculation_release_status.sql`，但没有新增常驻服务或改变工程公式，也没有执行远程部署。既有 Phase 4 验收仅证明当时采用迁移 `001`～`004` 的首发模块镜像，不能被解释为迁移 `005` 或当前九模块候选版已经远程放行。
