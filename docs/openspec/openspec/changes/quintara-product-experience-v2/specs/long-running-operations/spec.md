## Purpose

统一下载、数据检查、更新、训练和预测的可观察任务语义，让用户获得真实进度、明确停止行为、故障证据和可靠恢复。

## ADDED Requirements

### Requirement: 长任务采用统一状态合同
**LRO-001** Quintara SHALL 将长任务表示为 `PLANNING`、`READY`、`RUNNING`、`PAUSING`、`CANCELLING`、`CANCELLED`、`SUCCEEDED`、`FAILED` 或 `RECOVERABLE`，每次转换记录任务类型、阶段、时间、输入身份和产物引用；GUI 与 CLI SHALL 读取同一状态。

#### Scenario: 状态跨入口一致
- **WHEN** 用户在 CLI 发起训练后打开 GUI
- **THEN** GUI 展示同一任务 ID、阶段、数据身份、进度和停止能力

### Requirement: 进度只表达可测事实
**LRO-002** Quintara SHALL 对可计数阶段展示已完成量/总量，对只知阶段的工作展示阶段进度；剩余时间仅在样本足够时标为估算，日志与用户状态分层显示。

#### Scenario: 模型训练总轮次已知
- **WHEN** 内核报告已完成轮次和总轮次
- **THEN** 页面展示轮次比例、耗时和标为估算的剩余时间

#### Scenario: 总工作量未知
- **WHEN** 当前阶段没有可靠总量
- **THEN** 页面展示阶段名称和活动指示，不生成虚假百分比

### Requirement: 停止与退出可预测
**LRO-003** Quintara SHALL 为支持安全停止的任务提供停止操作，先请求协作式停止并清理未发布工件；超过规定等待期后可由用户确认强制结束，下一次启动执行恢复检查。

#### Scenario: 训练正常停止
- **WHEN** 用户确认停止且内核在等待期内响应
- **THEN** 任务进入 `CANCELLED`，暂存模型被清理，已发布模型和数据保持可用

#### Scenario: 任务期间关闭窗口
- **WHEN** 用户关闭主窗口且存在运行任务
- **THEN** 应用展示任务名称、当前阶段及“返回任务/停止并退出”的明确选择

### Requirement: 故障保留可行动证据
**LRO-004** Quintara SHALL 为失败任务保存脱敏错误摘要、阶段、错误码、重试条件和技术日志；默认视图提供最可能的恢复动作，诊断导出隐藏用户名和绝对路径，应用不自动截屏。

#### Scenario: BaoStock 会话失效
- **WHEN** 更新任务因会话失效而失败
- **THEN** 页面说明失败发生在数据登录阶段并提供重新登录重试，技术详情保留脱敏响应证据

### Requirement: 发布遵循原子边界
**LRO-005** Quintara SHALL 只在完整校验成功后发布数据 generation、模型或结果；启动恢复 SHALL 识别孤立暂存目录并按 manifest 决定续作或清理，且始终优先保留上一已发布产物。

#### Scenario: 发布前应用崩溃
- **WHEN** 应用在产物校验后、原子切换前异常结束
- **THEN** 下次启动将该任务标为 `RECOVERABLE`，核验暂存内容后让用户继续发布或清理
