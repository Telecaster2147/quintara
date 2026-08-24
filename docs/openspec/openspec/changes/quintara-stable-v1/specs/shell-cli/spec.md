## Purpose

Defines the full plain-shell interface for headless Linux, interactive users, automation, and test harnesses while sharing all domain behavior with the desktop application.

## ADDED Requirements

### Requirement: Complete CLI capability
**CLI-001.** The `quintara` CLI SHALL expose doctor, first data initialization, data update, universe list/create/import/switch, CSV validate/import, train, predict, run, result view/export, run history, cancellation, diagnostics export, and version check.

#### Scenario: Headless end-to-end run
- **WHEN** a Debian server user selects a valid universe and invokes the one-command workflow
- **THEN** the CLI completes the same application-service stages and produces the same generation identity as the GUI would

### Requirement: Interactive and direct invocation
**CLI-002.** The CLI SHALL offer Chinese step-by-step prompts for human use and direct subcommands with stable arguments for scripts, without implementing a full-screen TUI.

#### Scenario: Interactive invocation
- **WHEN** the user runs `quintara` without a subcommand in an interactive terminal
- **THEN** a sequential Chinese prompt guides selection and confirmation

#### Scenario: Direct invocation
- **WHEN** a complete subcommand and arguments are supplied
- **THEN** the command runs without additional prompts unless an explicit destructive or identity-downgrade confirmation is required

### Requirement: Exit and output contracts
**CLI-003.** Every direct command SHALL return a documented nonzero exit code for validation, network, configuration, conflict, cancellation, and internal failures, and SHALL keep human status separate from optional structured output.

#### Scenario: CSV validation failure
- **WHEN** validation produces `FAIL`
- **THEN** the process returns the documented validation exit code and identifies the local report path

### Requirement: Signal handling
**CLI-004.** A CLI-owned job SHALL handle terminal termination signals by requesting cancellation, cleaning unpublished artifacts, preserving logs, and returning a cancellation status.

#### Scenario: SSH disconnect
- **WHEN** the CLI receives a hangup or termination signal during training
- **THEN** it stops publication, cleans staging, preserves the run record, and releases its task lock

### Requirement: Shared behavior parity
**CLI-005.** The CLI SHALL call the same application services, validators, identity rules, and artifact publisher as the GUI and SHALL NOT implement alternate training or data logic.

#### Scenario: Cross-interface parity
- **WHEN** GUI and CLI run with identical validated inputs and CPU configuration
- **THEN** their manifests and result content are identical apart from interface-specific timestamps or presentation metadata
