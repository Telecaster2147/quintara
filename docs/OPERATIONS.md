# Quintara 运维手册

## 首次运行

1. `quintara doctor` 检查系统、磁盘和 GPU 信息。
2. `quintara bootstrap` 创建用户目录并清理上一次中断留下的 staging。
3. `quintara data update --pit-membership-csv PIT.csv` 或 `quintara data import` 发布首个数据 generation；没有历史 PIT 文件时必须显式加 `--allow-non-pit`。
4. 确认路线后执行 `quintara run`。

## 更新和回滚

数据更新始终写入 `data/staging`，文件 hash 和 manifest 写完后才切换
`data/active.json`。更新失败时 active generation 仍然可读。需要回滚时，
将 registry 中已验证的 generation 重新发布为 active pointer；不要手工覆盖 CSV。

## 并发与中断

同一工作区使用 `quintara.lock` 排斥训练/更新/导入。BaoStock 下载按股票保存 checkpoint，
重复相同计划会从已完成股票继续。GUI 任务在后台线程运行，关闭窗口先请求取消；超过等待
窗口会终止 worker，下次启动清理未发布 staging。启动时会记录并清理遗留 staging。

## 结果审计

每次成功 run 包含：

- `manifest.json`：路线、策略、数据/模型/结果 generation 和指标；
- `identity.json`：标签、特征、配置、runtime hash；
- `prepared_report.json`：PIT 日期合同和排除行统计；
- `result.csv`：严格两列 `stock_id,weight`；
- `ranking.csv`：全体 cutoff 排名和模型分数。
- `result_view.json`：带名称/交易所/模型分数的首页视图；`explanations.json`：特征贡献（只解释模型评分）。

相同数据 generation、路线、策略、标签和配置再次运行时，历史会新增 `CACHED` 记录并复用
已验证结果；数据 generation 变化会自动重新训练。

## 常见恢复

| 状态 | 操作 |
| --- | --- |
| `NO_ACTIVE_DATA` | 执行 `data update` 或 `data import` |
| `CSV-MAPPING` | 修正列名或传入 `--mapping` |
| `cutoff does not satisfy` | 检查完整交易日、成员和上市日期覆盖 |
| `LockBusy` | 确认没有其他 GUI/CLI 任务，再重试 |
| `unresolved prediction tie` | 保留告警，检查数据规模和特征；产品不静默打破模型平分 |
| `NON_PIT_REQUIRED` | 提供历史成员文件，或在确认幸存者偏差后使用 `--allow-non-pit` |
| `DATA-HASH-MISMATCH` | 停止使用损坏快照，保留旧版本并重新更新 |
