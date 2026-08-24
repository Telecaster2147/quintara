## Purpose

Defines cutoff eligibility, scoring and deterministic ranking, five-stock research combination construction, fixed weights, failure boundaries, and machine-readable result validation.

## ADDED Requirements

### Requirement: Compatible cutoff frame
**PRD-001.** Prediction SHALL use the latest complete trading cutoff of the active data generation and SHALL require a model whose full identity matches data, universe, label, kernel, features, and runtime contract.

#### Scenario: Stale model after update
- **WHEN** data is published after model training
- **THEN** prediction is blocked until a compatible retraining completes

### Requirement: Eligible candidate construction
**PRD-002.** `PIT_BASELINE` candidates SHALL be valid active PIT members at cutoff; `CUSTOM_UNIVERSE` and `NON_PIT_FALLBACK` candidates SHALL belong to their static pool and pass listing, critical-market, and enabled status filters.

#### Scenario: Ineligible high score
- **WHEN** a scored stock is not eligible at cutoff
- **THEN** the run fails integrity validation rather than including that stock

### Requirement: Deterministic ranking
**PRD-003.** Candidates SHALL be ranked by finite model score descending under a documented deterministic presentation order, and unresolved score ties within the selected five or at the fifth/sixth boundary SHALL fail portfolio construction.

#### Scenario: Fifth-place tie
- **WHEN** the fifth and sixth candidates are equal within the frozen tie tolerance
- **THEN** no portfolio is published and the result explains the unresolved boundary

### Requirement: Five-stock fixed combination
**PRD-004.** A successful stable result SHALL contain exactly five distinct eligible stocks with rank weights `[0.40, 0.25, 0.15, 0.12, 0.08]` interpreted as fractions of the research combination.

#### Scenario: Successful construction
- **WHEN** at least six untied eligible candidates exist
- **THEN** the top five receive the frozen weights in rank order and the weight sum equals 1.0

### Requirement: Insufficient candidate failure
**PRD-005.** Prediction SHALL fail with an actionable eligibility breakdown when fewer than five qualified candidates remain and SHALL NOT fill the combination with invalid or filtered securities.

#### Scenario: Four candidates remain
- **WHEN** cutoff filters leave four qualified candidates
- **THEN** no result generation is published and exclusions are summarized by reason

### Requirement: Result schema validation
**PRD-006.** CSV export SHALL use UTF-8 columns `stock_id,weight`, preserve six-digit codes, contain five unique rows for a successful stable result, and contain finite positive weights summing to 1 within declared tolerance.

#### Scenario: Result tampering
- **WHEN** an exported result is revalidated after a code, duplicate, or weight change
- **THEN** validation fails and identifies the violated output invariant

### Requirement: Research-only semantics
**PRD-007.** Results SHALL be described as model scores, predicted ranking, or research combination and SHALL NOT use guaranteed-return, order, target-price, or certain-outcome language.

#### Scenario: Render successful result
- **WHEN** the five-stock result is shown
- **THEN** the prediction horizon, model identity, fixed fractional weights, and research disclaimer are visible together
