## Context

See `proposal.md` for motivation and scope. Quintara starts from a Linux-oriented competition application whose domain logic is concentrated in Python modules but whose entry points, locks, durable publication, paths, source closure, and environment checks assume POSIX. The current production kernel uses dated CSI300 membership, an exact-300 PIT contract, LightGBM ranking, fixed portfolio weights, manifest-hash generations, pending/current pointers, and a competition `open(T+5)/open(T+1)-1` label.

The product requirements introduce a standalone desktop application, full headless CLI, user-managed datasets/universes, a `close(T+5)/open(T+1)-1` product label, three isolated identity modes, Windows packaging, local-only privacy, and stable-release evidence. Market data may be large, updates may be interrupted, and a model/result is meaningful only within the exact data, universe, label, feature, kernel, and runtime closure that created it.

## Goals / Non-Goals

**Goals:**

- Keep one domain/application service behind GUI, CLI, and background workers.
- Preserve the audited production kernel as the lineage and differential oracle while implementing the product-label version explicitly.
- Make every mutable dataset/model/result transaction crash recoverable and content addressable.
- Make PIT, custom, and non-PIT identities structurally difficult to mix.
- Provide equivalent durability and lock semantics on Windows and Linux.
- Enable deterministic CPU evidence and separately identified experimental GPU runs.
- Package a self-contained desktop/CLI runtime with platform-native installation behavior.

**Non-Goals:**

- Reproducing domain logic independently in the GUI or CLI.
- Adding a local server, browser UI, cloud backend, account system, broker integration, or telemetry.
- Treating GPU output as bit-identical or authoritative.
- Shipping market data in the installer or publishing a developer-built market-data bundle.
- Expanding v1 to non-A-share instruments, extra financial features, automatic trading, or end-user model tuning.

## Decisions

### 1. Layered modular monolith with owned job workers

```text
Qt GUI ─────────────┐
                    ├── Application Service ── Job Controller ── owned worker boundary
Shell CLI ──────────┘          │                       │
                               ├── Doctor              ├── event stream
                               ├── Data Service         ├── cancellation token
                               ├── Universe Service     └── staged artifacts
                               ├── Kernel Adapter
                               ├── Result Service
                               └── Registries
                                      │
                         Platform + Persistence Ports
```

GUI and CLI are thin adapters over typed application commands and events. The stable v1 GUI runs CPU-heavy training and network updates in owned `QThread` workers so the event loop remains responsive; cancellation requests are recorded in the JSONL event stream and the close path has a bounded force-termination/recovery guard. The CLI keeps the same service boundary and signal handling. A separate worker-process controller remains an explicit cross-platform hardening task rather than an undocumented promise. No HTTP or embedded web server exists.

Alternatives considered:

- In-process threads: simpler, but Python/native training cancellation and crash containment are weaker.
- A permanent local daemon: supports detach/reconnect but adds service installation, authentication, and lifecycle complexity contrary to the local desktop scope.
- Separate GUI/CLI implementations: rejected because behavior and identity rules would drift.

### 2. PySide6 with Qt Widgets for the desktop shell

Qt Widgets offers a stable native desktop model, high-DPI support, mature accessibility primitives for basic keyboard/focus behavior, and direct Python application integration. A page stack and model/view tables implement the fixed navigation. Styling remains application-owned and avoids a second UI framework dependency.

Electron was rejected for runtime size/memory and duplicated web stack. Tauri was rejected because Linux WebKit and Python sidecar packaging complicate the target matrix. QML remains a future option but Widgets minimizes initial build and test surfaces.

### 3. Python package with ports for all platform-sensitive behavior

The domain layer has no OS branches. Platform ports provide:

