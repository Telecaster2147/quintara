## Purpose

Defines import of user-supplied market CSV files through explicit schema/unit mapping and trainability validation while preserving the user's original bytes and reporting actionable defects.

## ADDED Requirements

### Requirement: Explicit field and unit mapping
**CSV-001.** Import SHALL accept a mapping from user column names to the required market contract and SHALL require explicit units for price, volume, amount, turnover, and percentage fields where scale is ambiguous.

#### Scenario: Percentage ambiguity
- **WHEN** a mapped change-rate column could represent `0.05` or `5`
- **THEN** validation remains incomplete until the user declares the unit and the plausibility check evaluates that declaration

### Requirement: Immutable source input
**CSV-002.** Quintara SHALL hash and preserve the user source file and SHALL NOT silently edit, fill, deduplicate, reorder, rescale, or overwrite it.

#### Scenario: Duplicate key detected
- **WHEN** duplicate `(stock_id,date)` keys exist
- **THEN** the import reports them and leaves the source file unchanged

### Requirement: Trainability validation
**CSV-003.** Validation SHALL check encoding/dialect, headers, mappings, types, six-digit codes, dates, key uniqueness, monotonicity, OHLC positivity/relationships, finite values, units, history length, label horizon, cross-sectional coverage, listing legality, and required universe metadata.

#### Scenario: Critical OHLC missing
- **WHEN** an eligible row lacks open, close, high, or low
- **THEN** validation emits `FAIL` for the affected key/date and excludes publication

#### Scenario: Tolerated noncritical missing value
- **WHEN** a noncritical field is missing within the frozen kernel's supported indicator policy
- **THEN** validation emits `WARNING`, preserves the missing value, and identifies the model policy that will consume it

### Requirement: Validation outcome contract
**CSV-004.** A validation report SHALL classify each finding as `PASS`, `WARNING`, or `FAIL`, identify field/key/impact and trainable range, and SHALL allow only a report without `FAIL` to become an active imported generation.

#### Scenario: Failed import attempt
- **WHEN** the report contains one or more `FAIL` findings
- **THEN** the dataset remains unpublished and GUI/CLI link to the report and issue sample

### Requirement: Local issue samples
**CSV-005.** Exported issue samples SHALL remain local, include at most the first 100 rows per issue class by default, redact user-directory paths, and exclude unrelated raw market rows from diagnostic bundles.

#### Scenario: Export issue sample
- **WHEN** a user requests examples for a validation failure
- **THEN** Quintara creates a bounded local CSV with issue keys and relevant fields only

### Requirement: Auxiliary metadata pairing
**CSV-006.** Quintara SHALL try to pair user market rows with validated local listing, calendar, and PIT metadata and MAY fetch missing supported metadata after explicit network confirmation.

#### Scenario: Metadata remains missing
- **WHEN** a stock/date cannot be covered after the permitted lookup
- **THEN** PIT-mode validation fails for that scope and identifies which auxiliary contract is absent

### Requirement: Existing-key conflict decision
**CSV-007.** Before merging a user import with managed data, Quintara SHALL show exact key-conflict statistics and require the user to choose user value or managed value precedence; the choice SHALL be written to the generation manifest.

#### Scenario: User chooses source precedence
- **WHEN** conflicting keys are present and the user selects user values
- **THEN** only the published derived generation reflects that choice while both original sources remain immutable
