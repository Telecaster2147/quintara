## 1. Project foundation and contract inventory

- [x] 1.1 Create the modern Python 3.12 package layout, `pyproject.toml`, locked `uv` environment, lint/type/test configuration, and GUI/CLI entry points.
- [x] 1.2 Add MIT `LICENSE`, initial `THIRD_PARTY_NOTICES`, contribution guide, and release-documentation skeleton.
- [x] 1.3 Capture a synthetic competition regression fixture and its authoritative input, feature, ranking, result, and manifest hashes from `bigdata/app`.
- [x] 1.4 Inventory authoritative kernel modules and record each reused, adapted, or replaced platform behavior in a kernel lineage document.
- [x] 1.5 Add CI formatting, lint, type, unit, and OpenSpec validation jobs on Ubuntu and Windows.

## 2. Identity schemas and application boundaries

- [x] 2.1 Define versioned enums and schemas for mode, data generation, universe generation, model identity, result identity, disclaimer version, and job state.
- [x] 2.2 Implement canonical JSON serialization and path-independent SHA-256 generation identifiers.
- [ ] 2.3 Add schema round-trip, canonicalization, collision, and incompatible-identity unit/property tests.
- [ ] 2.4 Define typed application commands, responses, events, error codes, and documentation anchors shared by GUI and CLI.
- [x] 2.5 Implement the application service facade with injected doctor, data, universe, kernel, job, result, and registry ports.
- [ ] 2.6 Add architecture tests that prevent GUI/CLI modules from importing kernel internals or implementing domain rules.

## 3. Cross-platform runtime services

- [x] 3.1 Implement platform-standard config/data/cache/log/export path resolution with overrides for tests.
- [x] 3.2 Implement cross-platform exclusive file locking with owner metadata, timeout, stale-owner validation, and release-on-exit behavior.
- [x] 3.3 Implement atomic file/pointer publication, hash verification, and staged recovery for POSIX and Windows.
- [ ] 3.4 Implement worker process spawn, event forwarding, cooperative cancellation, bounded force termination, and exit classification.
- [x] 3.5 Implement data-root-scoped single-instance GUI activation.
- [ ] 3.6 Test spaces, Chinese usernames, Unicode filenames, Windows long paths, concurrent locks, stale locks, and process termination.

## 4. Registry, generations, and recovery

- [x] 4.1 Design and migrate the SQLite registry for sources, generations, universes, models, results, jobs, pins, consent, and relationships.
- [x] 4.2 Implement immutable artifact directories, staging roots, scoped active pointers, manifest verification, and lineage queries.
- [ ] 4.3 Implement the two-phase filesystem/registry publication journal and startup reconciliation.
- [x] 4.4 Add fault-injection hooks at manifest, generation-rename, pointer, and registry boundaries.
- [ ] 4.5 Prove each injected failure recovers to one complete generation and never a mixed closure on Windows and Linux.
- [x] 4.6 Implement retention preview, five-success default retention, pinned-run protection, failure-log preservation, and explicit cleanup.

## 5. Environment doctor

- [x] 5.1 Implement OS/version/architecture, CPU, memory, disk, locale, path, application, runtime, and dependency probes.
- [ ] 5.2 Implement NVIDIA, driver, OpenCL, LightGBM CPU, and experimental GPU capability probes without changing user selection automatically.
- [ ] 5.3 Implement BaoStock, PIT-provider, GitHub Release, local data, and model compatibility probes with separate statuses.
- [x] 5.4 Implement workload memory/disk/time estimates and the 30-minute CPU warning without automatic parameter changes.
- [x] 5.5 Create Chinese beginner-readable doctor findings and local documentation for every stable error code.
- [ ] 5.6 Add probe fakes and cross-platform tests for no GPU, failed GPU, offline-valid-local, low disk, low memory, and unsupported platform cases.

## 6. Data source and PIT provider research spike

