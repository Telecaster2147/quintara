# 首次使用流程

1. 打开 GUI 的“首次使用向导”并阅读中国大陆 A 股研究免责声明。
2. 在“设置”确认声明；确认记录只保存声明版本、时间和应用版本。
3. 在“环境诊断”查看 CPU、内存、磁盘、NVIDIA 驱动和依赖版本。
4. 选择 `PIT_BASELINE`（推荐且需要可验证历史成员区间）或创建至少 100 只股票的
   `CUSTOM_UNIVERSE`。仅在明确确认 survivorship bias 后选择 `NON_PIT_FALLBACK`。
5. 从 BaoStock 更新数据（推荐提供历史 PIT 成分 CSV），或用字段映射/单位声明导入自己的 CSV；
   没有 PIT 文件时在确认静态成员告警后使用 `--allow-non-pit`。
6. 选择 3–10 年历史、balanced/aggressive/conservative 策略，然后开始训练。
7. 在结果页检查路线、截止日期、标签版本、权重、排名、风险窗口和 manifest。

CLI 等价流程：

```bash
quintara bootstrap
quintara consent accept
quintara doctor
quintara data update --pit-membership-csv ./pit_membership.csv
quintara run --years 5 --strategy balanced
```

GUI 的“更新 BaoStock”会先询问可选的 PIT 成分侧车；“导入 CSV”会要求确认
字段字典中的单位声明。GUI 不会替换单位、填补缺失值或改写原始文件。
