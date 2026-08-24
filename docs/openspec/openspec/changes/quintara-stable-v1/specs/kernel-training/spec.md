## Purpose

Defines versioned economic semantics, time-safe preparation, configuration, deterministic CPU authority, optional acceleration, and model identity for the Quintara training kernel.

## ADDED Requirements

### Requirement: Authoritative kernel lineage
**KER-001.** Quintara SHALL adapt the LightGBM features, ranking objective, fitting flow, and invariants from `/home/olm/bigdata/bigdata/app`, and every product kernel version SHALL identify its source closure and intentional deltas.

#### Scenario: Source change
- **WHEN** a kernel source or frozen configuration file changes
- **THEN** its source-closure hash changes and an existing incompatible generation is not reused

### Requirement: Versioned weekly label
**KER-002.** The default Quintara kernel SHALL label a signal date `T` with `close(T+5) / open(T+1) - 1`, where offsets refer to the next first and fifth actual market trading days and both observations belong to the same stock's gap-free legal history.

#### Scenario: Holiday week
- **WHEN** a holiday occurs between `T` and the fifth following trading session
- **THEN** label offsets count exchange trading sessions rather than calendar days

#### Scenario: Missing endpoint
- **WHEN** either endpoint is missing, invalid, suspended, or separated by an observed trading-data gap
- **THEN** that stock/date has no label and is excluded according to its universe date gate

### Requirement: Competition differential fixture
**KER-003.** The test system SHALL retain the original production `open(T+5) / open(T+1) - 1` contract as a named, non-default differential fixture and SHALL never present its result as the default Quintara product generation.

#### Scenario: Kernel regression
- **WHEN** the adapter runs the fixed competition fixture
- **THEN** input hash, PIT frame, features, configuration, ranking, and output match the authoritative production oracle within declared deterministic tolerances

### Requirement: Time-safe features and labels
**KER-004.** Feature construction SHALL use only information available at or before each signal date, label endpoints SHALL lie at or before the training cutoff, and membership/listing state SHALL be evaluated as of each row date.

#### Scenario: Future-dated row injected
- **WHEN** a candidate feature or membership record is effective after the signal date
- **THEN** it is excluded and the leakage assertion records the reason

### Requirement: Training window and configuration whitelist
**KER-005.** Users SHALL select an inclusive training history between 3 and 10 years, execution device, and thread count; all other LightGBM, feature, label, and portfolio settings SHALL be frozen by the selected kernel profile.

#### Scenario: Advanced parameter edit
- **WHEN** a configuration import changes a non-whitelisted setting
- **THEN** the run is rejected or explicitly assigned a separate unsupported experiment identity, never a stable production identity

### Requirement: CPU authority
**KER-006.** CPU execution SHALL be the authoritative reproducible result path and SHALL use frozen random seeds, deterministic ordering, feature list, and model configuration.

#### Scenario: Repeated CPU run
- **WHEN** identical validated inputs and runtime closure are trained twice on a supported CPU platform
- **THEN** manifests, ranking, and portfolio match according to the deterministic contract

### Requirement: Experimental GPU acceleration
**KER-007.** GPU execution SHALL be selectable only after a successful capability probe, SHALL be marked experimental, SHALL record device/driver/runtime, and SHALL never replace the CPU authoritative baseline.

#### Scenario: GPU ranking differs
- **WHEN** GPU output differs from the CPU result
- **THEN** both artifacts remain separately identified and CPU remains the authoritative baseline

### Requirement: Mode-bound model identity
**KER-008.** A model generation SHALL bind data generation, universe identity, label version, kernel source/config hashes, feature list, runtime versions, device profile, and training window.

#### Scenario: Cross-mode inference request
- **WHEN** a `CUSTOM_UNIVERSE` model is requested for a `PIT_BASELINE` result
- **THEN** inference fails before loading scores and reports the identity mismatch

### Requirement: Stable feature closure
**KER-009.** Stable v1 SHALL train only on the feature closure validated by the authoritative kernel and SHALL exclude BaoStock financial, valuation, industry, forecast, or other extra features until a separately versioned and tested kernel change adopts them.

#### Scenario: Extra column present
- **WHEN** imported or downloaded data contains an unapproved extra feature column
- **THEN** the column may remain in source storage but is absent from the stable model feature list and manifest