- [ ] 6.1 Evaluate candidate historical CSI300 PIT sources for 2015-present coverage, interval accuracy, update latency, reliability, terms, attribution, and user-side access.
- [ ] 6.2 Reconcile candidate membership histories against the existing verified fixture and document discrepancies and acceptable source precedence.
- [ ] 6.3 Select the primary and optional backup PIT adapters only after source/terms review and record the decision as an ADR.
- [x] 6.4 Review BaoStock client/data terms and freeze the user-side download/cache/attribution policy.
- [x] 6.5 Build deterministic provider fakes and recorded synthetic responses for offline integration tests.

## 7. Market and PIT data lifecycle

- [x] 7.1 Implement BaoStock login, listing metadata, daily market acquisition, bounded retry, checkpoint, and exact stock/date request planning.
- [ ] 7.2 Implement selected historical PIT provider acquisition with raw receipts, effective intervals, index identity, and terms metadata.
- [ ] 7.3 Implement canonical market/listing/calendar/membership schemas and partitioned local storage.
- [ ] 7.4 Implement first-run 2015-to-latest acquisition for the selected universe, using only the PIT closure for the recommended default and on-demand stock data for custom mode.
- [x] 7.5 Implement incremental update, exact-key replacement/union, checkpoint resume, and coverage metadata.
- [x] 7.6 Implement pre-18:00 Asia/Shanghai freshness warning and manual retry.
- [x] 7.7 Implement data manifest generation, independent source hashes, parent lineage, validation report, and atomic activation.
- [ ] 7.8 Test retries, resume, already-current, provider outage, invalid PIT, interrupted publication, and old-generation fallback.

## 8. CSV mapping and validation

- [x] 8.1 Define the canonical field dictionary, accepted dialect/encoding rules, unit declarations, and downloadable CSV templates.
- [x] 8.2 Implement source-byte hashing and immutable preservation before parsing.
- [x] 8.3 Implement field mapping and explicit unit/scale confirmation with plausibility checks.
- [ ] 8.4 Implement structural, key, type, OHLC, finite-value, temporal, history, label-horizon, listing, universe, and resource validators.
- [x] 8.5 Implement `PASS`/`WARNING`/`FAIL` reports with stable codes, source row/key scope, trainable dates, and docs links.
- [ ] 8.6 Implement local auxiliary metadata pairing and user-confirmed metadata fetch for supported stocks/dates.
- [x] 8.7 Implement exact-key conflict preview, explicit source precedence, and derived-generation manifest recording.
- [x] 8.8 Implement capped/redacted issue-sample CSV export and diagnostic exclusion of original market data.
- [ ] 8.9 Add property tests for row permutations, duplicate keys, unit scales, missing classes, immutable source bytes, and deterministic reports.

## 9. Universe management

- [x] 9.1 Implement immutable `PIT_BASELINE`, `CUSTOM_UNIVERSE`, and `NON_PIT_FALLBACK` universe schemas and scoped storage.
- [ ] 9.2 Implement dated PIT active sets, exact baseline member/date gates, legal listing checks, and lag-history eligibility.
- [ ] 9.3 Implement named custom pool create/list/select/rename/delete with code entry, BaoStock search, and CSV code import.
- [x] 9.4 Implement supported Shanghai/Shenzhen/Beijing A-share classification and rejection of other security classes.
- [x] 9.5 Implement ST/delisting/suspension status ingestion, default exclusion, explicit custom-experiment override, visible counts, and cutoff disclosure.
- [x] 9.6 Implement declared and per-date effective 100-stock custom universe gates.
- [x] 9.7 Implement explicit non-PIT acknowledgement, static-history semantics, permanent result badge, and PIT-restoration switch/retrain prompt.
- [ ] 9.8 Add interval, membership, custom-pool, status-filter, minimum-size, and cross-mode isolation tests.

## 10. Kernel adapter and labels

