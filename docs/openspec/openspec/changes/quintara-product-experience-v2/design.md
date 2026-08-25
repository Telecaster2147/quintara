## Context

参见 [proposal.md](proposal.md) 的动机。当前产品的 Python 应用服务、数据生命周期和训练适配已具备骨架，但桌面端把配置对象和 JSON 直接映射到 Qt Widgets 标签页；长任务缺少统一状态，安装包未建立供应方生产数据交付合同，Linux/WSLg smoke 也未覆盖真实可见窗口。

本设计受以下边界约束：业务和数据处理保持本地；GUI 与 CLI 复用一个应用服务；Windows 11 为主平台，Ubuntu/Debian 为保证平台，WSLg 作为真实 Linux GUI 场景；CPU 路径为权威；`PIT_BASELINE`、`CUSTOM_UNIVERSE`、`NON_PIT_FALLBACK` 的数据、模型和结果身份严格隔离。

## Goals / Non-Goals

**Goals:**

- 将呈现、用户任务状态与领域服务分层，使 GUI 美化不复制业务逻辑。
- 以版本化、可校验、可原子回滚的数据包交付开发者参考数据，并让 BaoStock 增量更新接续该数据。
- 为所有长任务建立同一状态机、持久化进度和恢复边界。
- 将 Top-5、数据截止日、模式身份与风险说明置于结果主视图。
- 用真实窗口、语义交互、视觉基线和故障注入建立稳定版证据。

**Non-Goals:**

- 本轮不重写训练内核或改变因子工程。
- GUI 进程不承载 HTTP 服务，CLI 也不通过 GUI 自动化实现。
- 设计系统不依赖在线 Figma 文件才能构建。
- v2 迁移不修改已发布数据内容；只在身份完整时建立索引或引用。

## Decisions

### 1. PySide6 + Qt Quick/QML 作为发布呈现层

发布 GUI 使用 `QGuiApplication`/`QQmlApplicationEngine`、Qt Quick Controls 2 与仓库内 QML 组件；Python 通过窄 ViewModel/Controller 接口暴露只读状态、命令和通知。训练、数据、配置和文件系统逻辑留在应用服务，QML 不直接访问数据库、网络或内核。

理由：Qt Quick 更适合状态驱动页面、响应式布局、设计令牌、动画和截图测试；仍复用现有 PySide6 打包链与 Python 服务。发布样式使用 Qt Quick Controls `Basic` 作为可预测的跨平台基础，再由语义令牌构建 Fluent 2 风格的桌面层级，避免不同系统原生样式造成尺寸和截图漂移。

备选方案：继续深修 Qt Widgets，迁移量较低，但响应式布局、状态视图和视觉系统会持续依赖大量命令式样式；嵌入 WebView 与既定“无 WebUI/HTTP”定位冲突；Electron 会扩大运行时和双技术栈成本。

### 2. UI 架构采用 Shell—Page—ViewModel—Application Service

组件边界如下：

```text
QML Shell / Design System
  ├─ Onboarding, Home, Data, Universe, Train, Results, History
  └─ Settings, Diagnostics, TechnicalDetailsDrawer
                 │ signals / commands / immutable DTOs
Python ViewModels & Navigation Coordinator
                 │ application use cases
ApplicationService / JobCoordinator / DatasetCatalog
                 │ domain ports
Data providers, validators, kernel adapter, artifact repositories
```

- QML Shell 只负责导航、布局、主题和对话框宿主。
- 每页 ViewModel 暴露页面级 `loading/ready/empty/error` 状态与领域 DTO，提交命令返回任务 ID。
- ApplicationService 保持 GUI/CLI 的共同入口，任何 GUI 特有状态不得进入内核 manifest。
- 绝对路径、枚举和技术日志经 `TechnicalDetailsDTO` 脱敏后进入抽屉；默认页面只接收用户视图模型。

备选方案：QML 直接调用既有 Python 对象，可快速显示数据，但会再次把内部模型泄漏为 UI 合同，并让测试依赖实现细节。

### 3. 信息架构和设计令牌固定为产品合同