- `AppPaths`: data/config/cache/log/export roots;
- `FileLock`: exclusive ownership, timeout, owner metadata, stale-lock validation;
- `AtomicPublisher`: durable file write, manifest write, atomic pointer replacement, journal recovery;
- `ProcessController`: spawn, signal, cooperative cancel, bounded force terminate;
- `RuntimeProbe`: CPU/memory/disk/runtime/GPU/OpenCL/network capabilities;
- `SingleInstance`: data-root-scoped activation lock and GUI wakeup;
- `SecretRedactor`: paths/usernames and diagnostic policies.

Windows and POSIX adapters implement the same behavioral contract. Directory `fsync` is used where supported; v1 durability uses atomic file/pointer replacement, immutable generations, hash verification, and startup staging recovery. Full filesystem/registry journal reconciliation and Windows fault-injection proof remain release-hardening tasks called out in `tasks.md`.

### 4. Platform-standard storage with immutable generations

```text
<data-root>/
  registry.sqlite
  data/
    generations/<data_hash>/
    staging/<job_id>/
    active.json
  universes/
    <universe_id>/definition.json
  models/
    <mode>/<universe_id>/generations/<model_hash>/
    <mode>/<universe_id>/active.json
  results/
    <mode>/<universe_id>/generations/<result_hash>/
  jobs/<job_id>/events.jsonl
  logs/
  diagnostics/
  consent.json
  recovery/journal.jsonl
```

SQLite stores searchable metadata, configuration, job/run history, pins, and relationships; large CSV/model artifacts remain files. v1 publication writes immutable files, verifies hashes, atomically replaces the scoped active pointer, and then records registry metadata; startup validates the active closure and removes abandoned staging. A full two-phase filesystem/registry journal and reconciliation pass remains a release-hardening task.

SQLite alone was rejected for large market tables and model blobs. Loose mutable CSV files were rejected because identity, replacement, and crash recovery become ambiguous.

### 5. Three structural model identities

`Mode` is an enum embedded in every universe/data/model/result key:

- `PIT_BASELINE`: dated CSI300 intervals and the strict baseline membership contract;
- `CUSTOM_UNIVERSE`: one named user-defined static A-share pool with survivorship disclosure;
- `NON_PIT_FALLBACK`: an explicitly confirmed degradation created only from the PIT failure flow.

Storage paths, registry compound keys, active pointers, manifests, and application command types all carry mode and universe ID. There is no global model pointer. Compatibility is equality over a canonical `ModelIdentity`:

```text
schema_version
mode + universe_id + universe_generation
market_data_generation + membership_generation + listing_generation + calendar_generation
label_contract + feature_contract + kernel_version + source_hash + config_hash
training_start + training_cutoff + runtime_lock_hash + device_profile
```

A mismatch produces a typed error before inference. `NON_PIT_FALLBACK` cannot be renamed into PIT; restoring PIT creates a new training requirement.

### 6. Versioned kernel profiles separate lineage from product semantics

Two profiles exist in code and tests:

- `competition-open-open-v1`: the unmodified production oracle contract, reachable only by differential tests/developer audit tooling;
- `quintara-weekly-open-close-v1`: the stable product default using `close(T+5)/open(T+1)-1`.

Both reuse the authoritative feature/ranking/model/portfolio implementation through a kernel adapter. Label endpoint calculation is a versioned strategy with explicit columns, gap rules, and embargo assertions. This resolves the owner-approved label change without describing the default product output as byte-identical to the competition generation.

Alternative considered: mutate the competition label in place. Rejected because existing manifests, regression fixtures, and “production alignment” language would become misleading.

### 7. Data lake transaction and source adapters

The BaoStock adapter records immutable per-request checkpoint CSVs and acquisition metadata. A user-supplied PIT membership sidecar is normalized alongside market/listing tables; no external historical PIT provider is silently selected before the source/terms spike is complete. Normalizers produce canonical tables only in staging. Validators build an `InputManifest` and typed findings before publication.

Update state machine:

```text
QUEUED -> PROBING -> DOWNLOADING <-> RETRY_WAIT -> NORMALIZING
       -> VALIDATING -> HASHING -> PUBLISHING -> SUCCEEDED
       -> CANCELLING -> CANCELLED
       -> FAILED
```