- [x] 10.1 Extract or wrap the authoritative feature, LightGBM ranking, final-refit, scoring, tie, and portfolio logic behind the kernel adapter.
- [x] 10.2 Implement `competition-open-open-v1` strictly for differential tests and audit tooling.
- [x] 10.3 Implement `quintara-weekly-open-close-v1` with actual-trading-session T+1 open and T+5 close endpoints.
- [x] 10.4 Implement gap-free stock history, listing legality, label endpoint, cutoff, embargo, and future-information assertions.
- [x] 10.5 Implement 3-to-10-year window selection and the user whitelist for device and thread count while freezing all other stable settings.
- [x] 10.6 Implement deterministic CPU configuration and manifest closure.
- [x] 10.7 Implement probe-gated experimental GPU configuration with separate device/runtime identity and CPU authority labeling.
- [ ] 10.8 Pass competition differential fixtures and product-label calendar/gap/embargo/leakage tests.
- [x] 10.9 Enforce the stable feature allowlist and test that unapproved extra features never enter matrices or manifests.

## 11. Training, prediction, and portfolio

- [x] 11.1 Implement application training orchestration from compatible data/universe identities through immutable model publication.
- [ ] 11.2 Implement compatible cutoff-frame reconstruction and fail-closed model identity validation before scoring.
- [x] 11.3 Implement full finite-score ranking, deterministic presentation order, and tie rejection inside top five and at the fifth/sixth boundary.
- [x] 11.4 Implement exactly five fixed weights `0.40/0.25/0.15/0.12/0.08` and UTF-8 `stock_id,weight` validation/export.
- [x] 11.5 Implement insufficient-candidate failure and eligibility/exclusion breakdown without candidate substitution.
- [x] 11.6 Implement cache reuse only when complete compatible data/model/result identities match.
- [ ] 11.7 Add repeated CPU, stale-model, cross-mode, tampered-result, tie, insufficient-candidate, and cache-identity tests.

## 12. Jobs, progress, cancellation, and history

- [x] 12.1 Implement one mutating job per data root with read-only access to published history during execution.
- [x] 12.2 Implement ordered JSONL job events, measurable/indeterminate progress, elapsed time, severity, and technical detail.
- [x] 12.3 Implement GUI close and CLI signal cancellation flows, safe-point cleanup, bounded force termination, and next-start recovery.
- [x] 12.4 Implement successful, failed, cancelled, cached, and recovered run history with mode/universe filters and pinning.
- [ ] 12.5 Add concurrency, interface reconnect, close, SSH signal, forced termination, cleanup, and stale-lock integration tests.

## 13. CLI

- [x] 13.1 Implement `doctor`, data initialize/list/update/validate/import, universe management, `train`, `predict`, `run`, result/history, diagnostics, cancel, and version commands.
- [x] 13.2 Implement Chinese sequential interactive prompts without a full-screen terminal UI.
- [x] 13.3 Implement direct command arguments, documented exit-code taxonomy, quiet/verbose modes, and optional structured output.
- [ ] 13.4 Add CLI parity tests proving identical application commands, manifests, and CPU outputs to the GUI/service path.
- [ ] 13.5 Add headless Debian/Ubuntu E2E and signal/SSH-disconnect smoke tests.

## 14. Desktop GUI

- [x] 14.1 Build the single PySide6/Qt Widgets shell with Home, Data, Universes, Training, Results, Run History, and Settings/Diagnostics pages.
- [x] 14.2 Build the reopenable first-run guide with disclaimer, paths, doctor, universe, and data initialization prompts.
- [x] 14.3 Build one-click weekly operation, verified-result reuse, honest progress, cancellation dialogs, and technical-log expansion.
- [ ] 14.4 Build searchable/sortable universe tables, single and CSV batch changes, status/coverage display, and explicit cleanup actions.
- [x] 14.5 Build light/dark/system themes, Chinese localization, basic keyboard focus, and responsive high-DPI layout.
- [x] 14.6 Implement single-instance activation, idle full exit, worker ownership, crash handling, and recovery-required startup.
- [ ] 14.7 Add Qt automated tests for navigation, first-run skip/resume, disabled training, universe edits, one-click run, close/cancel, themes, DPI, and single instance.

