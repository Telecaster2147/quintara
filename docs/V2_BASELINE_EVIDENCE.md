# Quintara v2 implementation baseline

Recorded: 2026-08-24

This document freezes the reproducible starting point for OpenSpec change
`quintara-product-experience-v2`. It is evidence of the migration baseline,
not evidence that the v2 release gates have passed.

## Source and quality baseline

```text
pytest:       18 passed in 3.12s
ruff:         All checks passed
type checker: All checks passed
Trailmark:    Python; 1,601 nodes; 245 functions; 21 classes; 6 entry points
```

Commands:

```bash
UV_CACHE_DIR=/tmp/quintara-uv-cache uv run pytest
UV_CACHE_DIR=/tmp/quintara-uv-cache uv run ruff check src tests packaging
UV_CACHE_DIR=/tmp/quintara-uv-cache uv run python packaging/typecheck.py
trailmark analyze --language auto --summary .
```

## Current desktop presentation

The release UI is a `QMainWindow` with eight `QTabWidget` tabs. The default
overview exposes the raw bootstrap JSON and a technical data-root path. It has
no left navigation, page DTO boundary, responsive compact mode, or QML design
system.

Offscreen baseline screenshot:

- [`evidence/v1-widgets-home.png`](evidence/v1-widgets-home.png)
- Resolution: 1120×720
- SHA-256: `6caddc990f0d6a552b08fcd253a7730f8a8d3de39b0ce01fe6e97735212f3ded`

Reproduce:

```bash
QT_QPA_PLATFORM=offscreen uv run python -c \
  'from PySide6.QtWidgets import QApplication; from quintara.gui import MainWindow; a=QApplication([]); w=MainWindow("/tmp/quintara-v1-baseline"); w.show(); a.processEvents(); assert w.grab().save("v1-widgets-home.png")'
```

## Platform baseline

- Native Linux CLI and offscreen Widgets startup are covered by existing CI.
- The release workflow now builds Linux bundles on pinned Ubuntu 22.04 and
  keeps Ubuntu 24.04, Debian 12/13 and Windows native-window evidence as
  separate matrix records.
- The current execution environment is WSL2 Ubuntu 24.04 with partial WSLg
  evidence. Reproduce the full WSLg run with `quintara doctor` followed by
  `quintara-gui`, recording `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`,
  the selected Qt backend, and a visible window screenshot.
- Windows uses separate GUI-subsystem and console-subsystem executables for
  GUI and CLI.

## Data-package baseline

- Existing data lifecycle publishes immutable CSV generations through an
  atomic active pointer and validates file hashes.
- BaoStock update and user CSV import exist.
- Provider `channel.json`, provider dataset manifest schema, offline package
  importer, resumable channel downloader, license preflight, and dataset
  catalog are absent at this baseline.
- The deterministic production-contract fixture now contains 120 stocks and
  70 business days, with isolated route definitions for all three modes.

## User-journey baseline

The current service can complete an in-process fixture journey of data publish,
consent, train, Top-5 result, details, cache reuse, and artifact persistence.
The current GUI smoke only verifies tab names. It does not exercise a visible
ordinary-user journey, provider-data onboarding, keyboard navigation, CSV
export, recovery, or screenshot acceptance.

The v2 acceptance journey must therefore replace this evidence with an
install/launch/onboard/data/train/result/export flow driven through user-visible
QML controls on a native Linux desktop.
