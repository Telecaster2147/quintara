# Quintara 生产内核对齐契约

> 本文记录原比赛生产内核的差分基线。Quintara 稳定版默认标签已按最新需求版本化为
> `close(T+5) / open(T+1) - 1`；原 `open(T+5) / open(T+1) - 1` 仅作为内部
> `competition-open-open-v1` 差分 fixture。产品契约以
> [`openspec/openspec/changes/quintara-stable-v1/specs/kernel-training/spec.md`](openspec/openspec/changes/quintara-stable-v1/specs/kernel-training/spec.md)
> 为准。

## 1. 权威来源

Quintara 算法内核的唯一权威来源是：

```text
/home/olm/bigdata/bigdata/app
```

外层 `THU-BDC2026`、历史实验目录、归档候选和 extra feature 文件不属于 Quintara 首版
生产内核。

## 2. 首版必须保持的生产身份

- 输入由基础行情、PIT 沪深 300 历史成分区间、上市状态和 manifest 组成；
- 标签为 `raw_open(T+5) / raw_open(T+1) - 1`；
- 数据在特征工程前执行上市合法性、关键 OHLC 和完整 300 股截面门禁；
- 滚动特征只使用当前和历史行；
- 模型为当前生产 LightGBM 横截面排序模型；
- 使用当前冻结配置、固定轮数、随机种子和线程策略；
- 最终组合来自模型排名；
- MVP 权重保持 `[0.40, 0.25, 0.15, 0.12, 0.08]`；
- 输出列为 `stock_id,weight`，股票数不超过 5，股票唯一，权重和不超过 1；
- 保留 generation、manifest、哈希与事务发布语义。

## 3. 适配层边界

Quintara 可以：

- 选择数据版本和过去 `x` 年的合法窗口；
- 提供环境检查、CLI、独立桌面 GUI、进度和报告；
- 在 Windows/Linux 上提供等价的文件锁和原子发布基础设施；
- 将生产模块封装成稳定服务接口；
- 为用户 CSV 增加前置检查；
- 管理数据更新、模型和运行历史。

任何会改变以下内容的工作均作为单独算法变更处理：

- 标签或标签日期；
- PIT universe；
- 特征定义；
- 模型目标与参数；
- 排名、tie 处理；
- 候选池；
- 组合权重；
- 训练/验证窗口选择原则。

算法变更应有版本号、迁移说明、时间验证和与生产基线的差分报告，不与跨平台包装混在同一
验收项中。

## 4. 扩展特征冻结

当前 `bigdata/docs/DATA_UPDATE_20260731.md` 明确将 BaoStock 估值、行业、财务、预测报告
等 extra features 标为 research-only。Quintara 首版：

- 不读取外层 `extra_features_20150101_now/`；
- 数据更新任务不抓取这些扩展特征；
- CSV 必需 schema 不包含这些字段；
- 模型训练不增加对应特征；
- 产品界面不展示“已使用扩展特征”的表述。

未来只有在 `bigdata/app` 正式生产线先完成对应变更和验证后，Quintara 才同步升级适配层。

## 5. 对齐验收

每个受支持平台都应执行：

1. 在同一个固定 fixture 上分别运行原生产入口和 Quintara 适配入口；
2. 比较输入哈希、cutoff、特征列表、配置哈希和 label contract；
3. CPU 模式比较完整 ranking 与 `result.csv`；
4. 验证 generation/manifest 闭包；
5. 对输入行序做扰动并验证不变量；
6. 对不合格 CSV 验证在训练前失败；
7. 对发布中断执行恢复测试。

首版完成的核心判据是“产品入口驱动同一生产内核”，而非仅生成格式相似的结果。
