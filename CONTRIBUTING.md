# Contributing to Quintara

1. Use Python 3.12 and `uv sync --all-groups`.
2. Keep GUI and CLI behavior in `QuintaraService`; do not duplicate training rules in a frontend.
3. Preserve route, label, feature, and artifact identities when changing behavior.
4. Add a unit/property/integration test for every validator, parser, publication, or training-component change.
5. Run `ruff`, `ty` (with the documented packaged-component exclusion), `pytest`, and `uv build`
   before opening a pull request.
6. Never commit user data, credentials, generated models, `.env`, or diagnostic bundles.

The packaged training component is versioned with the application; intentional updates must
include a lineage note and a changed source-closure hash.
