# Contributing to Quintara

1. Use Python 3.12 and `uv sync --all-groups`.
2. Keep GUI and CLI behavior in `QuintaraService`; do not duplicate kernel rules in a frontend.
3. Preserve route, label, feature, and artifact identities when changing behavior.
4. Add a unit/property/integration test for every validator, parser, publication, or kernel change.
5. Run `ruff`, `ty` (with the documented vendored-kernel exclusion), `pytest`, and `uv build`
   before opening a pull request.
6. Never commit user data, credentials, generated models, `.env`, or diagnostic bundles.

The source competition kernel is vendored under `src/quintara/_kernel`; intentional updates must
include a lineage note and a changed source-closure hash.
