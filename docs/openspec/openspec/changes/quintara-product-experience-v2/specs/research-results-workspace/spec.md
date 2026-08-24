## Purpose

规定模型完成后如何优先呈现五只研究组合、策略与数据证据，并提供可追溯历史和稳定 CSV 导出，而不是以技术清单代替结果。

## ADDED Requirements

### Requirement: Top-5 组合优先呈现
**RRW-001** Quintara SHALL 在成功预测后首先展示五只唯一 A 股的名称、六位代码、交易所、固定权重 0.40/0.25/0.15/0.12/0.08、模型评分和合格状态；manifest 配置进入“数据与模型依据”详情。

#### Scenario: 预测成功
- **WHEN** `PIT_BASELINE` 或合格 `CUSTOM_UNIVERSE` 生成五只候选
- **THEN** 结果首页显示组合卡片/表格、策略、预测日期、数据截止日和显著风险声明

#### Scenario: 合格候选少于五只
- **WHEN** 最新截面经过停牌、缺失和状态过滤后候选少于五只
- **THEN** 本次预测标为失败并列出过滤数量与原因，不用低质量候选补足

### Requirement: 模式身份贯穿结果
**RRW-002** Quintara SHALL 在页面、历史、CSV、manifest 和诊断中显示 `PIT_BASELINE`、`CUSTOM_UNIVERSE` 或 `NON_PIT_FALLBACK`；非 PIT 结果 SHALL 显著说明幸存者偏差，并与 PIT 模型和结果分库存储。

#### Scenario: 用户选择非 PIT 回退
- **WHEN** 用户确认使用 `NON_PIT_FALLBACK` 完成训练与预测
- **THEN** 结果标题、每条导出记录和历史条目均包含该身份及警告版本

### Requirement: 结果解释与不确定性可读
**RRW-003** Quintara SHALL 用“模型评分、研究组合、历史统计”等研究措辞解释策略差异、主要特征贡献、数据质量提醒和适用时间窗口，并明确评分不是收益保证。

#### Scenario: 查看单只股票详情
- **WHEN** 用户展开组合成员
- **THEN** 页面展示入选排名、评分、主要特征方向、特殊状态和数据完整性，而不展示行动性交易指令

### Requirement: 结果具有完整溯源
**RRW-004** Quintara SHALL 将结果绑定到运行 ID、数据 generation、股票池、模型、内核合同版本、标签合同、策略参数和声明版本；任何身份不匹配 SHALL 阻止结果发布。

#### Scenario: 模型来自旧数据版本
- **WHEN** 活动数据 generation 已变化且模型未重训
- **THEN** 一键流程标记模型过期并先重训，不以旧模型发布新数据身份结果

### Requirement: 历史与 CSV 导出可核验
**RRW-005** Quintara SHALL 提供按日期、股票池、策略和模式筛选的运行历史；成功结果可导出 UTF-8 CSV，包含组合字段、溯源字段、风险提示和内容哈希，导出前可选择路径并避免静默覆盖。

#### Scenario: 导出成功结果
- **WHEN** 用户选择目标路径并确认导出
- **THEN** 应用写入可由常见表格软件读取的 CSV，并显示文件位置、记录数和哈希

#### Scenario: 目标文件已存在
- **WHEN** 用户选择已存在的文件名
- **THEN** 应用请求确认覆盖或选择新名称，并保留原文件直到新文件完整写入
