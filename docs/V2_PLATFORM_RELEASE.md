# v2 平台、安装与发布门禁

## 支持矩阵

原生目标为 Windows 11 x86-64、Ubuntu 22.04/24.04、Debian 12/13；Windows 10 22H2 与 WSLg 是 best-effort。`detect_display_environment` 在创建 Qt 应用前区分 Windows、Wayland、X11、WSLg 和纯终端；Wayland socket 不可用时回退 XCB。纯终端使用独立 `quintara-cli`。

PyInstaller 清单显式携带 QML、图像、模型配置和法律材料；Qt hook 携带平台插件。Windows GUI 使用 GUI PE 子系统，CLI 使用控制台子系统。安装器、PE、Qt 窗口、桌面和开始菜单使用同一多分辨率 ICO。升级保留数据目录；卸载默认保留，删除数据必须单独勾选并二次确认。

Linux 可分发 one-file bundle 固定在 Ubuntu 22.04（glibc 2.35）构建，作为 Debian 12/13 与 Ubuntu 22/24 的最低 ABI 基线。`packaging/elf_compat_audit.py --max-glibc 2.35` 检查构建 Python shared library，并把构建平台、解释器 ABI 和发行物哈希写入 `dist/build-metadata.json` 与 `dist/elf-compatibility.json`；Ubuntu 24 本地调试产物不得直接冒充跨发行版发布物。

## 原生验收

每个平台在隔离用户目录执行安装、首次向导、数据目录选择、升级、卸载、GUI 与 CLI smoke。Windows 干净会话运行 `packaging/windows/smoke.ps1` 与 `install_smoke.ps1`，并用 UI 自动化/Process Explorer 证明 GUI 及下载/训练子进程不出现 PowerShell、Windows Terminal 或控制台窗口，同时回归 CLI stdout、stderr、退出码和管道；安装脚本还调用 `SHChangeNotify` 刷新图标缓存并记录 PE 哈希。

真实窗口矩阵覆盖浅/深主题、100/125/150/200% DPI、960×640 最小窗口，以及向导、首页、数据、股票池、训练、结果、错误/空状态。结构门禁检查文本截断、重叠、44 px 点击目标、焦点环、辅助名称和非纯颜色状态。

## 发布证据与法律材料

`packaging/sbom.py` 生成 CycloneDX 依赖与许可清单；`THIRD_PARTY_NOTICES.md` 收录 Qt/PySide6、LightGBM、安装器与数据材料。`release_evidence.py` 记录平台、发行物 SHA-256、fixture 身份、JUnit、旅程和截图。免责声明、隐私、风险与第三方法律材料由工程记录覆盖；发布判断使用可复现证据，不设置独立审阅或发行负责人签字字段。应用永久关闭遥测。

各原生 runner 使用 `packaging/native_evidence.py` 记录平台、发行物哈希和验收范围；收集 CI artifacts 后执行 `python packaging/native_evidence.py --merge`，生成 `dist/native-platform-evidence.json`，再运行 `candidate_gate.py --strict`；严格模式只检查机器可读工程证据。

`.github/workflows/platform-matrix.yml` 的 `aggregate-evidence` job 会自动下载各平台记录，优先采用 Ubuntu 22.04 builder 的 bundle/ABI 文件，安装固定版本 OpenSpec validator，重跑 OpenSpec、图标、法律、回滚和本地矩阵检查，并上传汇总的 `candidate-gate.json` 与 `release-evidence.json`。原生 job 尚未提供记录时，聚合 job 保留缺失项并继续输出 `pre-release` 证据。
