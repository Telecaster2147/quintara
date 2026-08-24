# 贡献者测试、视觉审阅与稳定版清单

## 本地快速门禁

```bash
UV_CACHE_DIR=/tmp/quintara-uv-cache uv run ruff check src tests packaging
UV_CACHE_DIR=/tmp/quintara-uv-cache uv run python packaging/typecheck.py
UV_CACHE_DIR=/tmp/quintara-uv-cache uv run pytest --junitxml=dist/pytest.xml
find src/quintara/qml -name '*.qml' -print0 | xargs -0 .venv/bin/pyside6-qmllint -I src/quintara/qml
# Linux release builder must be Ubuntu 22.04 / glibc 2.35 or older
UV_CACHE_DIR=/tmp/quintara-uv-cache uv run python packaging/elf_compat_audit.py --max-glibc 2.35
```

GUI 测试必须使用隔离内容根、`objectName`/`Accessible.name` 语义定位和 `fixtures/manifest.json` 固定身份。offscreen 是快速预检；候选发布仍需原生窗口、安装器和干净用户会话。

## 视觉基线审阅

运行 `packaging/visual_matrix.py` 生成 36 张浅/深主题、最小/标准窗口、首次向导、七页面与失败状态截图。审阅者逐张确认：标题与唯一主要动作、无截断/重叠、空白平衡、44 px 点击目标、键盘焦点、状态文字不只依赖颜色、技术详情不抢占业务信息。更新基线必须记录旧/新 SHA-256 和原因，禁止仅因测试失败而覆盖。

## 候选发布清单

1. 单元、属性、差分、合同、GUI、CLI、恢复与类型/lint 全绿；
2. provider 与 CSV 两条完整旅程、取消/恢复/重复启动/过期旅程通过；
3. Windows 11、Ubuntu 22.04/24.04、Debian 12/13 和 WSLg 原生窗口证据齐全；
4. Windows 安装器/便携包、Linux 发行物、GUI/CLI、升级/卸载和无控制台 smoke 通过；Linux bundle 的 glibc 基线审计通过；
5. `packaging/test_matrix.py` 汇总本地单元/属性/合同/GUI/CLI/恢复/视觉检查；`packaging/openspec_audit.py` 检查全部 OpenSpec 场景 ID 与证据矩阵的双向覆盖；
6. SBOM、法律/许可审阅、发行物哈希、生产 fixture、截图与 known items 写入 release evidence；未完成的原生平台或必需审阅门禁保持 `pre-release`。产品所有者确认不作为独立签字字段。
7. 生产 channel 凭证/再分发依据齐全或明确保持空 channel；
8. catalog 上一指针回滚演练成功后，才写候选版本标记。
