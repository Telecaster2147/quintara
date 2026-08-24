## Purpose

Defines local acquisition, validation, publication, rollback, freshness, and provenance of market, listing, calendar, and historical PIT data used by every model identity.

## ADDED Requirements

### Requirement: User-side initial data acquisition
**DAT-001.** The installer SHALL contain no historical market dataset; first-run initialization SHALL download the selected universe's required data from 2015 through the latest complete trading date directly to the user's local data store, using the PIT baseline closure when the recommended default is selected.

#### Scenario: First initialization
- **WHEN** no active dataset exists and the user confirms initialization
- **THEN** Quintara downloads the selected PIT baseline closure, validates it, and publishes the first active generation

#### Scenario: Custom universe selected first
- **WHEN** the user creates and selects a valid custom universe during first run
- **THEN** Quintara downloads that universe's required stock data on demand rather than downloading all A shares

### Requirement: Incremental BaoStock update
**DAT-002.** An update SHALL log in to BaoStock, determine missing stock/date keys, retrieve required A-share daily market and listing-state records, resume bounded partial downloads, and merge by exact key without duplicating existing rows.

#### Scenario: Already current
- **WHEN** all required keys through the latest complete trading date are present
- **THEN** the update reports that data is current and creates no new generation

#### Scenario: Trading day before 18:00 Asia/Shanghai
- **WHEN** a user checks same-day freshness before 18:00
- **THEN** Quintara warns that the provider may not yet contain a complete session and allows manual retry

### Requirement: PIT membership acquisition
**DAT-003.** `PIT_BASELINE` SHALL use dated membership intervals from a traceable historical source and SHALL validate interval structure, stock codes, index identity, and per-date active membership before publication.

#### Scenario: Static list offered as history
- **WHEN** a source supplies only current CSI300 constituents for historical dates
- **THEN** the PIT validation fails and the source is not published as a PIT generation

### Requirement: Transactional data publication
**DAT-004.** Every download/import SHALL write into staging, validate schema/keys/coverage/contracts, generate content hashes and a manifest, and atomically switch the active pointer only after success.

#### Scenario: Validation failure
- **WHEN** any staging check fails
- **THEN** the prior active generation remains unchanged and the failure report identifies the staging issue

#### Scenario: Process interruption
- **WHEN** the updater exits between staging creation and pointer replacement
- **THEN** startup recovery keeps the last valid active generation and quarantines or removes unpublished staging

### Requirement: Update-triggered training
**DAT-005.** Publishing a changed data generation SHALL invalidate incompatible model/result reuse and SHALL continue into retraining for the active universe before prediction for that generation, except for an explicitly selected download/validate-only expert operation.

#### Scenario: New rows published
- **WHEN** the active data generation hash changes
- **THEN** the prior model is shown as incompatible and the ordinary update flow proceeds through training

### Requirement: Failed-source fallback
**DAT-006.** A PIT-source or market-source failure SHALL preserve the last verified generation; the application SHALL NOT silently substitute an unverified, static, or different-identity dataset.

#### Scenario: PIT endpoint unavailable
- **WHEN** the PIT source is unavailable
- **THEN** the user may keep using the dated verified PIT generation or explicitly enter `NON_PIT_FALLBACK`, but the active PIT pointer does not change

### Requirement: Data provenance manifest
**DAT-007.** Each data generation SHALL record source name, acquisition time, covered dates, securities, row/key counts, validation outcome, applicable terms link, content hashes, parent generation, and publication status per data class.

#### Scenario: Inspect active data
- **WHEN** a user opens data details or exports a result
- **THEN** the market, listing, calendar, and membership inputs are independently traceable to their manifest entries
