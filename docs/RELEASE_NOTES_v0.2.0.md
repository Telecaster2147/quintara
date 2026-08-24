# Quintara 0.2.0 发布说明

**发布日期：** 2026-08-24
**版本标签：** `v0.2.0`
**版本状态：** 公开预发布版

Quintara 是一款在本机运行的 A 股数据与组合研究工具。它把数据准备、CSV 检查、股票池、
训练、结果解释和 CSV 导出整合在一个中文桌面应用中，同时提供适合自动化和无桌面环境的命令行入口。

> Quintara 仅用于本地研究、回测和软件验证。输出是模型排名与研究组合，不构成收益承诺、
> 个性化投资建议或交易指令。使用前请确认数据来源、许可和适用法规。

## 下载

### Windows x86-64

| 文件 | 用途 |
| --- | --- |
| `Quintara-Windows-x64-Setup.exe` | 安装版，支持开始菜单和桌面快捷方式 |
| `Quintara-Windows-x64-Portable.exe` | 便携版，下载后直接运行 |

安装包已包含 Python、Qt、LightGBM 与 Quintara 运行环境。Windows 安装包尚未使用数字签名，
SmartScreen 可能显示发布者提示；请先核对 Release 来源和 SHA-256。

### Linux x86-64

| 文件 | 支持范围 |
| --- | --- |
| `Quintara-Linux-x86_64.tar.gz` | Ubuntu 22.04/24.04、Debian 12/13 |

```bash
tar -xzf Quintara-Linux-x86_64.tar.gz
chmod +x Quintara quintara-cli
./Quintara
./quintara-cli --version
```

### 完整性校验

`SHA256SUMS.txt` 包含每个发布文件的 SHA-256。Linux 可执行：

```bash
sha256sum -c SHA256SUMS.txt
```

Windows PowerShell 可执行：

```powershell
Get-FileHash .\Quintara-Windows-x64-Setup.exe -Algorithm SHA256
```

## 这次更新带来什么

### 更清晰的首次使用流程

- 五步向导引导用户完成声明确认、设备检查、数据来源选择和本地存储确认。
- 首次使用可选择 Quintara 标准数据或自己的 CSV。
- 向导支持中断后继续，设置页可重新打开。
- 业务状态、下一步动作和问题原因使用中文直接呈现。

### 现代桌面工作台

- 全新的 Qt Quick 界面、紧凑导航、浅色/深色主题和高 DPI 适配。
- 训练、数据、股票池、结果和历史页面采用一致的卡片、表格和状态反馈。
- 内置研究罗盘图标，并在桌面、开始菜单、安装器和窗口中保持一致。
- 键盘焦点、辅助名称、44 px 点击目标和错误状态均纳入界面检查。

### 数据准备更可控

- 用户点击后才会连接 BaoStock；更新前展示来源、版本、许可、大小和预计空间。
- 下载采用断点续传、逐文件校验和原子切换；失败内容隔离，当前有效版本继续可用。
- CSV 导入会检查编码、字段、代码、日期、重复键、OHLC 关系、数值范围和单位声明。
- 原始 CSV 保持不变，问题报告提供中文定位信息和示例。
- 可创建、编辑、搜索和保存多个命名股票池，并清楚标出历史成员信息的适用范围。

### 训练、结果与导出

- 支持 3–10 年训练窗口，以及积极、稳健、保守三种策略。
- CPU 是可复现的默认路径；NVIDIA GPU 仅在诊断通过并由用户明确选择时使用。
- 结果页展示 Top-5、固定权重、数据截止日、入选解释、质量提醒和研究风险。
- 历史页支持按日期、股票池、策略和研究路线筛选。
- CSV 导出使用 UTF-8 原子写入；覆盖已有文件前会确认，并附带风险字段与内容哈希。
- 每次结果都绑定数据版本、股票池、模型配置、运行编号和软件版本，方便复查。

### Windows 启动体验

- 桌面和开始菜单快捷方式直接打开 GUI，不会由应用创建 PowerShell、Windows Terminal 或
  控制台窗口。
- 命令行入口 `quintara-cli.exe` 保留标准输出、错误输出、退出码和管道行为。
- GUI 的下载和训练后台任务使用隐藏窗口策略；从已经打开的终端手工启动时，父终端是否保持开启
  由用户的启动方式决定。
- 安装、升级默认保留本地数据；卸载时可以在向导中单独确认是否删除数据。

## 隐私与数据边界

- 默认关闭遥测、崩溃上传和使用统计。
- 数据、模型、股票池、结果和诊断信息默认保存在本机。
- BaoStock 连接只在用户发起数据更新时发生；版本检查需要用户主动开启。
- 标准数据是否可随介质再分发取决于对应许可；没有书面依据时，请导入自己的 CSV 或在本机更新数据。
- `NON_PIT_FALLBACK` 等研究路线会持续显示风险提示，避免将不同历史口径混用。

## 已知边界

- Windows 10 22H2、WSLg 和实验性 NVIDIA 路径属于 best-effort；Windows 10 专用机器记录仍需单独验证。
- Linux 发布包以 Ubuntu 22.04/glibc 2.35 为兼容基线；Ubuntu 24.04 本地调试包不替代正式发行包。
- BaoStock 服务可用性、数据覆盖、许可和网络质量由上游与用户环境决定。
- 公开预发布状态会在数据权益与发行审核完成后再转为正式稳定版。

## 升级与卸载

- 安装版：运行新版安装程序覆盖安装。
- 便携版：替换旧的可执行文件即可。
- 默认数据目录：Windows `%LOCALAPPDATA%\Quintara`，Linux `~/.local/share/quintara`。
- 卸载默认保留数据，重新安装后可继续使用；删除数据需要在卸载流程中明确确认。

## 获取帮助

- 首次使用：[`docs/FIRST_USE.md`](FIRST_USE.md)
- Linux/Windows 操作与排错：[`README.md`](../README.md)、[`docs/OPERATIONS.md`](OPERATIONS.md)
- CSV 字段：[`docs/CSV_FIELD_DICTIONARY.md`](CSV_FIELD_DICTIONARY.md)
- 隐私：[`docs/PRIVACY.md`](PRIVACY.md)
- 数据与研究边界：[`docs/LEGAL_NOTICE.md`](LEGAL_NOTICE.md)

欢迎通过 GitHub Issue 提交安装、数据、界面或结果展示方面的反馈。