## 15. Results and explainability

- [x] 15.1 Implement the simple five-stock summary with names/codes/exchanges, weights, horizon, cutoff, mode, freshness, and disclaimer.
- [x] 15.2 Implement complete ranking, model scores, feature-contribution explanations, and explicit non-causal wording.
- [x] 15.3 Implement 20/60/120-session volatility, downside volatility, maximum drawdown, and correlation metrics with 60-session default.
- [x] 15.4 Implement full provenance details and persistent `NON_PIT_FALLBACK` warnings in GUI, CLI, history, and export.
- [x] 15.5 Implement exact two-column local result CSV export with adjacent identity/provenance manifest and no unrelated absolute paths.
- [ ] 15.6 Implement compatible-history comparison gates and an explicit identity-audit view.
- [ ] 15.7 Add metric window, short-history, feature explanation, provenance, export, and cross-identity comparison tests.

## 16. Privacy, legal, versioning, and documentation

- [x] 16.1 Implement a network allowlist and tests proving no telemetry or hidden outbound requests.
- [x] 16.2 Implement GitHub Release checks with no generated identifier/payload, a disable setting, notice-only behavior, and no automatic update.
- [x] 16.3 Implement local disclaimer confirmation/version records and reconfirmation before result generation after statement changes.
- [x] 16.4 Implement redacted local diagnostic preview/export with no upload path, no automatic screenshots, and no raw market CSV by default.
- [x] 16.5 Draft and review the mainland-China research disclaimer, privacy/zero-telemetry statement, result wording guide, and data-source terms notices.
- [x] 16.6 Generate SBOM and complete license inventory; include Qt/PySide6, LightGBM, runtime, installer, and provider notices in source and binary packages.
- [x] 16.7 Reconcile `docs/README.md`, `PRODUCT_DESIGN.md`, `KERNEL_ALIGNMENT.md`, `WINDOWS_WSL_COMPATIBILITY.md`, and `SKILLS.md` with desktop GUI, full CLI, new label, and current test matrix.
- [x] 16.8 Complete Chinese first-use, install, data, CSV field dictionary/template, training, result, error index, privacy, legal, and contribution documentation.

## 17. Packaging and native platform qualification

- [ ] 17.1 Run PyInstaller-plus-native-installer and Briefcase packaging spikes with PySide6/LightGBM on clean Windows and Linux runners.
- [ ] 17.2 Record size, cold start, native-library discovery, reproducibility, install/upgrade/uninstall, and choose the release chain in an ADR.
- [ ] 17.3 Build and smoke-test the Windows ordinary-user installer with bundled runtime, Start-menu/desktop entries, CLI exposure, and default data retention on uninstall.
- [ ] 17.4 Build Ubuntu 22.04/24.04 and Debian 12/13 packages with desktop and headless CLI entry points.
- [x] 17.5 Sign or checksum release artifacts as available, attach SBOM and notices, and verify artifact hashes in release metadata.
- [ ] 17.6 Run clean-host package smoke: no-Python launch, doctor, CPU fixture, paths, retained-data reinstall, and optional full-data removal.

## 18. Stable release evidence and final review

- [ ] 18.1 Complete unit, property, integration, differential, fault-injection, GUI, CLI, privacy, and package test matrices on required platforms.
- [ ] 18.2 Run security default, API sharp-edge, dependency supply-chain, static-analysis, and code-review gates; resolve all release-blocking findings.
- [x] 18.3 Generate a machine-readable release evidence manifest tied to commit, installer, dependency lock, fixture, data-schema, and test-result hashes.
- [ ] 18.4 Audit all OpenSpec requirement IDs against implemented tests and documentation and close every missing trace.
- [x] 18.5 Verify every user-visible error code resolves to a Chinese explanation and next action.
- [ ] 18.6 Confirm every stable release gate is green and publish only the complete validated release candidate.
