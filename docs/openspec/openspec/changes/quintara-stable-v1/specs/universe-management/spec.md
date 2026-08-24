## Purpose

Defines creation and isolation of historical PIT baseline, named custom A-share universes, and explicitly degraded non-PIT universes with security eligibility and minimum-size contracts.

## ADDED Requirements

### Requirement: Universe identities
**UNI-001.** Every universe SHALL have exactly one identity: `PIT_BASELINE`, `CUSTOM_UNIVERSE`, or `NON_PIT_FALLBACK`, and that identity SHALL be immutable for a model generation.

#### Scenario: Change universe mode
- **WHEN** a user switches from PIT baseline to a custom pool
- **THEN** Quintara selects a different universe identifier and does not reuse the PIT model or results

### Requirement: PIT baseline membership
**UNI-002.** `PIT_BASELINE` SHALL determine eligible CSI300 securities independently for each historical date using effective membership intervals, listing legality, critical market validity, and the exact 300-member contract.

#### Scenario: Historical membership change
- **WHEN** a stock joins CSI300 after the start of the training window
- **THEN** its own legal earlier history may support lag features, but it enters cross-sectional training only on active membership dates

### Requirement: Default universe selection
**UNI-003.** First-run SHALL ask the user to select baseline or custom mode and SHALL recommend `PIT_BASELINE` without silently selecting an alternate universe after a validation failure.

#### Scenario: Baseline unavailable
- **WHEN** no valid PIT generation is available
- **THEN** the user sees the dated failure and explicit choices rather than an automatic static-universe substitution

### Requirement: Named custom pools
**UNI-004.** Users SHALL be able to create multiple named A-share pools by code entry, searchable BaoStock selection, or CSV code list, view all participating securities and data coverage, and select exactly one active pool.

#### Scenario: Remove security
- **WHEN** a user removes a stock from a pool
- **THEN** it leaves that pool while downloaded history is retained until a separate cleanup is confirmed

### Requirement: Supported security scope
**UNI-005.** Custom pools SHALL accept RMB ordinary shares listed on Shanghai, Shenzhen, or Beijing exchanges and SHALL reject other security classes from v1 model eligibility.

#### Scenario: ETF code submitted
- **WHEN** metadata identifies an entered code as an ETF
- **THEN** the pool import rejects it with a supported-scope explanation

### Requirement: Special-status filtering
**UNI-006.** ST, delisting-board, and long-suspended securities SHALL be stored with explicit status but SHALL be excluded from training and prediction by a default-enabled filter that the user can inspect and explicitly disable for a custom experiment.

#### Scenario: Special status in result cutoff
- **WHEN** a security is special-status at the prediction cutoff and the default filter is active
- **THEN** it is absent from eligible candidates and the run report counts the exclusion

#### Scenario: User disables special-status filter
- **WHEN** the user explicitly disables the filter for a custom-universe run
- **THEN** the manifest records the changed policy and the result is marked as a custom experiment

### Requirement: Custom universe size gates
**UNI-007.** A custom pool SHALL contain at least 100 declared eligible securities, and each training date SHALL contain at least 100 valid securities; dates below the effective threshold SHALL be excluded.

#### Scenario: Pool contains 99 supported stocks
- **WHEN** the user requests training
- **THEN** training is blocked and the user is offered actions to add stocks or explicitly switch to PIT baseline

### Requirement: Non-PIT fallback confirmation
**UNI-008.** `NON_PIT_FALLBACK` SHALL be entered only through explicit confirmation of static-pool backfill and survivorship-bias warnings and SHALL remain visually and structurally distinct everywhere.

#### Scenario: Confirm fallback
- **WHEN** PIT data is unavailable and the user accepts fallback
- **THEN** a new non-PIT universe generation is created with the confirmation and warning version in its manifest

#### Scenario: PIT restored
- **WHEN** a valid PIT generation becomes available
- **THEN** Quintara prompts for a switch and full retraining rather than relabeling the non-PIT model
