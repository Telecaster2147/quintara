## Purpose

Defines how Quintara is installed, started, upgraded, and removed on supported Windows and Linux systems without requiring users to manage a Python environment.

## ADDED Requirements

### Requirement: Supported platform contract
**IR-001.** The product SHALL guarantee the stable CPU path on Windows 11 x86-64, Ubuntu 22.04/24.04 x86-64, and Debian 12/13 x86-64, and SHALL label Windows 10 22H2 x86-64 as best-effort compatibility.

#### Scenario: Supported platform launch
- **WHEN** a release package is installed on a guaranteed platform
- **THEN** the desktop or CLI entry point starts without a user-installed Python runtime

#### Scenario: Unsupported platform
- **WHEN** the installer or doctor detects an architecture or operating-system version outside the declared matrix
- **THEN** it reports the detected value and the supported matrix before any training begins

### Requirement: Windows installation experience
**IR-002.** The Windows package SHALL install with ordinary user privileges, bundle the locked runtime, create Start-menu and desktop entries, and expose the CLI without requiring Python knowledge.

#### Scenario: Clean Windows installation
- **WHEN** a user without Python installs Quintara
- **THEN** the GUI and CLI launch using only files installed by the package

### Requirement: Linux installation experience
**IR-003.** The Linux release SHALL provide Debian/Ubuntu installation packages and SHALL make the `quintara` CLI available to both desktop and headless users.

#### Scenario: Headless Debian installation
- **WHEN** a user installs Quintara on Debian without a desktop session
- **THEN** the CLI remains fully usable and doctor explains that the graphical entry requires a desktop environment

### Requirement: Platform-standard writable paths
**IR-004.** The application SHALL store configuration, data, models, results, cache, logs, and consent records in platform-standard per-user directories rather than the installation directory.

#### Scenario: Default paths
- **WHEN** Quintara starts with no path override
- **THEN** durable assets are rooted at `%LOCALAPPDATA%/Quintara` on Windows or `~/.local/share/quintara` on Linux

#### Scenario: Non-ASCII user path
- **WHEN** the operating-system user path contains spaces or non-ASCII characters
- **THEN** installation, training, publication, and export preserve the path correctly

### Requirement: Version notice without automatic replacement
**IR-005.** The product SHALL check the latest GitHub Release only when version checks are enabled, display an available version, and require the user to initiate any download or installation.

#### Scenario: New release found
- **WHEN** the version endpoint returns a newer compatible release
- **THEN** Quintara displays the version and release link without changing installed files

### Requirement: Uninstall data choice
**IR-006.** The uninstaller SHALL retain user data and models by default and SHALL offer an explicit option to remove all Quintara user data.

#### Scenario: Default uninstall
- **WHEN** a user uninstalls without selecting data removal
- **THEN** program files are removed and durable user data remains available for reinstallation
