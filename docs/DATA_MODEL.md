# 数据模型设计

## C-08/C-09 冻结补充（snapshot schema v3 / report context schema v2）

输入新增/确认拉力与速度位置、拉力类型、滑轮倍率/效率、实际槽距/槽数、死圈、安装预留、绳型/结构/材料、载荷谱、D/d、环境、制动轴/反向效率、工作制/启动次数/供电和功率系列。`dead_wrap_count` 兼容读取旧名 `dead_wraps`。

`source_status` 固定为 `project_default|user_input|standard_confirmed|manufacturer_data|pending_confirmation`。快照保存原始输入、SI 输入、未舍入结果、警告、假设、公式步骤、计算模型版本、报告模板版本、持久化报告上下文和生成时间；展示值不是权威存储。

警告包含 `code`、`severity`（`info|warning|high|blocking`）、`title`、`message`、`affected_result`、`recommended_action`。发布门禁只存状态：机械计算、产品范围、软件验收、质量安全和总发布状态；不存人员姓名或计划/实际日期。

文档版本：0.2.0
数据库：SQLite  
原则：通用元数据列 + 版本化 JSON 快照，不为每个模块不断增加业务列

## 1. 实体关系

```text
calculation
  1 ─── 0..N report_artifact
  1 ─── 0..N audit_event（MVP 可选）
```

模块目录来自代码注册表，不作为可在线编辑的数据库配置，避免数据库与已部署代码版本漂移。

## 2. `calculations` 表

| 列 | SQLite 类型 | 约束/索引 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | UUID。 |
| `module_id` | TEXT | NOT NULL, index | 如 `winch_drum`。 |
| `module_version` | TEXT | NOT NULL | SemVer 字符串。 |
| `calculation_model_version` | TEXT | NOT NULL, index | 如 `winch_drum.calc.1.1.0`。 |
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
| `snapshot_schema_version` | INTEGER | NOT NULL | JSON 快照结构版本；当前写入 3。 |
| `input_hash` | TEXT | NOT NULL | 规范化输入 + 模型版本的 SHA-256，用于诊断/可选去重。 |
| `created_at` | TEXT | NOT NULL, index | UTC ISO 8601。 |
| `request_id` | TEXT | NOT NULL | 日志关联。 |

不保存“当前默认值引用”来替代快照；所有实际采用值和来源都必须写进本次记录。JSON 序列化需稳定定义键顺序/数值策略，以便哈希和回归比较。

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

- 使用轻量迁移工具或有序 SQL 迁移；每次启动只检查，不在未经备份的生产库上做破坏性自动迁移。
- 迁移前执行 SQLite 在线备份并记录应用/模型版本；恢复演练包含主库、WAL/SHM 处理和文件权限。
- 当前不自动删除计算记录或 PDF；项目持久化容量上限 5 GiB，达到 85% 后停止生成新 PDF。若未来启用按期清理，必须先冻结策略并优先删除可再生 PDF。
- 备份至少包含 SQLite 一致性备份与报告清单；PDF 可由快照重建，但模板版本/字体变化可能改变二进制，因此重要报告需单独归档。

## 8. 数据模型验收

- 可以保存并完整读取方案 A 以及一个虚拟方案 B 快照，不改表结构。
- 旧计算模型版本在新版本发布后仍能查看和生成带原版本标识的报告。
- 数据库约束拒绝非法状态组合；应用测试验证 JSON schema。
- 在线备份期间可继续只读/短写操作，恢复后记录数、哈希和抽样报告一致。
