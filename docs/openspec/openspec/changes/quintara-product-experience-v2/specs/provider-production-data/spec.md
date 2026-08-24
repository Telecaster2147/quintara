## Purpose

定义供应方发布的比赛生产数据如何作为可选择、可验证、可更新的本地训练数据，并确保行情、额外特征、PIT 成分和许可证信息完整追溯。

## ADDED Requirements

### Requirement: 标准生产数据具有版本化身份
**PPD-001** Quintara SHALL 将“Quintara 标准生产数据”定义为供应方使用比赛生产管线发布的数据 generation；每个版本 SHALL 包含行情、extra features、交易日历、证券主数据、适用的历史 PIT 成分区间，以及记录版本、截止日、覆盖范围、行数、文件哈希、来源、获取时间、许可链接和管线身份的 manifest。

#### Scenario: 展示可用版本
- **WHEN** 用户查看供应方数据来源
- **THEN** 应用展示版本、截止日、日期范围、股票范围、大小、校验状态和来源链接

#### Scenario: PIT 材料缺失
- **WHEN** 标记为 `PIT_BASELINE` 的数据包缺少历史成分区间或其哈希
- **THEN** 应用将该包判为未通过，并保持上一已验证 generation 为活动版本

### Requirement: 安装介质与联网下载共享合同
**PPD-002** Quintara SHALL 支持由安装包附带或从供应方发布端下载同一逻辑数据包；两种交付方式 SHALL 使用相同 manifest、内容哈希、许可信息和激活检查，完成后存入用户本地数据仓库。

#### Scenario: 安装包带有数据
- **WHEN** 发行物包含匹配平台且通过校验的生产数据包
- **THEN** 用户可将其导入本地仓库并在无网络状态完成准备

#### Scenario: 发行物采用精简安装
- **WHEN** 安装介质未携带大数据包且用户选择供应方数据
- **THEN** 应用展示下载大小、所需空间和目标目录，经确认后从发布端获取

### Requirement: 获取过程可校验且可恢复
**PPD-003** Quintara SHALL 在独立暂存区进行下载，提供字节级真实进度、速率、已用时间、剩余量估计和取消；支持断点续传时 SHALL 校验服务端对象身份，完成后逐文件校验并原子激活。

#### Scenario: 网络中断后继续
- **WHEN** 下载因网络中断而暂停且远端对象身份保持一致
- **THEN** 用户重试时从已验证的分块继续并保持上一活动 generation 可用

#### Scenario: 哈希校验失败
- **WHEN** 任一文件的内容哈希与 manifest 不一致
- **THEN** 应用隔离暂存内容、展示失败文件和重试动作，并继续使用上一活动 generation

#### Scenario: 用户取消
- **WHEN** 用户确认取消正在进行的下载
- **THEN** 任务进入已取消状态，安全保留可续传分块且不激活未完成数据

### Requirement: 传输前完成资源与身份预检
**PPD-004** Quintara SHALL 在市场数据传输前验证许可确认、磁盘预算、目标目录可写性、manifest 兼容性及所选路由所需的 PIT 材料；预检结果 SHALL 明确区分阻断项与提醒项。

#### Scenario: 可用空间不足
- **WHEN** 可用空间小于下载、解包、校验和保留上一版本所需预算
- **THEN** 应用在传输前停止计划并展示需求量、可用量和更换目录动作

#### Scenario: PIT 服务暂不可用
- **WHEN** 新 `PIT_BASELINE` generation 所需历史成分资料未就绪
- **THEN** 应用先展示使用上一已验证 PIT 版本或显式创建 `NON_PIT_FALLBACK` 计划的选择，不先下载大规模行情

### Requirement: BaoStock 受控更新本地数据
**PPD-005** Quintara SHALL 允许用户对活动供应方 generation 执行“一键更新至最新”：登录 BaoStock、拉取增量行情和 extra features、连接到当前本地数据，并以新 generation 发布；更新 SHALL 保留来源级证据且保持 `PIT_BASELINE`、`CUSTOM_UNIVERSE`、`NON_PIT_FALLBACK` 身份隔离。

#### Scenario: 成功增量更新
- **WHEN** 活动数据截止日早于可用交易日且所需 PIT 材料就绪
- **THEN** 应用仅获取缺失区间，校验合并结果，并在原子激活后显示新旧版本差异

#### Scenario: 更新失败
- **WHEN** BaoStock 登录、查询、合并或发布阶段失败
- **THEN** 应用展示失败阶段和可执行重试，活动 generation 与其模型映射保持原状

### Requirement: 用户 CSV 保持独立来源身份
**PPD-006** Quintara SHALL 将用户 CSV 复制或导入受管本地 generation，保存原文件哈希、字段映射和检查报告；检查只报告问题而不静默改写值，用户 CSV 与供应方生产数据的模型、结果和历史分别存储。

#### Scenario: CSV 检查通过
- **WHEN** 用户 CSV 满足字段、类型、日期、覆盖、重复、缺失和股票池门禁
- **THEN** 应用将其作为 `CUSTOM_UNIVERSE` generation 原子激活并允许本地训练

#### Scenario: CSV 检查失败
- **WHEN** CSV 存在阻断性问题
- **THEN** 应用保持原文件不变并生成包含问题类型、数量、样例和行列定位的报告
