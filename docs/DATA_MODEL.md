# 数据模型设计

## C-08/C-09 冻结补充（snapshot schema v4 / report context schema v4）

输入新增/确认拉力与速度位置、拉力类型、滑轮倍率/效率、实际槽距/槽数、死圈、安装预留、绳型/结构/材料、载荷谱、D/d、环境、制动轴/反向效率、工作制/启动次数/供电和功率系列。`dead_wrap_count` 兼容读取旧名 `dead_wraps`。

`source_status` 固定为 `project_default|user_input|standard_confirmed|manufacturer_data|pending_confirmation`。快照保存原始输入、SI 输入、未舍入结果、警告、假设、公式步骤、计算模型版本、报告模板版本、计算时工程发布状态、持久化报告上下文和生成时间；展示值不是权威存储。

警告包含 `code`、`severity`（`info|warning|high|blocking`）、`title`、`message`、`affected_result`、`recommended_action`。发布门禁只存状态：机械计算、产品范围、软件验收、质量安全和总发布状态；不存人员姓名或计划/实际日期。

Phase 7 的 8 个扩展模块复用完全相同的通用表和版本化 JSON 快照，不增加模块专属列。Phase 8 通过通用迁移 `005_calculation_release_status.sql` 增加可空发布状态列：新计算冻结注册表中的当次状态，迁移前旧记录保留 `NULL` 并读取为 `legacy_unknown`，不得按当前注册表回填。

文档版本：0.5.0
数据库：SQLite  
原则：通用元数据列 + 版本化 JSON 快照，不为每个模块不断增加业务列

## 1. 实体关系

```text
calculation
  1 ─── 0..N report_artifact
  1 ─── 0..N audit_event（MVP 可选）
```

模块目录及当前 `internal_testing|engineering_review|released` 状态来自代码注册表，不作为可在线编辑的数据库配置，避免数据库与已部署代码版本漂移。每次成功计算另将当次状态冻结到通用计算记录和报告上下文。当前注册表为 `winch_drum` 加 8 个扩展模块；注册数量变化本身不要求数据库迁移。

## 2. `calculations` 表

| 列 | SQLite 类型 | 约束/索引 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | UUID。 |
| `module_id` | TEXT | NOT NULL, index | 如 `winch_drum`、`transmission_check`、`gear_drive`；由保存时注册模块决定。 |
| `module_version` | TEXT | NOT NULL | SemVer 字符串。 |
| `calculation_model_version` | TEXT | NOT NULL, index | 如 `winch_drum.calc.1.2.0`。 |
| `release_status` | TEXT | NULL, CHECK | 迁移 `005` 新增；新记录为 `internal_testing` / `engineering_review` / `released`，旧记录允许 `NULL` 并在读取层映射为 `legacy_unknown`。 |
| `status` | TEXT | NOT NULL, CHECK | `completed` / `completed_with_warnings`。校验失败不建成功记录。 |
| `input_original_json` | TEXT | NOT NULL | 原始值、显示单位和用户语义选择。 |
| `input_si_json` | TEXT | NOT NULL | 规范化 SI 输入。 |
| `assumptions_json` | TEXT | NOT NULL | 默认值、来源和人工确认状态。 |
| `results_json` | TEXT | NOT NULL | 未格式化结果、单位、等级、公式 ID。 |
| `steps_json` | TEXT | NOT NULL | 公式文本、符号、SI 代入值、顺序和未舍入结果。 |
| `warnings_json` | TEXT | NOT NULL | 稳定代码、严重度、消息、影响字段。 |
| `disclaimer_json` | TEXT | NOT NULL | 本次快照采用的免责声明；旧记录读取时不得替换为当前文案。 |
| `report_template_version` | TEXT | NOT NULL | 生成报告上下文时采用的模板版本。 |
| `report_context_json` | TEXT | NULL | 计算时物化的报告 DTO；旧迁移记录允许为空并由兼容读取路径映射。 |
| `snapshot_schema_version` | INTEGER | NOT NULL | JSON 快照结构版本；当前写入 4。 |
| `input_hash` | TEXT | NOT NULL | 规范化输入 + 模型版本的 SHA-256，用于诊断/可选去重。 |
| `created_at` | TEXT | NOT NULL, index | UTC ISO 8601。 |
| `request_id` | TEXT | NOT NULL | 日志关联。 |

