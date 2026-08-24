# Quintara QML component catalog

The release presentation uses Qt Quick Controls 2 with a repository-owned,
Fluent-inspired token layer. Business state reaches QML only through
`QmlBackend` and presentation DTOs.

## Context checklist

- Target: Windows 11 desktop first; Ubuntu/Debian and WSLg supported.
- Geometry: rectangular resizable window, minimum 960×640, primary 1200×760.
- Scale: 100%–200% desktop DPI; layouts use Qt Quick Layouts.
- Design language: Fluent-inspired hierarchy over Qt Quick Controls Basic.
- Priority: next user action, readiness and Top-5 results; technical identities are secondary.
- Viewing distance: desk, approximately 60 cm.
- Locale/input: Simplified Chinese, keyboard and mouse; stable accessible names.

## Tokens

`Theme.qml` owns semantic light/dark colors, typography, spacing, radii,
navigation widths, 44 px click targets, motion durations, shadow and focus color. The Chinese family list falls through Segoe UI Variable, Microsoft YaHei UI, Noto Sans CJK SC and the platform sans-serif. Components reference role names rather than
raw colors.

## Components

| Component | Purpose |
| --- | --- |
| `AppButton` | 44 px primary/secondary action with visible focus. |
| `StatusBadge` | Text-plus-color status cue. |
| `StatusCard` | Readiness/next-action card. |
| `EmptyState` | Explains missing prerequisites and gives one action. |
| `ErrorState` | Redacted failure and retry action. |
| `SkeletonBlock` | Reduced-motion-aware loading placeholder. |
| `TechnicalDrawer` | Escape-closeable, selectable technical details. |
| `DataTable` | Responsive semantic list/table for pools, jobs, history and Top-5. |
| `ConfirmDialog` | Escape-closeable destructive/transfer/overwrite confirmation. |
| `OnboardingDialog` | Resumable five-step first-use workflow. |
| `WorkspacePage` | Responsive renderer for page DTOs. |
| `AppShell` | Wide/compact navigation and current page host. |

All user-visible literals use `qsTr`, interactive controls are keyboard
reachable, state pairs text with color, and the shell keeps navigation usable
while page content changes.
