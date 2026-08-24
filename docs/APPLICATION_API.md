# Quintara application and presentation API

The GUI, CLI, and background jobs share one authoritative
`QuintaraService`. Presentation code uses `ProductUseCases` to translate domain
state into immutable, user-oriented `PageDTO` values.

## Boundaries

```text
QML page → PageViewModel → ProductUseCases → QuintaraService → domain adapters
```

- QML receives `PageDTO.as_dict()` values and invokes controller slots.
- QML does not read SQLite, manifests, files, providers, or the training service directly.
- `ProductUseCases` exposes environment, data, stocks, training, results, and
  history summaries using user-facing Chinese copy.
- `TechnicalDetailsDTO` is the only presentation path for implementation
  identities and copyable diagnostic details.
- `ErrorSummaryDTO` removes the application root and home directory, describes
  impact, and supplies recovery actions.

## Page states

Every page has exactly one of these states:

| State | Meaning |
| --- | --- |
| `loading` | A snapshot is being loaded; navigation remains available. |
| `ready` | The task is available or complete. |
| `empty` | Required user data is absent; a primary next action is supplied. |
| `error` | Loading failed; a redacted summary and recovery action are supplied. |

`NavigationCoordinator` owns the current page and compact-navigation state.
Page state never changes the model/data/result manifest identity.

## Strategy policy

The default is the explicit key `balanced` (稳健平衡). Each strategy has an
independent version recorded in result manifests:

- `strategy-aggressive-v1`
- `strategy-balanced-v1`
- `strategy-conservative-v1`

The strategy changes research ranking preferences. The five portfolio weights
remain `0.40 / 0.25 / 0.15 / 0.12 / 0.08`.
