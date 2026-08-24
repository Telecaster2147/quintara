# Kernel lineage and differential boundary

Quintara's model path is a vendored snapshot of the authoritative modules in
`/home/olm/bigdata/bigdata/app/code/src`:

| Product module | Source authority | Product delta |
| --- | --- | --- |
| `src/quintara/_kernel/utils.py` | `app/code/src/utils.py` | Copied unchanged except import/package formatting |
| `src/quintara/_kernel/data.py` | `app/code/src/data.py` | Package-relative utility import |
| `src/quintara/model_config.json` | `app/model/model_config.json` | Packaged copy; product route overrides label identity and fixed weights |
| `src/quintara/kernel.py` | source API calls | Adds product close/open label, identity closure, and installed-build fallback |

The original competition contract remains `competition-open-open-v1`; it is selected only
by an explicit contract argument. Stable v1 uses `quintara-weekly-open-close-v1` and counts
actual observed market sessions. BaoStock extra features remain in generation storage but are
excluded from the stable feature allowlist.

The current source-closure hash is reproducible with:

```bash
uv run python -c "from quintara.kernel import kernel_source_hash; print(kernel_source_hash())"
```

Any change to the vendored modules, adapter, or frozen model configuration changes this hash
and makes prior model identities incompatible. `fixtures/` contains the deterministic synthetic
input used for offline regression; it is never included in release data.
