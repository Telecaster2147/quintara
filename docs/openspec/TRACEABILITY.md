# Quintara 需求追踪矩阵

本矩阵按决策范围将 Grill 中的稳定编号映射到 OpenSpec 能力。单个 OpenSpec Requirement 的
稳定 ID 位于对应规范正文，例如 `DAT-004`、`KER-002`、`QAL-001`。

## v2 产品体验覆盖

`quintara-product-experience-v2` 叠加在 v1 基线上，并记录 2026-08-24 产品所有者补充决定：
用户首次使用时主动选择安装包开发者数据、BaoStock 在线初始化或自己的 CSV，所选活动 generation
保存于本地并在本机训练；三类来源后续都由受控 BaoStock 路径生成只读派生版本。

| 决策与审计范围 | v2 OpenSpec 能力 | 覆盖重点 |
|---|---|---|
| C-006/C-008/C-023/C-058/C-090、2026-08-24 补充决定 | `first-run-data-choice`, `provider-production-data` | 来源显式选择、生产数据版本包、本地落盘、CSV 严格检查、BaoStock 更新、来源追溯 |
| C-065–C-069、C-075–C-078、UI03–UI10、UI16–UI19 | `desktop-product-experience`, `long-running-operations` | 左侧导航、通俗状态、设计系统、主题/DPI、单实例、进度、停止与恢复 |
| C-070–C-074、C-084–C-089、UI11–UI15、F04–F11 | `desktop-product-experience`, `research-results-workspace` | 股票池表格、100只门禁、Top-5、模式身份、历史和 CSV 导出 |
| C-079/C-080、UI20/UI21、T23–T30 | `desktop-release-evidence` | Windows/Linux/WSLg 真实窗口、GUI 旅程、视觉回归、安装卸载与脱敏证据 |

v2 的稳定 Requirement ID 为 `FRC-001`–`FRC-006`、`PPD-001`–`PPD-011`、
`DPE-001`–`DPE-007`、`LRO-001`–`LRO-006`、`RRW-001`–`RRW-005`、
`DRE-001`–`DRE-006`。2026-08-25 BaoStock 补充需求对应 `FRC-004`、`PPD-008`–`PPD-011`、
`LRO-006` 与 `DRE-002`，覆盖三来源初始化/派生更新、完整交易日、PIT 续接、阶段恢复和双平台旅程。

## 确认需求 C-xxx

| Grill 范围 | 主要 OpenSpec 能力 | 覆盖重点 |
|---|---|---|
| C-001–C-005 | `proposal`, `installation-runtime`, `desktop-gui`, `shell-cli` | 产品名、项目、平台、桌面 GUI/CLI、无 TUI/WebUI |
| C-006–C-011 | `data-lifecycle`, `csv-ingestion`, `environment-doctor`, `kernel-training` | 自带管理数据、用户 CSV、BaoStock、环境、权威内核、开源本地定位 |
| C-012–C-022 | `desktop-gui`, `job-artifacts`, `results-explainability` | 普通用户、向导、一键流程、更新确认、关闭与清理 |
| C-023–C-027 | `data-lifecycle`, `csv-ingestion`, `universe-management` | 2015至今、3–10年、PIT闭包、字段映射、辅助资料、失败报告 |
| C-028–C-034 | `kernel-training`, `prediction-portfolio`, `results-explainability`, `environment-doctor` | 结果内容、参数白名单、CPU权威、更新重训、30分钟警告 |
| C-035–C-040 | `installation-runtime`, `privacy-legal-versioning`, `quality-release` | Windows CI、版本提示、兼容阻断、稳定版质量门禁 |
| C-041–C-059 | `quality-release`, `shell-cli`, `universe-management`, `csv-ingestion`, `job-artifacts`, `privacy-legal-versioning` | 完整稳定版、发布顺序、任意A股、缺失策略、存储、MIT、零遥测 |
| C-060–C-080 | `desktop-gui`, `shell-cli`, `job-artifacts`, `results-explainability`, `quality-release` | WebUI删除、GUI形态、进度/退出、多股票池、CSV导出、主题、单实例、GUI测试 |
| C-081–C-090 | `shell-cli`, `universe-management`, `privacy-legal-versioning`, `data-lifecycle` | 完整CLI、A股边界、特殊状态、双层100只门禁、法律、非PIT回退、来源追溯 |

## 第三至第五轮问题

| Grill 范围 | 主要 OpenSpec 能力 | 覆盖重点 |
|---|---|---|
| T01–T08 | `proposal`, `universe-management`, `data-lifecycle`, `quality-release` | 稳定版范围、默认PIT、定制池、模式隔离、按需下载 |
| T09–T15 | `kernel-training`, `prediction-portfolio`, `results-explainability` | T+1开盘/T+5收盘标签、缺失样本、固定权重、解释与风险窗口 |
| T16–T22 | `data-lifecycle`, `csv-ingestion`, `job-artifacts`, `privacy-legal-versioning` | 更新时间、旧版本、CSV冲突/隐私、数据目录、保留、版本检查 |
| T23–T30 | `environment-doctor`, `installation-runtime`, `quality-release` | GPU实验路径、平台矩阵、验收责任、文档门禁 |
| UI01–UI22 | `desktop-gui`, `shell-cli`, `job-artifacts`, `results-explainability`, `privacy-legal-versioning` | 独立GUI、无桌面CLI、生命周期、股票池、导出、法律、DPI、单实例、隐私 |
| F01–F03 | `shell-cli`, `job-artifacts` | CLI完整范围、交互/直接命令、信号清理 |
| F04–F07 | `universe-management`, `prediction-portfolio` | A股范围、特殊状态、100只门禁、候选不足五只 |
| F08–F10 | `privacy-legal-versioning`, `results-explainability` | 中国大陆研究场景、声明留痕、非保证性措辞 |
| F11–F12 | `data-lifecycle`, `universe-management`, `job-artifacts`, `results-explainability` | 非PIT显式降级、身份隔离、来源与哈希追溯 |

## 规范统计

- 13个能力规范
- 95条规范要求
- 106个 WHEN/THEN 验收场景
- 119项实现/测试/文档任务，其中 77 项已完成并有本地或 CI 证据，42 项保留为
  真实 PIT 供应商、原生安装包、干净主机或跨平台深测门禁。

任何新增所有者决策先进入 `REQUIREMENTS_GRILL.md` 的变更记录，再通过新的 OpenSpec change
修改能力规范；实现细节使用 ADR 或 `design.md`，不回写为未经确认的产品需求。
