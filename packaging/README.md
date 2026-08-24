# Packaging

发布机先执行 `uv sync --all-groups`，再在 release environment 安装 PyInstaller：

```bash
uv pip install pyinstaller
uv run python packaging/build_release.py
uv run python packaging/sbom.py
uv run python packaging/release_evidence.py
```

输出 `dist/Quintara[.exe]` 是 Python-free one-file bundle：

- Linux 使用 `./packaging/install_linux.sh` 安装到 `$HOME/.local`；
- Windows 使用 Inno Setup 编译 `packaging/windows/Quintara.iss`。

`dist/sbom.json` 和 `dist/release-evidence.json` 随发布候选一起保存，分别记录依赖许可
元数据以及 commit、锁文件、测试夹具和 OpenSpec 任务的哈希闭包。

安装包不包含用户数据、账户、token 或训练结果。首次启动后数据目录由应用创建。