主窗口最低尺寸 960×640，推荐 1200×760。左栏宽 224dp，紧凑态 72dp；内容区使用 8dp 基础间距、12/16/24dp 圆角层级、最小 36dp 控件高度。字体通过 Qt 系统中文字体回退，正文以 14–16sp 等效尺寸为主，标题和辅助文本使用语义字号而非统一 9pt。

导航顺序固定为：首页、数据、股票池、训练、结果、历史；设置和诊断置底。每页最多一个高强调主操作，危险操作使用确认层。颜色按 `surface/onSurface/primary/success/warning/error/focus` 等语义角色定义，浅色、深色和高 DPI 共享度量令牌。状态同时使用图标、标题和文字。

主页状态卡从领域快照派生：数据、活动股票池、模型、最近结果。每张卡回答“当前是什么、是否就绪、下一步是什么”。首次向导使用相同页面组件和领域状态，避免形成第二套逻辑。

### 4. 供应方生产数据采用发布目录 + 内容寻址清单

供应方发布端提供一个轻量 channel 索引和不可变版本目录：

```text
channel.json
releases/<dataset-version>/
  manifest.json
  manifest.sig                 # 发布通道启用签名时存在
  market/*.parquet|csv.zst
  extra_features/*.parquet|csv.zst
  membership/pit_intervals.*
  reference/{calendar,securities}.*
  licenses/*
```

`manifest.json` 至少包含：`schema_version`、`dataset_version`、`created_at`、`cutoff_date`、日期/证券覆盖、`pipeline_identity`、模式身份、标签兼容范围、各文件大小与 SHA-256、总解包预算、来源与许可条款。大 CSV 在交付层可压缩或分片，本地规范化后再由训练适配器读取；“标准生产数据”指内容和管线身份，而非强制单一文件格式。

下载器先获取 channel 与 manifest，完成许可、兼容性、PIT 材料、可写性和空间预算预检；随后写入 `.downloads/<version>/`，以 ETag/长度/分块哈希判断续传条件。全部校验后转入 generation 暂存目录，写完成标记，再通过替换活动引用原子发布。安装介质内置数据走同一导入器和 manifest 检查。

BaoStock 更新以活动 generation 为基底，只写新 generation；行情、extra features、PIT 成分分别保留 provenance entry。PIT 计划在行情传输前解析完毕。更新不会在原目录追加后就直接训练。

备选方案：安装器直接解压一个未版本化大 CSV，首次体验简单，但升级、续传、来源、损坏恢复和 PIT 身份都缺少稳定边界。

### 5. 本地存储按来源、模式和 generation 分层

使用 Qt 标准应用数据目录，允许用户在首次向导中更换大数据根目录；配置和索引留在标准目录，内容根可位于其他磁盘。

```text
<app-data>/
  config/settings.json
  legal/acceptances.json
  catalog/catalog.sqlite
  jobs/<job-id>/{state.json,events.jsonl,logs/}
  diagnostics/
<content-root>/
  downloads/<dataset-version>/
  datasets/<source-id>/<mode-id>/<generation-id>/
    manifest.json
    READY
    data/...
  models/<mode-id>/<universe-id>/<generation-id>/<model-id>/
  results/<mode-id>/<universe-id>/<run-id>/
  exports/
  staging/<job-id>/
```

`mode-id` 取 `PIT_BASELINE`、`CUSTOM_UNIVERSE`、`NON_PIT_FALLBACK`。模型 manifest 绑定 dataset generation、universe identity、kernel contract、label contract、strategy policy 和参数；结果再绑定 model identity 与法律声明版本。目录只是物理布局，catalog 中的活动引用才代表发布状态。

用户 CSV 导入后复制或规范化到受管 generation，同时保存原始 SHA-256、只读检查报告和字段映射；原文件保持原样。大文件复制前也执行空间预算。

### 6. 长任务采用事件日志驱动的可恢复状态机

`JobCoordinator` 是单一任务写入者，以状态快照 + 追加事件日志持久化：

```text
PLANNING → READY → RUNNING → SUCCEEDED
                     ├──→ CANCELLING → CANCELLED
                     ├──→ FAILED
                     └──→ RECOVERABLE
RUNNING → PAUSING → RECOVERABLE       # 可续传下载
```

