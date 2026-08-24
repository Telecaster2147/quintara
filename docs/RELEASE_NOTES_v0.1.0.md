# Quintara 0.1.0 发布说明

**发布日期：** 2026-08-24  
**版本标签：** `v0.1.0`  
**发布类型：** 首个稳定版

Quintara 是一款在本机运行的 A 股数据与组合研究工具。它将 BaoStock 数据更新、
CSV 检查、股票池管理、训练、预测、Top-5 组合生成、结果解释和环境诊断整合进
独立的中文桌面应用，并为自动化和无桌面环境保留完整的 CLI。

> Quintara 用于本地数据研究。输出内容是模型推荐组合与预测排名，不构成收益承诺或
> 交易指令。

---

## 下载

### Windows x86-64

| 文件 | 用途 |
| --- | --- |
| `Quintara-Windows-x64-Setup.exe` | 安装版，支持开始菜单和桌面快捷方式 |
| `Quintara-Windows-x64-Portable.exe` | 便携版，下载后可直接运行 |

安装包已包含 Python、Qt、LightGBM 和 Quintara 运行环境。

### Linux x86-64

| 文件 | 支持范围 |
| --- | --- |
| `Quintara-Linux-x86_64.tar.gz` | Ubuntu 22.04/24.04、Debian 12/13 |

解压后运行：

```bash
tar -xzf Quintara-Linux-x86_64.tar.gz
chmod +x Quintara
./Quintara --version
./Quintara
```

### 完整性校验

Release Assets 中的 `SHA256SUMS.txt` 记录了所有发布包的 SHA-256。Linux 可使用：

```bash
sha256sum -c SHA256SUMS.txt
```

Windows PowerShell 可使用：

```powershell
Get-FileHash .\Quintara-Windows-x64-Setup.exe -Algorithm SHA256
```

将命令输出与 `SHA256SUMS.txt` 中的对应值核对即可。

---

## 版本亮点

### 独立桌面应用

- 基于 PySide6 的中文 GUI，日常流程集中在应用内完成。
- Windows 与 Linux 共用同一套数据、训练和结果逻辑。
- 提供安装版、便携版和 Linux 单文件发布包。
- GUI 与 CLI 共用本地数据版本、股票池、模型、运行记录和结果。

### BaoStock 数据生命周期

- 由用户发起数据更新，应用自动登录 BaoStock 并拉取行情与 extra features。
- 新数据先进入 staging 区域，通过校验后再原子发布为新的数据世代。
- 下载中断、字段异常或校验失败时，当前有效数据版本保持原状。
- 数据世代采用不可变设计，结果可追溯到确切的输入版本。
- 首次安装保持轻量；历史行情在首次数据更新时保存到用户电脑。

### 自有 CSV 导入与训练前检查

- 支持导入用户准备的 CSV 数据。
- 训练前检查编码、必需字段、股票代码、日期、重复键和历史长度。
- 检查 OHLC 关系、数值范围、缺失情况与单位声明。
- 检查报告提供中文原因、定位信息和问题样本。
- 导入时保留源文件，数据整理规则始终由用户控制。

字段、单位和校验规则详见 `docs/CSV_FIELD_DICTIONARY.md`。

### PIT 与股票池路线

Quintara 0.1.0 将三种研究路线显式分离：

| 路线 | 说明 |
| --- | --- |
| `PIT_BASELINE` | 使用经过校验的历史成员有效区间研究沪深 300 |
| `CUSTOM_UNIVERSE` | 使用用户定义的静态 A 股股票池 |
| `NON_PIT_FALLBACK` | 使用当前成分快照进行回看，全程保留显著提示 |

- PIT 成员数据采用 `stock_id,index_code,start_date,end_date` 有效区间。
- 自定义股票池至少包含 100 只沪、深、北交易所 A 股普通股。
- 自定义静态股票池的结果会标记幸存者偏差。
- 不同路线的模型与结果相互隔离，避免研究口径混用。

PIT 与静态成分路线始终使用独立数据、模型和结果身份。

### 训练、预测与 Top-5 组合

- 训练窗口可选 3–10 年。
- 默认预测标签为 `close(T+5) / open(T+1) - 1`，交易周期按实际交易日计算。
- 使用现有算法内核直接完成特征计算、模型训练、候选排名与组合生成。
- 每次运行输出排名最高的五只股票。
- Top-5 使用固定权重 `40% / 25% / 15% / 12% / 8%`。
- CPU 是权威结果路径；NVIDIA GPU 在环境诊断通过后可用于实验加速。

### 激进、稳健与保守策略

本版本提供三种可选策略：

- `aggressive`：激进；
- `balanced`：稳健，默认选项；
- `conservative`：保守。

策略通过模型容量和正则参数调整选股风格。Top-5 组合权重在三种策略中保持一致，
便于比较策略本身对排名的影响。

### 结果解释与可追溯性

结果首页展示：

- 五只入选股票及组合权重；
- 数据截止日和下一实际交易周；
- 股票池路线和数据新鲜度；
- 入选理由和主要特征贡献；
- 20/60/120 日风险指标与相关性；
- 完整候选排名、模型分数和数据来源。

每次结果都绑定：

- 数据世代；
- 股票池 identity；
- 模型与策略配置；
- 运行环境 identity；
- 软件版本和运行编号。

这些信息使结果具备复查、对比和复现基础。

### 启动环境诊断

Quintara 启动后会读取并展示：

- 操作系统与版本；
- CPU 与系统架构；
- 内存和可用磁盘空间；
- NVIDIA GPU 型号与相关运行环境；
- Python 与 Quintara 运行时 identity；
- 数据、模型和结果目录的可用性。

诊断信息保存在本机。用户可主动生成脱敏诊断包，用于定位运行问题。

### 完整 CLI