Publication is only reachable from `HASHING` after all required validations pass. Network retry is bounded with checkpointed stock/date ranges. An unavailable PIT provider leaves the prior PIT generation active; explicit non-PIT selection is a separate universe command, not an updater branch.

Canonical large tables should use Parquet partitions by data class/year or stock range for efficient incremental access; raw user files and provider receipts remain intact. SQLite indexes generations and partitions.

### 8. CSV validation as a pure report-producing pipeline

CSV ingestion separates:

1. byte-level detection and source hash;
2. field/unit mapping declaration;
3. parse to a staging canonical view;
4. structural, numeric, temporal, universe, and resource validators;
5. conflict analysis and explicit precedence choice;
6. derived-generation publication.

Validators return stable finding codes with severity, field, source row/key, affected scope, and documentation anchor. No validator mutates the original. Noncritical missing indicators pass only when the selected kernel contract explicitly supports them. Problem samples are generated from findings and capped/redacted.

### 9. Application job and cancellation ownership

The application service creates one mutating job per data root under an exclusive lock. Each job owns its worker boundary, cancellation event, append-only event stream, and staging root. GUI close, CLI signal, or explicit cancel follows:

```text
RUNNING -> CANCEL_REQUESTED -> COOPERATIVE_CLEANUP -> CANCELLED
                         \-> timeout -> FORCE_TERMINATED -> RECOVERY_REQUIRED
```

Forced termination never attempts publication. Startup recovery must complete before a new mutating job. Read-only commands can operate against immutable published generations during a job.

### 10. Manifest and canonical hashing

Manifests are UTF-8 canonical JSON with sorted keys, normalized path-independent logical identifiers, explicit schema versions, and SHA-256 hashes. Timestamps, absolute paths, GUI state, and log paths do not affect semantic generation identity. Parent hashes preserve lineage.

- Data manifest: per-source receipt, coverage, normalized schema, keys/counts, validation, terms URI, hashes.
- Universe manifest: mode, constituents/intervals, status policy, minimum gates, PIT confirmation/fallback acknowledgement.
- Model manifest: full `ModelIdentity`, features/config/runtime, fit metrics, data report, model/ranking hashes.
- Result manifest: model identity/hash, cutoff, eligible/excluded counts, ranking/result hashes, disclaimer version.

### 11. Result and explanation generation

Prediction produces a complete ranking first, validates eligibility and tie invariants, then constructs fixed weights. Explanation is derived from model feature contributions and explicitly describes score influence. Risk metrics use adjusted/declared price policy consistently with their manifest and compute 20/60/120-session windows without filling unavailable history.

The result summary reads immutable result artifacts. Export is a new immutable export receipt plus CSV; it does not mutate model or result identity.

### 12. Local-only network policy

Only explicit, user-triggered adapters use the network:

- BaoStock and approved PIT sources for user-confirmed data operations;
- GitHub Releases for an enabled version check;
- supported auxiliary metadata lookup after user confirmation (not enabled as a hidden background call in v1).

The current stable implementation ships BaoStock plus the allowlisted GitHub check;
the PIT source selection and auxiliary provider are tracked as explicit follow-up gates.

There is no analytics client. Requests contain only what the provider protocol requires. Diagnostic bundle generation has no upload method. A network-policy test intercepts outbound attempts and asserts the allowed endpoint/operation matrix.

### 13. Packaging strategy

Use `uv` for locked development/test environments. Stable v1 builds self-contained PyInstaller artifacts from a single Python package. The native packaging spike compares:

- PyInstaller one-folder/one-file plus WiX/Inno Setup on Windows and `.deb` assembly on Linux;
- Briefcase only if it proves compatible with PySide6 and LightGBM wheels across the matrix.

The current release chain is PyInstaller + Inno Setup on Windows and the user-prefix launcher on Linux; clean-runner size, cold start, native-library resolution, uninstall, upgrade, and reproducibility evidence remain package-gate tasks. GPU runtime remains external capability, not a separately trusted product identity.