任务由阶段组成，每阶段声明：进度类型（确定总量/阶段型）、可停止点、暂存产物、重试幂等键和发布边界。UI 订阅状态快照，不从日志文本推断进度。CLI 的命令输出引用相同 job ID。

应用退出先向活动任务发送协作式取消；超时后由用户决定继续等待或强制结束。启动恢复扫描 `RUNNING/CANCELLING` 快照和 staging：下载可进入 `RECOVERABLE`，内核训练默认清理未发布模型后进入 `CANCELLED`，已完成校验但尚未切换引用的产物可恢复发布。

### 7. 训练标签和策略保持版本化边界

内核适配器维持两个明确标签合同：

- `competition-open-open-v1`：开发者参考数据的 open/open 复现合同，用于固定数据版本的结果一致性检查。
- `quintara-close5-open1-v1`：产品默认 `close(T+5) / open(T+1) - 1`，交易日历驱动，用于面向用户的训练和结果。

任何 dataset/model/result manifest 都写入标签合同，适配器在训练前执行闭包校验。开发者参考数据按其清单声明的 open/open 合同和完整历史训练，并对包内参考结果逐行与哈希核对；其他用户数据继续按所选产品标签构造目标，两者身份隔离。

“激进、稳健平衡、保守”由版本化 `strategy_policy` 约束允许调整的打分聚合、波动/回撤惩罚和集中度；Top-5 固定权重保持不变。默认键显式写为 `balanced`，不依赖字典或字母排序。

### 8. 平台适配在启动前探测而非崩溃后解释

启动器在创建 Qt 应用前探测 Windows、X11、Wayland、WSLg 和纯终端环境：

- Windows 使用随发行物打包并经 smoke 验证的 Qt 插件集合。
- Linux 检查 `XDG_RUNTIME_DIR` 权限、`WAYLAND_DISPLAY`、`DISPLAY`、平台插件和 XCB 运行库；Wayland 条件完整时优先 Wayland，否则选择已验证 XCB。
- WSLg 使用其运行时套接字和实际环境探测，不硬编码单一后端。
- 纯终端环境由 CLI 正常工作；显式 GUI 请求返回结构化诊断。

诊断数据进入本地报告并脱敏。平台插件、QML 模块、字体和图像资源由打包清单显式列出，CI 对解包后的发行物进行导入和真实窗口检查。

### 9. 测试分成组件、合同、旅程和发行物四层

1. **组件层**：QML 组件状态、主题、焦点、辅助名称、ViewModel 单元测试；Python 领域服务保持既有测试。
2. **合同层**：manifest schema、哈希、续传身份、空间预算、状态机属性测试、PIT/非 PIT 隔离、标签合同差分夹具。
3. **旅程层**：Qt Quick Test 与语义驱动 GUI 自动化覆盖首次向导、两类数据、股票池、训练、停止、Top-5、历史和导出；断言页面文本及产物。
4. **发行物层**：Windows 安装器/便携包、Linux 包与 WSLg 真实窗口；截图矩阵覆盖主题、DPI、窗口尺寸和错误状态。offscreen smoke 只做分钟级预检。

网络测试使用本地可控发布端和 BaoStock adapter fixture，注入断网、ETag 改变、损坏分块、磁盘不足和取消。至少一条受控夜间任务连接真实 BaoStock，以发现协议漂移，并且不把其波动作为单元测试依据。

### 10. Windows 桌面入口与 CLI 分离，品牌资源单源派生

当前 Windows 打包链把唯一 `Quintara.exe` 设为 PyInstaller `console=True`，Inno Setup 的桌面和开始菜单快捷方式又直接启动该文件并附加 `gui` 参数。`gui` 只影响 Python 应用路由，不改变 Windows PE 子系统，因此桌面启动仍会附着或创建控制台宿主；用户把该宿主或启动它的父终端识别为常驻 PowerShell。仓库中没有由安装器快捷方式调用的 PowerShell 包装脚本，根因属于可执行文件子系统与入口复用，而非 QML/Widgets 窗口生命周期。

