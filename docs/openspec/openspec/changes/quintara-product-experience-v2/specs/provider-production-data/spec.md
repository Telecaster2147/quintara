## Purpose

定义随应用交付的开发者参考数据如何作为可选择、可验证、可更新的本地训练数据，并确保行情、额外特征、PIT 成分和许可证信息完整追溯。

## ADDED Requirements

### Requirement: 标准生产数据具有版本化身份
**PPD-001** Quintara SHALL 将“Quintara 开发者参考数据”定义为随应用发布的数据 generation；每个版本 SHALL 包含行情、extra features、交易日历、证券主数据、适用的历史 PIT 成分区间和参考结果，以及记录版本、截止日、覆盖范围、行数、文件哈希、来源、获取时间、许可说明和生成身份的 manifest。

#### Scenario: 展示可用版本
- **WHEN** 用户查看供应方数据来源
- **THEN** 应用展示版本、截止日、日期范围、股票范围、大小、校验状态和来源链接

#### Scenario: PIT 材料缺失
- **WHEN** 标记为 `PIT_BASELINE` 的数据包缺少历史成分区间或其哈希
- **THEN** 应用将该包判为未通过，并保持上一已验证 generation 为活动版本

### Requirement: 安装介质与联网下载共享合同
**PPD-002** Quintara SHALL 支持由安装包附带或从供应方发布端下载同一逻辑数据包；两种交付方式 SHALL 使用相同 manifest、内容哈希、许可信息和激活检查。安装包附带的原始压缩包 SHALL 保持在应用目录树的 `data/developer/`，活动 generation SHALL 存入用户选择的工作目录。

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

### Requirement: 开发者数据输出绑定参考结果
**PPD-007** Quintara SHALL 为 `quintara-developer-data-v1` 使用清单声明的 300 成员 PIT 合同、完整可用历史和版本化 open/open 标签合同执行固定参数训练；结果 SHALL 与包内 `reference-result.csv` 的股票、顺序、权重和 SHA-256 完全一致，不一致时不发布结果。

#### Scenario: 参考结果完全一致
- **WHEN** 用户使用未修改的随包开发者数据完成本机 CPU 训练
- **THEN** 应用发布五行 `stock_id,weight` 结果，并在准备报告中记录参考结果哈希通过

#### Scenario: 数据或训练语义发生漂移
- **WHEN** 实际结果任一股票、顺序、权重或 CSV 哈希偏离清单参考结果
- **THEN** 任务以明确的一致性错误结束，上一份已发布结果保持可用

### Requirement: 三种来源统一派生更新
**PPD-008** Quintara SHALL 允许安装包数据、BaoStock 初始化数据和用户 CSV 的活动 generation 通过数据页“一键更新至最新交易日”；安装包与 CSV 原件保持只读，更新结果 SHALL 标记为 BaoStock 派生版本并记录父 generation、原来源、源哈希、合并区间、字段、单位、复权和股票池合同。

#### Scenario: 固定参考数据派生更新
- **WHEN** 用户更新未修改的开发者参考 generation
- **THEN** 新 generation 使用 BaoStock 派生身份，原始 sidecar、参考 generation 与参考结果保持不变

#### Scenario: 用户 CSV 派生更新
- **WHEN** 用户确认 CSV 字段映射、单位、复权及保持或变更股票池的计划
- **THEN** 应用按选定代码集合增量合并并在新 manifest 保存源 CSV 哈希和合同复核报告

### Requirement: 目标截止日来自远端完整交易日
**PPD-009** Quintara SHALL 通过 BaoStock 交易日历及实际日线可用性探测确定最新完整交易日，从当前截止日之后的第一个有效交易日开始，不以操作系统日期直接替代远端完整性证据，也不重复扩大已发布历史区间。

#### Scenario: 当日数据尚未完整
- **WHEN** 交易日历包含当天但宽基指数日线探测未返回完整记录
- **THEN** 更新目标回退到最近实际可用交易日并在预览展示提醒

#### Scenario: 已处于最新
- **WHEN** 当前截止日不早于远端最新完整交易日
- **THEN** 应用报告无需新增，不发布重复 generation，也不将模型误标为过期

### Requirement: PIT 区间连续且历史证券保留
**PPD-010** `PIT_BASELINE` 更新 SHALL 对新增交易日获取可验证的历史成分快照并压缩为无重叠区间，续接旧开放区间、记录加入移出，保留退市或代码变化证券的历史行情和证券资料；当前快照 SHALL NOT 被静默当作完整历史 PIT。

#### Scenario: 成分在增量区间变化
- **WHEN** 证券从指数移出且另一证券加入
- **THEN** 旧证券区间在最后有效交易日闭合，新证券从首次有效交易日开启，历史行与证券资料继续存在

#### Scenario: 历史材料不完整
- **WHEN** 交易日历、历史成分快照或区间校验缺失或重叠
- **THEN** 应用不发布 PIT generation，并保持上一活动 generation 可训练和可查看

### Requirement: 更新计划、阶段与检查点可见
**PPD-011** 更新确认前 SHALL 展示当前来源/版本/截止日、目标交易日、证券和成分变化、字段/单位/复权、预计行数/下载量、工作目录和身份变化；运行时 SHALL 展示连接、证券主数据、股票池、行情与额外字段、校验、发布的真实阶段和完成数量。检查点 SHALL 绑定代码集合、日期范围、字段、复权、路线和连接器身份。

#### Scenario: 失败或取消
- **WHEN** 登录、查询、模式、单位、复权、PIT、重复键、OHLC、磁盘、取消或退出检查失败
- **THEN** 应用展示失败阶段、进度和重试/重新规划动作，清理或保留身份匹配的检查点，且活动指针保持原值