### 14. Test architecture and release evidence

Tests are layered:

- unit: identities, calendars, labels, status filters, result validator, redaction;
- property: CSV row order, duplicate keys, interval sets, generation canonicalization, weights;
- differential: authoritative competition fixture versus kernel adapter;
- integration: provider fakes, SQLite/filesystem registries, update/import/train/predict;
- fault injection: every publication/cancellation boundary;
- GUI: Qt test harness on Windows/Ubuntu, DPI/theme/single-instance/close flows;
- CLI: direct/interactive commands, exit codes, signals, headless run;
- package smoke: clean install, no-Python launch, CPU fixture, uninstall/reinstall;
- network/privacy: outbound allowlist and zero-telemetry assertion;
- license/legal/docs: SBOM, notice closure, error-code documentation links.

Release evidence is a machine-readable matrix tied to commit and artifact hashes. Stable labeling is computed from required gate status rather than a manual checkbox.

## Risks / Trade-offs

- **[Historical PIT source instability or unclear redistribution terms]** -> Keep provider adapters replaceable, store source/terms receipts, preserve last verified PIT data, and require explicit non-PIT downgrade.
- **[Product label diverges from the competition baseline]** -> Maintain named profiles and differential fixtures; never claim product output is byte-identical to the old label.
- **[Windows native-library and durability differences]** -> Use native CI/package smoke, platform ports, and kill-point recovery tests before declaring support.
- **[PySide6 increases package size and Qt notice obligations]** -> Prefer one UI toolkit, inventory redistributed Qt modules, measure installer size, and include third-party notices.
- **[BaoStock throughput or availability makes first initialization long]** -> Checkpoint downloads, bound retries, show honest per-stock progress, and keep partial raw receipts outside active data.
- **[Full custom pools change ranking semantics]** -> Isolate universes and models, enforce 100-stock gates, disclose static-pool survivorship, and prohibit cross-identity comparisons by default.
- **[GPU numerical variation]** -> Mark GPU experimental, record device closure, retain CPU authority, and never overwrite CPU baseline identity.
- **[Local registry/filesystem split can drift]** -> Journal publication, reconcile on startup, and verify manifest hashes before every active-pointer use.
- **[No telemetry reduces automatic field visibility]** -> Invest in local structured logs, beginner error codes, redacted diagnostic export, and reproducible CI fixtures.
- **[Legal disclaimer alone may be overtrusted]** -> Keep product actions research-oriented, exclude trading execution, version the acknowledgement, and review wording/source terms before release.

## Migration Plan

1. Preserve `/home/olm/bigdata/bigdata/app` as a read-only differential oracle and capture a small redistributable synthetic fixture.
2. Create the Quintara Python package, identity schemas, application-service ports, and platform-neutral kernel adapter.
3. Implement and prove the `competition-open-open-v1` adapter fixture before adding the product label strategy.
4. Add `quintara-weekly-open-close-v1`, calendar/gap/embargo tests, and versioned manifests.
5. Build local registries, data import/update transactions, universe modes, and recovery journal.
6. Add worker job control and CLI, then GUI over the same command/event contracts.
7. Complete packaging spikes, select one release chain, and validate native Windows/Linux packages.
8. Reconcile legacy prose docs, legal/notice materials, and generate the release evidence matrix.
9. Publish only after every required gate is green. Rollback consists of retaining the previous application release and immutable user generations; incompatible schemas stop with migration guidance rather than mutating old generations in place.

## Open Questions

- Which historical CSI300 PIT provider satisfies stability, coverage, attribution, and redistribution requirements after empirical/legal review?
- Which packaging candidate wins the cross-platform spike under measured size, startup, native-library, and uninstall criteria?
- What exact minimum display resolution becomes the tested GUI floor after the first layout prototype?

These questions select providers or packaging parameters within the specified behavior and do not change the capability contracts.