Windows 发行物采用两个显式入口：

- `Quintara.exe`：`WINDOWED`/无控制台子系统，作为安装器、桌面、开始菜单、文件属性和 GUI 单实例协议的唯一目标；启动即进入 GUI，不再依赖 `gui` 参数改变窗口类型。
- `quintara-cli.exe`（最终名称在实现时固定）：控制台子系统，保留标准输入输出、退出码、管道、自动化和诊断能力；与 GUI 调用相同 Python 应用服务。
- 源码与 wheel 使用 `quintara-gui` 的 `gui-scripts` 入口进入同一 `qml_gui.main`，支持 `--root` 隔离内容目录；`quintara`/`quintara-cli` 保持终端入口，旧 Widgets 模块只作为历史对照夹具。

GUI 启动的 Windows 子进程统一经过平台端口，使用 `CREATE_NO_WINDOW`、`DETACHED_PROCESS` 或经验证的等价语义，并捕获标准输出到任务日志；CLI 从已有终端启动时继续继承调用方控制台。验收同时检查可见窗口和进程树，避免仅凭主窗口出现而遗漏闪现/常驻控制台。

品牌母版采用无文字的圆角方形轮廓，深海军蓝—青色为主、克制金色标识最高排序，把分析罗盘与五档递增组合合并为核心主形。母版保留安全边距和简化小尺寸变体，由可重复资源脚本派生包含 16/20/24/32/48/64/128/256 像素的 Windows `.ico`；16–32 像素版本减少高光、细刻度和阴影，优先保证轮廓。相同资源版本写入 PE 图标、Qt 窗口图标、Inno Setup、桌面/开始菜单快捷方式和安装器视觉，并记录来源、许可与生成哈希。

### 11. 开发者数据采用应用旁 sidecar，活动数据进入用户工作目录

发布仓库保存 `quintara-developer-data-v1.zip`。Windows 安装器、Windows 便携 ZIP、Linux tar 和 Linux 前缀安装都把它放在可执行文件相邻目录树的 `data/developer/`；应用以冻结可执行文件目录、PyInstaller 解包目录和源码仓库目录的顺序发现数据，也允许开发者通过 `QUINTARA_DEVELOPER_DATA` 显式覆盖。原始 sidecar 不复制到 AppData。

导入器对 ZIP 路径、清单、每个文件大小和 SHA-256 执行相同检查，再把规范化数据原子发布到用户选择的内容根。路径摘要来自当前服务、活动 generation 和持久化的最近导入/导出记录；内容根迁移完成后重建服务并立即让 GUI 与应用用例引用新根。

参考数据使用完整可用历史、清单声明的 300 成员 PIT 门禁和固定训练参数。`reference-result.csv` 同时作为校验文件进入清单；实际结果必须在股票、顺序、权重与 CSV SHA-256 上全部一致。此检查位于结果发布之前，因此任何漂移都只留下失败任务和诊断信息。

### 12. BaoStock 初始化与三来源更新采用“预览—暂存—派生发布”

首次向导将来源固定为安装包、BaoStock、CSV 三选一；来源对象保持只读，活动 generation 是训练唯一输入。BaoStock 预览先登录、读取交易日历，并以 `sh.000300` 日线探测确认远端实际完整截止日；增量起点只取当前截止日之后的第一个有效交易日。预览 DTO 展示当前/目标身份、证券数、交易日数、字段、单位、后复权口径、预计行数与字节、内容根和模型过期影响。

`PIT_BASELINE` 对每个新增交易日查询历史成分快照，将连续出现压缩为 `[start_date,end_date]`，以旧截止日续接开放区间；移出证券闭合区间但保留行情与 listing，加入证券开启新区间。`CUSTOM_UNIVERSE` 严格跟随用户当前代码集合，保持继续存在的开放区间、闭合移除代码并为新增代码建立区间。远端代码始终转换为 `sh.XXXXXX`/`sz.XXXXXX`/`bj.XXXXXX`，基础资料不按当前上市状态过滤。

