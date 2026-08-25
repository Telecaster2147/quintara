# v2 OpenSpec 双向证据矩阵

| Requirement | 实现 | 主要验证证据 |
|---|---|---|
| FRC-001–006 | `onboarding.py`, `OnboardingDialog.qml`, `QmlBackend` | versioned five-section consent、path persistence、QML shell/DPI tests |
| PPD-001–007 | `provider.py`, `data_lifecycle.py`, `bundled_data.py`, reference-result gate | package schema/corruption tests；`developer-data-journey.json` byte-identical result evidence |
| PPD-008–011 | `data_lifecycle.py`, `service.py`, `QmlBackend`, BaoStock preview dialog | `test_baostock_one_click.py` 三来源派生、PIT 变化/退市保留、远端交易日、OHLC 失败原子性；QML shell tests |
| DPE-001–003 | QML Theme/AppShell/Workspace/components, DTO/ViewModels | qmllint、shell/contrast/theme persistence、36 图矩阵 |
| DPE-004–005 | `universe.py`, service/app use cases, searchable DataTable, strategy policies | universe edit/100只门禁/default strategy tests |
| DPE-006–008 | theme tokens, DPI subprocess tests, single-instance launcher, icon exporter | 125–200% smoke、ICO structure/review manifest、WSLg smoke |
| LRO-001–005 | `JobCoordinator`, `JobContext`, atomic publication/recovery | Hypothesis progress、transition/idempotency/cancel/recovery、publication fault tests |
| LRO-006 | BaoStock request identity/checkpoint、GUI stage signals | checkpoint identity assertions、cancel/failure publication tests |
| RRW-001–005 | result DTO/QML DataTable, manifests, history filters, atomic export | five-stock service/GUI journeys、identity mutation、overwrite/hash tests |
| DRE-001 | display probe/repair, PyInstaller specs, platform workflows | Ubuntu 24.04 bundle、real WSLg smoke、Debian 12 CLI probe；CI native platform jobs |
| DRE-002–003 | `GuiHarness`, Linux journey, developer-data journey, visual matrix | `linux-user-journey.json`, `developer-data-journey.json`, result/onboarding captures, structural QML checks |
| DRE-004–006 | split GUI/CLI specs, sidecar-aware Inno/Linux installers, icon and subprocess policy | bundle/install smoke、Windows smoke script、sidecar packaging tests、`dist/icon-release-audit.json`、`packaging/elf_compat_audit.py`、`packaging/candidate_gate.py` |

反向检查：`tests/test_contracts_v2.py` 对应 FRC/PPD/RRW 身份闭包；`tests/test_v2_product_infrastructure.py` 对应 PPD/LRO/DRE；`tests/test_qml_product_shell.py` 对应 FRC/DPE/DRE；`packaging/linux_user_journey.py` 与 `packaging/developer_data_journey.py` 对应 DRE-002/004/005；`packaging/rollback_drill.py` 对应 catalog 回滚。`packaging/test_matrix.py` 汇总单元、属性、合同、GUI、CLI、恢复和本地视觉检查，`packaging/openspec_audit.py` 对全部 37 个需求 ID 做双向覆盖检查。正式 Linux release 必须在 Ubuntu 22.04/glibc 2.35 builder 通过 ABI 审计；原生平台证据缺少时 DRE-001/004/005 保持候选门禁，offscreen 结果只作为快速预检；`candidate_gate.py` 和 `dist/release-evidence.json` 将这些状态明确标为 `pre-release`。
