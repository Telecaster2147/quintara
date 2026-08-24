## Purpose

Defines the standalone local graphical experience for ordinary Chinese-speaking users, including first-run guidance, task lifecycle, desktop behavior, and display compatibility.

## ADDED Requirements

### Requirement: Native desktop-only interface
**GUI-001.** Quintara SHALL provide a standalone Chinese desktop GUI and SHALL NOT start an HTTP service, open a browser, or depend on a browser for normal operation.

#### Scenario: GUI startup
- **WHEN** the user launches the desktop shortcut
- **THEN** a native application window opens and no listening network port is created for the interface

### Requirement: Main navigation
**GUI-002.** The main window SHALL expose Home, Data, Universes, Training, Results, Run History, and Settings/Diagnostics through a single-window navigation model.

#### Scenario: Navigate without losing state
- **WHEN** the user switches pages during an idle or running job
- **THEN** the selected dataset, universe, configuration, and job state remain consistent

### Requirement: First-run guide
**GUI-003.** The first-run guide SHALL cover the research disclaimer, storage location, environment diagnosis, universe selection, data initialization, and first run; it SHALL be skippable and reopenable.

#### Scenario: Skip before data is ready
- **WHEN** the user skips the guide before a validated dataset exists
- **THEN** browsing and settings remain available while training actions remain disabled with an explanation

### Requirement: One-click weekly run
**GUI-004.** Home SHALL offer one primary action that diagnoses the environment, checks data, publishes any valid update, trains when data/model identity requires it, predicts, and records the result.

#### Scenario: Reuse verified artifacts
- **WHEN** the active data generation and compatible model/result generation already match
- **THEN** the action reuses the verified result instead of retraining and records a cache hit

#### Scenario: Data changed
- **WHEN** a new data generation is published
- **THEN** the action retrains before producing a result for that generation

### Requirement: Honest progress and details
**GUI-005.** The GUI SHALL show stage, elapsed time, concise status, and exact progress only for measurable work; technical logs SHALL be opt-in and copyable/exportable.

#### Scenario: Indeterminate training stage
- **WHEN** a training phase has no reliable completion percentage
- **THEN** the GUI shows an indeterminate state rather than a fabricated percentage

### Requirement: Close and crash behavior
**GUI-006.** Closing an idle GUI SHALL exit fully; closing during a job SHALL request confirmation, attempt graceful cancellation and cleanup, and offer forced termination after a bounded wait while preserving diagnostic logs.

#### Scenario: GUI crash during training
- **WHEN** the GUI process terminates unexpectedly
- **THEN** its owned worker is terminated and the next startup cleans unpublished staging before accepting a new job

### Requirement: Single instance
**GUI-007.** Only one GUI instance SHALL own an application data root at a time, and repeated launch SHALL activate the existing window.

#### Scenario: Repeated shortcut activation
- **WHEN** the user starts Quintara while its GUI already runs
- **THEN** the existing window is focused and no second writer process starts

### Requirement: Theme and scaling
**GUI-008.** The GUI SHALL support light, dark, and system-following themes and SHALL remain usable with Chinese text at Windows 125%, 150%, and 200% scaling and on the supported minimum screen size.

#### Scenario: DPI change
- **WHEN** Windows display scale is 200%
- **THEN** primary actions, tables, dialogs, and text remain visible without clipped controls

### Requirement: Basic keyboard usability
**GUI-009.** Stable v1 SHALL provide predictable tab order, visible keyboard focus, keyboard activation for primary actions, and non-color-only status cues without claiming full accessibility certification.

#### Scenario: Keyboard-only primary flow
- **WHEN** a user navigates the first-run guide and main action with standard keyboard controls
- **THEN** the focused control is visible and every required action can be activated