请求身份由连接器版本、代码集合、起止交易日、行情/估值字段、`adjustflag=3` 和股票池路线共同哈希。每只证券下载后原子更新检查点；所有新行与旧活动 generation 合并后执行重复键、日期边界、OHLC、PIT 重叠、字段、单位和复权合同检查。安装包或 CSV 更新发布为 `source=baostock` 的派生 generation，记录父 generation、原来源和合同复核；原 ZIP、CSV、旧 generation、模型和结果均保持不可变。活动指针仅在完整发布后切换，无新增交易日时返回 no-change 且不使模型过期。

## Risks / Trade-offs

- **[QML 迁移扩大短期改动面]** → 先固定 Python 应用服务合同和 DTO，再按页面垂直迁移；旧 Widgets 只保留为短期对照夹具，不进入最终发行入口。
- **[自带生产数据体积使安装包过大]** → 同时发布精简安装包与带数据离线介质，两者引用同一不可变 manifest；产品页清楚标注大小和截止日。
- **[供应方数据许可限制再分发]** → 发布流水线把许可审查作为数据 channel 门禁；许可尚未覆盖的版本仅进入受控下载通道并展示条款。
- **[BaoStock 字段或限流变化]** → adapter 版本化、先做小请求能力探测、支持指数退避和恢复，不在原 generation 就地写入。
- **[截图测试在字体和渲染后端间漂移]** → 固定 CI 字体与渲染环境，视觉阈值配合结构断言，差异超阈值进入人工审阅而非自动更新基线。
- **[本地大文件迁移耗时与空间压力]** → 建立内容根迁移计划、预估双份空间、提供校验后切换与旧目录延后清理。
- **[策略名称让用户误解为收益档位]** → 每个策略同时展示模型风险偏好说明，结果保留研究措辞和统一风险声明。
- **[GUI/CLI 双入口增加打包体积或配置漂移]** → 两个入口共用冻结模块、应用服务和版本资源，只分离 Windows 子系统及入口路由；发行物测试比较版本、依赖和存储身份。
- **[复杂图标在 16px 失去辨识度]** → 从同一母版维护简化小尺寸导出，使用轮廓/灰度/深浅背景矩阵人工审阅，不把 1024px 缩放结果直接视为通过。
- **[Linux bundle 在较旧发行版启动失败]** → 正式 Linux 包只从 Ubuntu 22.04/glibc 2.35 builder 发布；`elf_compat_audit.py` 检查 Python shared library ABI，Ubuntu 24 产物只作为本地窗口调试证据。
- **[候选状态被部分证据误标]** → `candidate_gate.py` 汇总任务、原生平台、ABI、图标、法律材料、回滚和制品证据。默认只生成 `pre-release`，`--strict` 用于发布流水线的完整证据检查。
- 原生 runner 通过 `native_evidence.py` 记录自身平台和发行物哈希，收集 artifacts 后合并为 `native-platform-evidence.json`，避免用单一 offscreen 主机推断全矩阵。

## Migration Plan

1. 固化现有应用服务、CLI、manifest 和内核差分测试，建立 v1 只读兼容 fixture。
2. 引入 QML 设计系统、Shell 和 ViewModel 边界；先接环境/首页，再迁移数据、股票池、训练、结果和历史。
3. 引入 dataset catalog、供应方 manifest schema、下载/导入器和 generation 原子发布；用小型生产合同 fixture 打通全旅程。
4. 将既有 BaoStock、CSV、训练和预测接入 JobCoordinator，完成停止和启动恢复。
5. 对旧数据目录执行只读扫描：身份完整的 generation 建立 catalog 索引；身份不足的内容标为“需要重新验证”，继续保留原文件。
6. 发布预览版并并行运行 v1 内核夹具与 v2 产品旅程；达到全部门禁后切换发布入口。
7. 回滚时恢复上一发行物和 catalog 活动引用；v2 新 generation 保持不可变，旧版本只读取其认识的 manifest schema。

## Open Questions

- 生产数据首个正式 channel 的托管域名、CDN 和签名公钥由发布基础设施阶段确定；本设计已固定其清单与验证接口。
- 首个离线介质采用完整历史包还是最近三年包，由许可与发行物体积测量决定；两者遵循相同用户选择和 generation 合同。
