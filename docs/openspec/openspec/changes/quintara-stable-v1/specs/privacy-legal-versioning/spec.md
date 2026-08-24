## Purpose

Defines local-only privacy, redacted diagnostics, version checking, research-risk acknowledgement, legal wording, and redistribution notices for a mainland-China A-share research application.

## ADDED Requirements

### Requirement: Permanent zero telemetry
**PLV-001.** Quintara SHALL NOT transmit usage, hardware, environment, training, universe, result, log, crash, or diagnostic telemetry; all such information SHALL remain local unless the user manually submits selected files.

#### Scenario: Application launch
- **WHEN** Quintara starts
- **THEN** its only possible automatic external request is an enabled version check that carries no product-use payload

### Requirement: Minimal version request
**PLV-002.** An enabled version check SHALL request only the latest GitHub Release resource, SHALL include no Quintara-generated identifiers or user data, and SHALL be disableable in settings.

#### Scenario: Version checks disabled
- **WHEN** the user disables version checks
- **THEN** startup makes no version-related network request

### Requirement: Local redacted diagnostics
**PLV-003.** Diagnostic bundles SHALL be generated only on user request, redact usernames and absolute paths, exclude original market CSV by default, and list included files before creation.

#### Scenario: Generate bundle
- **WHEN** a user confirms diagnostic export
- **THEN** the archive is written locally and no upload is initiated

### Requirement: No automatic screenshots
**PLV-004.** Quintara SHALL NOT capture screenshots; users SHALL decide whether separately created screenshots are included in an external issue.

#### Scenario: GUI error
- **WHEN** a fatal dialog appears
- **THEN** logs and redacted diagnostics remain available but the application captures no screen image

### Requirement: Versioned research acknowledgement
**PLV-005.** First use SHALL require active confirmation of a Chinese research-use and investment-risk statement, record statement version/confirmation time/application version locally, and require reconfirmation after a statement revision.

#### Scenario: Updated statement
- **WHEN** the installed release requires a newer statement version than the local record
- **THEN** result generation remains unavailable until the new statement is displayed and confirmed

### Requirement: Research wording and scope
**PLV-006.** User-facing text SHALL identify Quintara as a mainland-China A-share research tool and SHALL use non-guaranteed model/research language rather than personalized investment instruction or execution language.

#### Scenario: CSV result export
- **WHEN** a result is exported
- **THEN** it records the research disclaimer version and a concise no-guarantee notice

### Requirement: Open-source and third-party notices
**PLV-007.** Source and binary distributions SHALL include the Quintara MIT license, third-party license texts/notices, data-source attribution and terms links, and an SBOM/license inventory for redistributed components.

#### Scenario: Release artifact inspection
- **WHEN** a user opens legal information from an installed package
- **THEN** PySide6/Qt, LightGBM, packaging/runtime dependencies, and data-source notices are discoverable

### Requirement: Local consent and privacy records
**PLV-008.** Consent and settings records SHALL contain no user account identity and SHALL remain in the local configuration store through ordinary runs and version checks.

#### Scenario: Diagnostic review
- **WHEN** consent records appear in a diagnostic bundle
- **THEN** only statement/application versions and timestamps appear, without username or market results
