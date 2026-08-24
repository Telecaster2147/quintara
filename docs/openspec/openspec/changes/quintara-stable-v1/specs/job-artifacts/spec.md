## Purpose

Defines exclusive task execution, observable progress, cancellation and recovery, immutable generations, atomic publication, and bounded retention of data, model, and result artifacts.

## ADDED Requirements

### Requirement: Single mutating job
**JOB-001.** One application data root SHALL allow at most one update, import, training, or prediction publication job at a time, while read-only history and result views remain available.

#### Scenario: Concurrent start
- **WHEN** a second mutating job is requested
- **THEN** it is rejected with the owning job ID, stage, and start time rather than running concurrently

### Requirement: Job event contract
**JOB-002.** Every job SHALL emit ordered events containing job ID, stage, timestamp, severity, message key, optional measurable progress, and local diagnostic context usable by both GUI and CLI.

#### Scenario: Interface reconnect
- **WHEN** an interface reloads the current job state
- **THEN** it reconstructs the latest stage and events without inventing missing progress

### Requirement: Cooperative and forced cancellation
**JOB-003.** Cancellation SHALL first request cooperative stop at safe points, prevent pointer publication, and clean unpublished files; after a bounded timeout the owning interface MAY force process termination and mark startup cleanup required.

#### Scenario: Cancel before publish
- **WHEN** cancellation arrives after model staging but before active pointer replacement
- **THEN** the active model remains unchanged and staged model files are removed or quarantined

### Requirement: Crash recovery
**JOB-004.** Startup SHALL inspect locks, journals, staging directories, and pending pointers, distinguish live ownership from stale state, restore the last complete active generation, and preserve failure evidence.

#### Scenario: Stale lock after crash
- **WHEN** the recorded owner process is absent
- **THEN** recovery clears the stale lock only after validating active pointers and recording the recovery action

### Requirement: Content-addressed generations
**JOB-005.** Published data, model, and result generations SHALL be immutable and identified by a canonical manifest content hash; active pointers SHALL name both generation and manifest hash.

#### Scenario: Existing generation collision
- **WHEN** a computed identifier already exists with different bytes
- **THEN** publication fails closed and reports a collision

### Requirement: Atomic active-pointer publication
**JOB-006.** Publication SHALL durably write artifacts and manifest before atomically replacing a pointer, with platform-equivalent recovery semantics on Windows and Linux.

#### Scenario: Kill during pointer update
- **WHEN** fault injection terminates the process at any publication boundary
- **THEN** recovery yields either the prior complete generation or the new complete generation, never a mixed closure

### Requirement: Run history and retention
**JOB-007.** Quintara SHALL retain the most recent five successful runs by default, all failure/cancellation logs, and every user-pinned run; cleanup SHALL preview reclaimed space and affected unpinned generations.

#### Scenario: Retention cleanup
- **WHEN** a sixth unpinned successful run is published
- **THEN** the oldest unpinned success becomes cleanup-eligible without deleting any pinned run or failure log
