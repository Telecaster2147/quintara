## Purpose

Defines evidence required to call Quintara stable, including cross-platform installation, deterministic and time-safe kernel behavior, transactional recovery, interface acceptance, and documentation completeness.

## ADDED Requirements

### Requirement: Stable release gate
**QAL-001.** A release SHALL NOT be labeled stable while any required Windows/Linux install, data, CPU train/predict, result, cancellation/recovery, uninstall, unit, property, differential, GUI, CLI, license, or documentation gate is failing or unexecuted.

#### Scenario: One failed Windows smoke
- **WHEN** the clean Windows install-and-launch job fails
- **THEN** the candidate remains unreleased or pre-release regardless of other passing jobs

### Requirement: Supported-platform matrix
**QAL-002.** CI SHALL exercise native Windows and supported Linux environments, while a real Windows user trial SHALL provide additional feedback rather than replacing automated evidence.

#### Scenario: Linux-only success
- **WHEN** all Linux jobs pass but native Windows CPU training has no passing evidence
- **THEN** Windows support is not declared stable

### Requirement: Kernel differential evidence
**QAL-003.** Fixed competition fixtures SHALL compare authoritative source and adapter input hashes, PIT cutoff, feature order, config, CPU ranking, portfolio, generation closure, and output validation.

#### Scenario: Ranking drift
- **WHEN** a source-compatible fixture produces a different CPU ranking
- **THEN** the differential gate fails with the first differing identity and row

### Requirement: Product-label tests
**QAL-004.** Tests SHALL independently verify `close(T+5)/open(T+1)-1`, actual trading-session offsets, missing/gap exclusion, label embargo, and absence of future feature or membership leakage.

#### Scenario: Calendar holiday fixture
- **WHEN** a synthetic fixture contains a multi-day exchange holiday
- **THEN** the expected fifth trading session, not fifth calendar day, defines the close endpoint

### Requirement: Data and CSV properties
**QAL-005.** Property-based tests SHALL cover key uniqueness, row-order invariance, unit/mapping validation, immutable source files, conflict policy, PIT intervals, universe-size gates, and deterministic generation hashing.

#### Scenario: Row permutation
- **WHEN** a valid source CSV is randomly permuted
- **THEN** normalized generation identity and model inputs remain equivalent

### Requirement: Publication fault injection
**QAL-006.** Tests SHALL terminate data/model/result publication at every durability boundary and prove recovery produces one complete generation, releases locks, and retains diagnosis.

#### Scenario: Failure after manifest write
- **WHEN** the publisher is killed after durable manifest write but before pointer replacement
- **THEN** restart preserves the old active pointer and safely classifies the unpublished generation

### Requirement: GUI and CLI acceptance
**QAL-007.** Automated tests SHALL cover first-run, diagnosis, data initialization, universe editing, CSV validation, one-click run, progress, cancellation, results, export, single instance, headless CLI, signals, and error-document links.

#### Scenario: Windows high-DPI smoke
- **WHEN** GUI smoke runs with supported high-DPI settings
- **THEN** critical controls are visible and the end-to-end fixture remains operable

### Requirement: Package lifecycle evidence
**QAL-008.** Release smoke SHALL install on a clean host without Python, launch GUI/CLI, create platform paths, run a CPU fixture, preserve data on default uninstall, and verify optional full-data removal.

#### Scenario: Default uninstall/reinstall
- **WHEN** a user uninstalls with retained data and reinstalls the same compatible release
- **THEN** the validated local generation is rediscovered without re-downloading

### Requirement: Documentation gate
**QAL-009.** Stable release SHALL include first-use guidance, installation, data contracts, CSV template/dictionary, training/label explanation, result interpretation, error index, privacy/zero-telemetry statement, legal/third-party notices, and contribution guidance.

#### Scenario: Error code documentation audit
- **WHEN** release validation enumerates user-visible error identifiers
- **THEN** each identifier resolves to a Chinese documentation entry with cause and next action
