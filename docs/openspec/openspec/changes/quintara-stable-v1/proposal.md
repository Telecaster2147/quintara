## Why

Quintara must turn the existing competition pipeline into a stable, locally installed A-share research product that a non-quant user can operate end to end without Python knowledge. The closed grill fixes the product semantics, platform matrix, data identities, interaction model, privacy posture, and release gates; this change converts those owner decisions into testable contracts and implementation evidence.

## What Changes

### Goals

- Deliver a Windows-first standalone Chinese desktop application plus a full plain-shell CLI for headless Linux. (C-004, C-045, C-052, C-060–C-064, C-081)
- Manage BaoStock market data, historical PIT membership, custom CSV data, named universes, models, results, and provenance as local versioned assets. (C-006–C-010, C-023–C-027, C-046–C-047, C-070–C-072, C-088–C-090)
- Adapt the authoritative LightGBM kernel into three isolated identities: `PIT_BASELINE`, `CUSTOM_UNIVERSE`, and explicitly confirmed `NON_PIT_FALLBACK`. (C-003, C-024, C-030–C-031, C-046, C-048, C-088–C-089)
- Produce an understandable five-stock weekly research combination, fixed weights, advanced model details, risk metrics, CSV export, and complete run history. (C-028, C-049–C-050, T09–T15, C-073–C-075)
- Offer three named, bounded profiles—`aggressive`, `balanced`, and `conservative`—that adjust only the approved model-capacity/regularization knobs while preserving the fixed portfolio contract. (T15, C-050)
- Make every critical path diagnosable, cancellable, recoverable, cross-platform tested, privacy preserving, and provenance bound. (C-014–C-015, C-022, C-034–C-038, C-041, C-054–C-059, C-067–C-069, C-078–C-080)

### Behavioral changes

- **BREAKING**: Browser WebUI and local HTTP service are removed; PySide6/Qt Widgets becomes the graphical interface. (UI01, UI22)
- **BREAKING**: The default Quintara weekly label is versioned to `close(T+5) / open(T+1) - 1` over actual trading days. The original competition `open(T+5) / open(T+1) - 1` contract remains an internal differential fixture rather than the default product result. (C-048, T09–T10)
- **BREAKING**: CLI returns to the stable-release scope so Debian/Ubuntu systems without a desktop can complete the same core workflow. (UI02, F01–F03)
- Data or PIT failure never silently changes a universe or identity. A user may explicitly enter `NON_PIT_FALLBACK` only after a warning and receives separately stored, prominently marked outputs. (F11)
- Parameters exposed to users are limited to training years, CPU/GPU choice, thread count, and the three bounded strategy presets; all other model and portfolio configuration is frozen for the stable profile. (C-029–C-030, C-050)

### Non-goals

- Brokerage connectivity, order execution, automated trading, cloud accounts, multi-tenancy, mobile applications, or telemetry. (C-018, C-059)
- Browser WebUI, HTTP service, TUI, system-tray daemon, or remote access. (C-005, C-063, C-067)
- ETF, LOF, convertible bond, B-share, Hong Kong, US, index, or fund modelling in v1. (C-083)
- Arbitrary user-facing LightGBM tuning, variable portfolio weights, or unvalidated extra features in v1. The three named strategy profiles are bounded presets, not free-form tuning. (C-010, C-017, C-044, C-050)
- Silent CSV cleaning, automatic system-driver modification, automatic application upgrade, or automatic PIT downgrade. (C-007, C-036, C-054, C-088)

### Success gates

Stable release requires clean Windows installation and CPU operation, Ubuntu/Debian installation and CLI operation, data initialization/update/import, PIT/custom/non-PIT identity isolation, deterministic training/prediction, cancellation/recovery, local-only diagnostics, GUI/CLI acceptance, production differential fixtures, and license/legal documentation to pass. Any failed core gate blocks release. (C-035, C-038, T28–T30, UI20)

## Capabilities

### New Capabilities

- `installation-runtime`: Cross-platform installation, user data paths, runtime bundling, upgrade notice, uninstall, and platform support policy.
- `desktop-gui`: Standalone Chinese Qt desktop navigation, first-run workflow, one-click operation, themes, DPI, lifecycle, and single-instance behavior.
- `shell-cli`: Headless and interactive shell commands, exit codes, signals, logs, and parity with the core application service.
- `environment-doctor`: OS, CPU, memory, disk, Python/runtime, NVIDIA/OpenCL, network, data, and workload estimate diagnostics.
- `data-lifecycle`: Local market-data initialization, BaoStock incremental update, PIT-source update, staging validation, atomic publication, fallback, and provenance.
- `csv-ingestion`: Field mapping, units, validation severities, conflict policy, issue samples, auxiliary-data pairing, and immutable source imports.
- `universe-management`: PIT CSI300, named custom A-share pools, security-state filters, minimum universe contracts, and explicit non-PIT fallback isolation.
- `kernel-training`: Versioned labels, feature history, leakage barriers, parameter whitelist, deterministic CPU authority, experimental GPU, and model identity.
- `job-artifacts`: Single-writer task orchestration, progress events, cancellation, crash cleanup, generations, manifests, locks, and retention.
- `prediction-portfolio`: Eligible cutoff construction, score ranking, tie behavior, five-stock fixed weights, insufficient-candidate failure, and output validation.
- `results-explainability`: Home and advanced result views, feature contributions, risk windows, source/status disclosure, CSV export, and run history.
- `privacy-legal-versioning`: Zero telemetry, redacted diagnostics, local consent records, research wording, third-party notices, and version checks.
- `quality-release`: Unit, property, differential, fault-injection, GUI/CLI E2E, packaging smoke, supported-platform matrix, and release blocking evidence.

### Modified Capabilities

_None. This is the initial OpenSpec baseline; all capabilities are new._

## Impact

- New Python application/service layers, PySide6 GUI, CLI entry points, cross-platform locking/publication/process-control adapters, data/version registries, diagnostics, and installers.
- Intentional versioned adaptation of `/home/olm/bigdata/bigdata/app` while retaining its current production behavior as a differential oracle.
- New local network integrations for BaoStock and optional GitHub Releases version checks. Historical PIT membership is accepted through a user-supplied, validated sidecar until a source/terms review selects a redistributable provider; the fallback route is always explicit.
- New user-data, model, result, log, consent, and manifest schemas under platform-standard user directories.
- New dependencies for Qt, packaging, platform services, testing, SBOM/license inventory, and CI; every redistributed dependency requires notice and supply-chain review.
- Existing prose documents containing WebUI and old-label assumptions are superseded by this change and must be reconciled as documentation tasks.
