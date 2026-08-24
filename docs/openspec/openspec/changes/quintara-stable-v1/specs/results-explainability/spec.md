## Purpose

Defines understandable result presentation, advanced model and risk detail, provenance disclosure, local CSV export, and isolated historical comparison for non-quant users and auditors.

## ADDED Requirements

### Requirement: Simple result summary
**RES-001.** The default result view SHALL show five stock names, six-digit codes, exchanges, fixed weights, actual prediction dates, identity badge, data cutoff, and concise model-based explanations.

#### Scenario: Open latest result
- **WHEN** a verified result exists
- **THEN** Home shows the combination without requiring the user to open a raw `result.csv`

### Requirement: Advanced ranking detail
**RES-002.** Advanced details SHALL expose complete eligible ranking, model scores, principal feature contributions, historical volatility, downside volatility, maximum drawdown, and correlations without presenting feature contributions as causal proof.

#### Scenario: Inspect feature explanation
- **WHEN** a user opens a selected stock's explanation
- **THEN** the page states which features influenced model score and distinguishes that from a claim about future price causes

### Requirement: Risk windows
**RES-003.** Risk statistics SHALL be available for 20, 60, and 120 trading-session windows with 60 sessions selected by default, and SHALL disclose insufficient-history cases.

#### Scenario: Short-history stock
- **WHEN** only 35 valid sessions exist
- **THEN** 20-session metrics are shown and 60/120-session fields are marked unavailable rather than extrapolated

### Requirement: Provenance visibility
**RES-004.** Every result view SHALL expose its data generation, model generation, universe and PIT status, label version, kernel/config hashes, device, training window, source freshness, validation state, and applicable disclaimer version.

#### Scenario: Non-PIT result
- **WHEN** a `NON_PIT_FALLBACK` run is opened
- **THEN** the identity and survivorship warning remain prominent in summary and advanced views

### Requirement: CSV-only release export
**RES-005.** Stable v1 SHALL export results and requested ranking details to local CSV; PDF and PNG export SHALL NOT be release requirements.

#### Scenario: Export result
- **WHEN** a user selects CSV export
- **THEN** Quintara writes an exact `stock_id,weight` result CSV plus an adjacent provenance manifest, without disclosing unrelated local paths

### Requirement: Isolated run history
**RES-006.** Run history SHALL list successful, failed, cancelled, cached, and recovered runs and SHALL filter or compare only compatible model identities unless the user explicitly requests a cross-identity audit view.

#### Scenario: Compare incompatible universes
- **WHEN** a user selects a PIT and custom-universe run
- **THEN** ordinary performance comparison is blocked and the identity differences are shown

### Requirement: Beginner-readable failures
**RES-007.** Every user-visible failure SHALL include a plain-Chinese summary, affected stage, whether prior verified assets remain usable, a local documentation anchor, and an expandable technical identifier.

#### Scenario: Data validation failure
- **WHEN** an update is rejected
- **THEN** the user sees that the previous data remains active and receives a direct link to the matching error guide