不保存“当前默认值引用”来替代快照；所有实际采用值和来源都必须写进本次记录。JSON 序列化需稳定定义键顺序/数值策略，以便哈希和回归比较。

当前新写入的报告上下文 `schema_version=4`。该版本在权威原始值之外物化计算时的 `release_status`/中文标签、字段标签、状态/等级/来源展示文本，以及公式的表达式、代入值、结果分层展示字段；这些展示字段不得反向参与工程计算。旧报告上下文仍按其保存的模板版本读取，缺少发布状态时按 `legacy_unknown` 展示。

## 3. `report_artifacts` 表

| 列 | SQLite 类型 | 约束/索引 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | UUID。 |
| `calculation_id` | TEXT | FK, NOT NULL, index | 引用 `calculations.id`，删除策略需确认，建议 RESTRICT。 |
| `format` | TEXT | CHECK | `pdf`；HTML 默认动态渲染，不落文件。 |
| `status` | TEXT | CHECK | `generating` / `ready` / `failed`。 |
| `template_version` | TEXT | NOT NULL | 报告模板版本。 |
| `relative_path` | TEXT | NULL | 仅服务端生成的相对路径。 |
| `sha256` | TEXT | NULL | 完成文件哈希。 |
| `size_bytes` | INTEGER | NULL | 大小，`>=0`。 |
| `created_at` | TEXT | NOT NULL | UTC。 |
| `completed_at` | TEXT | NULL | UTC。 |
| `error_code` | TEXT | NULL | 受控错误代码，不保存敏感堆栈。 |

唯一性约束：`(calculation_id, format, template_version)`；生成使用临时文件和原子改名，只有 `ready` 可下载。数据库触发器保证 `ready` 状态的 path、hash、size、completed_at 均非空。

## 4. 可选 `audit_events` 表

MVP 无账户体系时可暂缓。若保留，只记录事件类型、对象 ID、UTC 时间、request ID 和最少元数据；不记录完整输入副本。事件包括 `calculation_created`、`report_generated`、`report_failed`。

## 5. JSON 快照结构

### 5.1 输入

```json
{
  "rated_line_pull_kn": {"value": 100, "unit": "kN"},
  "drum_core_diameter_mm": {"value": 400, "unit": "mm", "source": "user"}
}
```

SI 快照用明确单位，例如 `rated_line_pull_n`、`rope_diameter_m`。可选未知值使用 JSON `null`，禁止空字符串、0 或缺省含糊表达。

八个扩展模块还保存 `basis_source_status`、`basis_reference` 及适用时的候选数据来源/引用。各模块输入字段不同，但都写入 `input_original_json` 和 `input_si_json`，不建立模块专属表。验证算例只是用户显式载入的普通输入，不作为数据库默认值。

### 5.2 结果

```json
{
  "minimum_motor_power_w": {
    "value": 28235.29411764706,
    "unit": "W",
    "classification": "calculated",
    "formula_ids": ["POWER-002"]
  }
}
```

逐层数组中的每层保存层号、工作直径、每圈长度、完整/使用圈数、毛/可用/累计容量。展示字符串不作为数值真源。

扩展模块结果同样使用带 `value`、`unit`、`classification`、`formula_ids` 和可选 `reason` 的标量对象；模块专属结果保存在 `results_json`，不可计算结论使用 `value=null` 且分类为 `review_required`。只有 `winch_drum` 需要逐层容量数组。

### 5.3 假设与确认

