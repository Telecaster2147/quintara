## Purpose

Defines reproducible environment and workload diagnostics so users understand platform readiness, resource limits, acceleration status, data readiness, and corrective actions before work starts.

## ADDED Requirements

### Requirement: Runtime inventory
**DOC-001.** Doctor SHALL report operating system/version, architecture, CPU model/core count, memory, available disk, application/runtime/dependency versions, user-data path, and relevant locale/path capabilities.

#### Scenario: Standard diagnosis
- **WHEN** doctor runs
- **THEN** it emits a local report containing detected values, pass/warning/fail status, and beginner-readable guidance

### Requirement: GPU capability probe
**DOC-002.** Doctor SHALL report NVIDIA GPU model, driver, visible compute/OpenCL capability, LightGBM GPU probe result, and fallback status without requiring a GPU for normal operation.

#### Scenario: GPU visible but probe fails
- **WHEN** an NVIDIA device is detected but the LightGBM acceleration probe fails
- **THEN** GPU training remains unavailable, CPU remains selected, and doctor explains the failed capability

### Requirement: Resource thresholds
**DOC-003.** Doctor SHALL evaluate the minimum x86-64/4-core/8-GB/15-GB profile and recommended 8-core/16-GB/25-GB profile and SHALL prevent a write operation when required free disk is insufficient.

#### Scenario: Low memory
- **WHEN** memory is below the minimum but execution is still technically possible
- **THEN** doctor marks the condition as failed for the stable supported path and offers non-destructive guidance

### Requirement: Workload estimation
**DOC-004.** Doctor SHALL estimate memory, disk, and CPU duration from training years, active universe size, and thread count, and SHALL warn when estimated CPU training exceeds 30 minutes without changing parameters or stopping an accepted run.

#### Scenario: Long estimated training
- **WHEN** the estimate exceeds 30 minutes
- **THEN** the user receives a warning and the accepted run proceeds with unchanged settings and no time-based termination

### Requirement: Network and data probes
**DOC-005.** Doctor SHALL separately test BaoStock access, PIT-provider access, GitHub version access, active data integrity, and model/data compatibility, and SHALL distinguish offline conditions from invalid local state.

#### Scenario: Offline with valid local state
- **WHEN** network probes fail but a verified local data/model generation exists
- **THEN** doctor reports network warnings and allows compatible offline result reuse or training

### Requirement: Non-invasive guidance
**DOC-006.** Doctor SHALL only create application-owned directories and validate/download application assets; it SHALL provide instructions rather than automatically modifying drivers, system runtimes, permissions, or global configuration.

#### Scenario: Missing driver
- **WHEN** the optional GPU driver is missing
- **THEN** doctor explains the CPU path and links local documentation without changing the operating system
