# Packaging

发布机先执行 `uv sync --all-groups`，再在 release environment 安装 PyInstaller：

```bash
uv pip install pyinstaller
uv run python packaging/build_release.py
uv run python packaging/elf_compat_audit.py --max-glibc 2.35
uv run python packaging/sbom.py
uv run python packaging/icon_release_audit.py
uv run python packaging/legal_review.py
uv run python packaging/openspec_audit.py
uv run python packaging/candidate_gate.py
uv run python packaging/rollback_drill.py
uv run python packaging/native_evidence.py --platform ubuntu-22.04
uv run python packaging/native_evidence.py --merge
QT_QPA_PLATFORM=offscreen uv run python packaging/test_matrix.py
uv run python packaging/release_evidence.py
```

输出两个职责分离的 Python-free one-file bundle：

- `dist/Quintara[.exe]`：桌面 GUI；Windows 使用 `console=False` 的 GUI PE 子系统，桌面/开始菜单启动时不创建 PowerShell 或控制台窗口。
- `dist/quintara-cli[.exe]`：控制台 CLI；保留标准输入输出、退出码、重定向和管道语义。
- 源码/wheel 环境使用 `quintara-gui`（`gui-scripts`）启动 QML GUI；`quintara` 与 `quintara-cli` 保持终端入口。

- Linux 使用 `./packaging/install_linux.sh` 安装到 `$HOME/.local`；
- Windows 使用 Inno Setup 编译 `packaging/windows/Quintara.iss`。

`dist/sbom.json` 和 `dist/release-evidence.json` 随发布候选一起保存，分别记录依赖许可
元数据以及 commit、锁文件、测试夹具和 OpenSpec 任务的哈希闭包。

正式 Linux release job 使用 Ubuntu 22.04 构建机。Ubuntu 24/WSLg 产物用于本地调试和窗口验收；如果 `elf_compat_audit.py` 报告 Python ABI 超出 `2.35`，先切换到 Ubuntu 22.04 builder 再发布。

安装包不包含用户数据、账户、token 或训练结果。首次启动后数据目录由应用创建。

GUI 后台进程必须使用 `quintara.platform.subprocess_policy(gui_background=True)`；CLI 子进程使用默认策略继承调用终端。Windows 干净会话验收脚本记录在 `packaging/windows/smoke.ps1`，安装/卸载/图标缓存脚本记录在 `packaging/windows/install_smoke.ps1`。`test_matrix.py` 与 `openspec_audit.py` 产生本地测试及双向追踪证据；原生平台与制品证据未附前 release evidence 保持 `pre-release`。`candidate_gate.py --strict` 只在全部 OpenSpec 任务、原生矩阵、ABI、图标、法律材料和回滚演练均存在时返回候选通过，不读取独立签字字段。