每项建议结构：`key`、`value`、`unit`、`source_type`（user/project/standard/supplier/system）、`source_reference`、`confirmation_status`、`note`。未确认的经验/安全参数不得标记为系统默认。

## 6. 一致性与约束

- 写入前验证 JSON 可序列化且满足对应版本 schema；读取时按 `snapshot_schema_version` 解析。
- `status=completed` 时不得有 high 警告；有任何警告时使用 `completed_with_warnings`。
- 所有 `review_required` 结果必须为 `value=null` 并有原因。
- `report_artifacts.status=ready` 时 path、hash、size、completed_at 均非空。
- 数据库时间统一 UTC，报告按配置显示时区并标注。
- 数据库级 CHECK 覆盖有限的状态约束；复杂工程约束由应用层验证和测试覆盖。

## 7. 迁移、保留与恢复

- 使用轻量迁移工具或有序 SQL 迁移；生产设置 `DESIGN_AGENT_AUTO_MIGRATE=false`，启动只做完整迁移/数据库就绪检查，不在未经备份的生产库上自动迁移。
- 迁移前执行 SQLite 在线备份并记录应用/模型版本；恢复演练包含主库、WAL/SHM 处理和文件权限。
- 当前不自动删除计算记录或 PDF；项目持久化容量上限 5 GiB，达到 85% 后停止生成新 PDF。若未来启用按期清理，必须先冻结策略并优先删除可再生 PDF。
- 备份至少包含 SQLite 一致性备份与报告清单；schema v4 快照可按其保存的报告上下文重建 PDF，但模板版本/字体变化可能改变二进制。缺少计算时发布状态的旧快照不得重建 PDF，因此遗留缓存和重要报告需单独归档。

## 8. 迁移 `005` 与旧记录兼容

- 当前迁移清单为 `001_initial.sql`～`005_calculation_release_status.sql`。`005` 只向 `calculations` 增加允许为空且限定枚举的 `release_status`，不增加模块专属列，也不改写 JSON 计算结果。
- 新写入记录必须保存注册模块当时的有效发布状态，并写入 snapshot schema v4 / report context schema v4。发布状态不是计算结果，改变当前注册表状态不会改变历史记录。
- 迁移前记录的列值为 `NULL`，repository 统一返回 `legacy_unknown`；该值表示“当时状态未记录”，只能按内部测试边界展示，不能推断为任何历史放行状态。
- HTML 可读取旧报告上下文；旧记录缺少上下文时允许从已保存快照映射展示，但不得调用计算器。报告模型对缺失字段使用 `legacy_unknown` 默认值。
- PDF 服务先查找与旧记录模板版本匹配的 ready artifact，并校验相对路径、大小和 SHA-256。校验通过的遗留缓存可下载并带 legacy 响应头/Warning/文件名前缀；没有有效缓存（含缓存损坏）时返回 `409 LEGACY_RELEASE_STATUS_MISSING`，不得用当前发布状态重新生成。
- 远程部署必须先在线备份，再受控应用 `005` 并执行 `--check`、旧快照/缓存读取和隔离备份恢复；既有 Phase 4 的 `001`～`004` 证据不覆盖本迁移。

## 9. 数据模型验收

- 可以通过通用表保存并完整读取 9 个已注册模块的 schema v4 快照、HTML 报告上下文和 PDF artifact；仅增加计算级通用发布状态列，不增加模块专属表/列。
- 旧计算模型版本在新版本发布后仍能读取；缺少计算时发布状态的旧记录仅能下载经完整性验证的既有缓存 PDF，其他 PDF 请求返回受控 `LEGACY_RELEASE_STATUS_MISSING`，不得用当前模型或当前发布状态静默补算。
- 数据库约束拒绝非法状态组合；应用测试验证 JSON schema。
- 在线备份期间可继续只读/短写操作，恢复后记录数、哈希和抽样报告一致。