GUI 与 CLI 共用应用内核。常用命令示例：

```bash
# 环境诊断
quintara doctor

# 更新 BaoStock 数据
quintara data update --start-date 2015-01-01 --pit-membership-csv ./pit_membership.csv

# 训练并生成稳健策略结果
quintara run --strategy balanced --years 5

# 查看运行历史
quintara runs

# 查看某次运行的完整结果
quintara results RUN_ID --details
```

---

## 本地存储与隐私

### 默认数据位置

| 系统 | 目录 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Quintara` |
| Linux | `~/.local/share/quintara` |

主要内容包括：

```text
data/generations/       不可变数据版本
universes/              股票池定义
models/                 模型文件
results/RUN_ID/         组合、排名、解释与来源信息
registry.sqlite3        本地运行索引
diagnostics/            用户主动导出的脱敏诊断包
```

### 隐私原则

- 自动遥测、崩溃上传与使用统计永久关闭。
- 环境信息、日志、股票池、模型和结果保存在本机。
- 数据更新由用户主动发起，此时应用会连接 BaoStock。
- 版本检查默认关闭；启用后只请求 GitHub Releases 的版本信息。
- 诊断包由用户主动生成，默认排除原始行情数据。

完整说明见 `docs/PRIVACY.md`。

---

## 安装、升级与卸载

### Windows 安装版

1. 下载 `Quintara-Windows-x64-Setup.exe`。
2. 运行安装向导。
3. 按需创建开始菜单和桌面快捷方式。
4. 从开始菜单或桌面启动 Quintara。

安装包目前未使用数字签名，Windows SmartScreen 可能显示发布者提示。
请核对 Release 来源和 SHA-256，然后在“更多信息”中继续安装。

### Windows 便携版

将 `Quintara-Windows-x64-Portable.exe` 保存到需要的位置并直接运行。用户数据仍保存在
`%LOCALAPPDATA%\Quintara`，替换主程序时不会覆盖该目录。

### 升级

- 安装版：下载新版安装程序并运行覆盖安装。
- 便携版：用新版可执行文件替换旧版主程序。
- 默认用户数据目录在升级过程中保留。

### 卸载

Windows 可从系统的“已安装的应用”中卸载 Quintara。卸载程序默认保留用户数据，
便于重新安装后继续使用。

---

## 0.1.0 的已知边界

- 安装包处于无数字签名状态，SmartScreen 可能展示发布者提示。
- NVIDIA GPU 属于实验加速路径；CPU 路径用于权威结果。
- 历史行情未嵌入安装包，首次使用时由用户发起 BaoStock 数据更新。
- 静态自定义股票池存在幸存者偏差，结果页会持续显示该标记。
- `NON_PIT_FALLBACK` 用于当前成分快照回看，该路线与 PIT 基准结果分开管理。
- 数据质量取决于 BaoStock 数据或用户 CSV；训练前门禁用于识别异常输入。

---

## 质量与发布验证

Quintara 0.1.0 的发布源提交为：

```text
59bf5def9ca36d6957998b2b45a616c1237e48ed
```

发布前门禁包括：

- Ubuntu 与 Windows CI；
- Ruff 静态检查；
- 项目类型检查；
- 18 项 pytest 测试，包括 Hypothesis 与 BaoStock fake；
- OpenSpec `validate --strict --all`；
- Python wheel 构建与安装烟测；
- Linux PyInstaller bundle 启动烟测；
- Windows PyInstaller 与 Inno Setup installer 构建烟测；
- CLI `--version`、`doctor`、bootstrap 与 CSV 流程烟测；
- Linux offscreen GUI 启动烟测；
- SBOM、第三方组件说明与机器可读发布证据。

已通过的 GitHub Actions：

- Quintara CI：[32693975329](https://github.com/Telecaster2147/quintara/actions/runs/32693975329)
- Package smoke：[32694000601](https://github.com/Telecaster2147/quintara/actions/runs/32694000601)

---

## 重要文档

| 文档 | 内容 |
| --- | --- |
| [`README.md`](https://github.com/Telecaster2147/quintara/blob/v0.1.0/README.md) | 安装、使用与项目入口 |
| [`docs/FIRST_USE.md`](https://github.com/Telecaster2147/quintara/blob/v0.1.0/docs/FIRST_USE.md) | 首次启动和完整操作流程 |
| [`docs/CSV_FIELD_DICTIONARY.md`](https://github.com/Telecaster2147/quintara/blob/v0.1.0/docs/CSV_FIELD_DICTIONARY.md) | CSV 字段、单位和验证规则 |
| [`docs/OPERATIONS.md`](https://github.com/Telecaster2147/quintara/blob/v0.1.0/docs/OPERATIONS.md) | 数据恢复、运行维护和排错 |
| [`docs/ERROR_CATALOG.md`](https://github.com/Telecaster2147/quintara/blob/v0.1.0/docs/ERROR_CATALOG.md) | 中文错误索引和处理建议 |
| [`docs/PRIVACY.md`](https://github.com/Telecaster2147/quintara/blob/v0.1.0/docs/PRIVACY.md) | 本地数据与隐私原则 |
| [`docs/THIRD_PARTY_NOTICES.md`](https://github.com/Telecaster2147/quintara/blob/v0.1.0/docs/THIRD_PARTY_NOTICES.md) | 第三方组件、许可证与数据来源 |

---

## 致谢

Quintara 的实现与发布依赖 Python、PySide6 / Qt、LightGBM、BaoStock、uv、
PyInstaller、Inno Setup 以及其他开源项目。完整归属和许可证信息见
`docs/THIRD_PARTY_NOTICES.md`。

---

**Full Changelog:** [v0.1.0 完整提交记录](https://github.com/Telecaster2147/quintara/commits/v0.1.0)
