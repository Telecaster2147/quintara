# 发布清单与证据

此页是 release candidate 的门禁索引；勾选项必须对应本机命令、GitHub Actions 运行或
`dist/release-evidence.json`，不以手工描述替代证据。

## 本地可重复门禁

- [x] `uv lock --check`
- [x] Ruff、`packaging/typecheck.py`、pytest（含 Hypothesis 与 BaoStock fake）
- [x] OpenSpec `validate --strict --all`
- [x] wheel 构建、版本命令、CLI doctor/bootstrap/csv smoke
- [x] PyInstaller Linux bundle：`--version`、doctor、offscreen GUI 等待烟测
- [x] SBOM、第三方 notice、机器可读 release evidence

## CI / 原生安装门禁

- [x] Ubuntu/Windows CI 运行在最终提交 SHA（ruff、pytest、ty、uv build）
- [x] Linux prefix 安装与 wheel smoke（Package workflow）
- [x] Windows PyInstaller、Inno Setup installer smoke（Package workflow）
- [ ] 全新主机导入→训练→结果导出与卸载/重装保留策略

## 已验证的远程运行

Quintara 0.1.0 的发布源提交为 `59bf5def9ca36d6957998b2b45a616c1237e48ed`：

- Quintara CI：运行 [`32693975329`](https://github.com/Telecaster2147/quintara/actions/runs/32693975329)，Ubuntu、Windows、OpenSpec 门禁全部通过。
- Package smoke：运行 [`32694000601`](https://github.com/Telecaster2147/quintara/actions/runs/32694000601)，Linux prefix/wheel 与 Windows PyInstaller/Inno Setup 全部通过。
- GitHub Release：[`v0.1.0`](https://github.com/Telecaster2147/quintara/releases/tag/v0.1.0) 已发布 Windows 安装版、Windows 便携版、Linux x86-64 压缩包和 SHA-256 校验文件。

## 发布前人工复核

- [x] 发布包不含 `.env`、账户、token、绝对开发路径或历史真实行情；不默认携带遥测。
- [x] `LICENSE`、Qt/PySide6、LightGBM、BaoStock、PyInstaller/Inno notice 已列出。
- [x] PIT、CUSTOM、NON_PIT_FALLBACK 路线与固定 Top-5 权重在结果中可见。
- [x] 版本检查默认关闭；诊断导出只写本地脱敏 JSON/ZIP。

本页只记录发布证据；运行时的机器可读证据由
`dist/release-evidence.json` 随对应构建生成。
