## Purpose

把真实桌面启动、安装、核心用户旅程、视觉适配和故障恢复转化为跨平台发布证据，防止仅凭 offscreen 进程存活判定产品可用。

## ADDED Requirements

### Requirement: 发布平台完成真实窗口启动
**DRE-001** 稳定版 SHALL 在 Windows 11 x86-64、Ubuntu 22.04/24.04、Debian 12/13 x86-64 启动真实可交互窗口，并在具备 WSLg 的环境验证 Wayland/XCB 选择、运行时目录与 Qt 插件依赖；Windows 10 22H2结果单独记录为 best-effort。

#### Scenario: WSLg 普通用户启动
- **WHEN** 用户从已安装或便携发行物启动 `Quintara` 图形入口
- **THEN** 应用自动选择可用 Qt 平台并显示主窗口，诊断页记录实际后端及依赖探测结果

#### Scenario: 纯终端 Linux
- **WHEN** 环境没有图形会话
- **THEN** `Quintara` CLI 保持完整可用，GUI 启动返回明确环境诊断与 CLI 入口提示

### Requirement: 核心旅程由真实交互验收
**DRE-002** 发布流水线 SHALL 在隔离用户目录中通过鼠标/键盘或 Qt 语义接口完成首次声明、两类数据来源、数据检查、股票池、训练、Top-5、历史和 CSV 导出，并断言用户可见文本、状态与产物内容。

#### Scenario: 供应方数据端到端旅程
- **WHEN** CI 使用小型但合同完整的生产数据 fixture
- **THEN** 自动化完成选择、获取、校验、本地训练和结果导出，并验证 manifest 身份与页面内容

#### Scenario: 用户 CSV 端到端旅程
- **WHEN** CI 导入合格 CSV fixture
- **THEN** 自动化完成检查、训练、预测和导出，同时证明源 CSV 哈希未变化

### Requirement: 视觉适配具有回归证据
**DRE-003** 稳定版 SHALL 对首次向导、首页、数据、股票池、训练中、结果和失败状态建立浅色/深色及关键 DPI 截图基线，并检查文本截断、重叠、空白失衡、点击目标和焦点可见性。

#### Scenario: 截图差异超阈值
- **WHEN** 关键页面截图与已审阅基线差异超出阈值
- **THEN** 发布门禁要求人工审阅并记录接受理由或修复证据

### Requirement: 安装与数据交付共同验收
**DRE-004** Windows 安装器、Windows 便携包和 Linux 发行物 SHALL 验证首次启动、快捷方式或入口、QML/Qt 资源、可选内置数据、联网数据下载、本地数据目录、升级保留、卸载边界和 CLI；许可证及法律材料 SHALL 随发行物可访问。

#### Scenario: 精简安装后下载数据
- **WHEN** 用户安装不含大数据包的发行物并选择供应方数据
- **THEN** 应用从受控发布端下载、校验并存入本地数据目录，卸载时按用户选择保留或删除该目录

#### Scenario: 离线安装介质含数据
- **WHEN** 用户使用包含生产数据的发行物且网络离线
- **THEN** 应用可导入并验证随包数据，显示其截止日且不宣称其为最新版本

#### Scenario: Linux 发行物使用最低 ABI 构建
- **WHEN** 发布流水线生成 Ubuntu/Debian x86-64 one-file 发行物
- **THEN** 构建必须来自 Ubuntu 22.04/glibc 2.35 或更旧 ABI builder，并通过 `elf_compat_audit.py` 后才进入跨发行版候选目录

### Requirement: 发布结论绑定证据
**DRE-005** 稳定发布 SHALL 汇总平台、发行物哈希、测试版本、数据 fixture 身份、旅程结果、截图审阅和已知 best-effort 项；任一核心平台安装、CPU 训练预测、恢复、GUI、CLI 或制品证据门禁失败时，候选版本保持预发布状态。发布判断不依赖独立审阅或发行负责人签字字段。

#### Scenario: offscreen smoke 通过但真实旅程失败
- **WHEN** 进程存活检查通过而真实窗口或用户旅程失败
- **THEN** 发布结论以真实旅程失败为准并关联日志、截图和复现步骤

#### Scenario: 候选 gate 缺少核心证据
- **WHEN** OpenSpec 任务、原生矩阵、ABI、图标、法律材料、回滚或制品证据任一项缺失
- **THEN** `candidate_gate.py --strict` 返回失败并列出 blocker，发布证据保持 `pre-release`

### Requirement: Windows GUI 与 CLI 使用独立启动身份
**DRE-006** Windows 发行物 SHALL 提供无控制台子系统的桌面 GUI 入口和保留标准输入输出的 CLI 入口；源码/wheel SHALL 提供 `quintara-gui` GUI script；桌面与开始菜单快捷方式 SHALL 直接指向 GUI 入口，GUI 启动及其后台子进程 SHALL NOT 创建或常驻 PowerShell、Windows Terminal 或控制台宿主窗口，且两个入口 SHALL 复用同一应用服务、版本和存储合同。

#### Scenario: 从桌面快捷方式启动
- **WHEN** 用户在无已打开终端的 Windows 会话中双击 Quintara 桌面快捷方式
- **THEN** 仅出现 Quintara 产品窗口，进程树和桌面上不出现伴随其生命周期的 PowerShell、Windows Terminal 或控制台窗口

#### Scenario: 从终端调用 CLI
- **WHEN** 用户在 PowerShell、Command Prompt 或自动化流水线中调用 Quintara CLI
- **THEN** CLI 在调用方终端中提供标准输出、标准错误、退出码和管道行为，不启动桌面窗口

#### Scenario: GUI 发起后台任务
- **WHEN** GUI 执行环境探测、下载、训练或预测并创建子进程
- **THEN** 子进程使用隐藏控制台的 Windows 创建标志或等价启动方式，任务状态仅通过 Quintara 界面呈现
