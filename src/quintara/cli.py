"""Headless command-line interface for Debian/Ubuntu and automation."""
from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import DEFAULT_LABEL, UniverseMode
from .csv_validation import export_issue_sample, validate_csv
from .service import STRATEGIES, QuintaraService, ServiceError


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quintara", description="Quintara 本地 A 股周度组合研究工具")
    parser.add_argument("--root", help="override the application data directory")
    parser.add_argument("--json", action="store_true", help="emit structured JSON (the default output format)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="inspect OS, CPU, memory, GPU and package versions")
    sub.add_parser("bootstrap", help="initialize local folders and recover interrupted staging jobs")
    consent = sub.add_parser("consent", help="view or confirm the local research disclaimer")
    consent_sub = consent.add_subparsers(dest="consent_command", required=True)
    consent_sub.add_parser("status")
    consent_sub.add_parser("accept")
    data = sub.add_parser("data", help="manage immutable market data generations")
    data_sub = data.add_subparsers(dest="data_command", required=True)
    data_sub.add_parser("status")
    data_sub.add_parser("list")
    initialize = data_sub.add_parser("initialize")
    initialize.add_argument("--start-date")
    initialize.add_argument("--end-date")
    validate_data = data_sub.add_parser("validate")
    validate_data.add_argument("path", type=Path)
    validate_data.add_argument("--mapping")
    validate_data.add_argument("--units")
    validate_data.add_argument("--issue-sample", type=Path)
    update = data_sub.add_parser("update", help="login BaoStock and pull the latest market data")
    update.add_argument("--start-date")
    update.add_argument("--end-date")
    update.add_argument("--pit-membership-csv", type=Path)
    update.add_argument("--codes", help="comma-separated codes or a text file for an on-demand extension")
    update.add_argument("--allow-non-pit", action="store_true", help="explicitly acknowledge static current-membership fallback")
    imp = data_sub.add_parser("import", help="validate and import a user CSV without modifying it")
    imp.add_argument("market_csv", type=Path)
    imp.add_argument("--membership-csv", type=Path)
    imp.add_argument("--listing-csv", type=Path)
    imp.add_argument("--mapping", help="JSON object mapping canonical fields to CSV headers")
    imp.add_argument("--units", help="JSON object declaring canonical field units")
    imp.add_argument("--merge-active", action="store_true")
    imp.add_argument("--conflict-precedence", choices=["user", "managed"])
    package_import = data_sub.add_parser("import-package", help="verify and activate a provider ZIP or media directory")
    package_import.add_argument("package", type=Path)
    package_import.add_argument("--platform-tag", default="any")
    csv = sub.add_parser("csv", help="validate an input CSV")
    csv_sub = csv.add_subparsers(dest="csv_command", required=True)
    validate = csv_sub.add_parser("validate")
    validate.add_argument("path", type=Path)
    validate.add_argument("--mapping", help="JSON object mapping canonical fields to CSV headers")
    validate.add_argument("--units", help="JSON object declaring canonical field units")
    validate.add_argument("--issue-sample", type=Path)

    universe = sub.add_parser("universe", help="manage isolated universe routes")
    universe_sub = universe.add_subparsers(dest="universe_command", required=True)
    universe_sub.add_parser("list")
    create = universe_sub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--mode", choices=[mode.value for mode in UniverseMode], required=True)
    create.add_argument("--codes", required=True, help="comma-separated six digit stock IDs or a text file")
    create.add_argument("--ack-warning", default=None)
    create.add_argument("--include-special-status", action="store_true")
    search = universe_sub.add_parser("search", help="search BaoStock listing names/codes")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=50)
    activate = universe_sub.add_parser("activate")
    activate.add_argument("universe_id")
    switch = universe_sub.add_parser("switch")
    switch.add_argument("universe_id")
    import_universe = universe_sub.add_parser("import")
    import_universe.add_argument("codes", help="comma-separated codes or a text file")
    import_universe.add_argument("--name", default="Imported custom universe")
    add_universe = universe_sub.add_parser("add", help="append codes to an existing custom universe")
    add_universe.add_argument("universe_id")
    add_universe.add_argument("codes", help="comma-separated codes or a text file")
    remove_universe = universe_sub.add_parser("remove", help="remove codes from an existing custom universe")
    remove_universe.add_argument("universe_id")
    remove_universe.add_argument("codes", help="comma-separated codes or a text file")

    run = sub.add_parser("run", help="train the selected strategy and write a five-stock result")
    run.add_argument("--mode", choices=[mode.value for mode in UniverseMode])
    run.add_argument("--strategy", choices=sorted(STRATEGIES), default="balanced")
    run.add_argument("--label-contract", default=DEFAULT_LABEL, choices=[DEFAULT_LABEL, "open_t5_over_open_t1_minus_1"])
    run.add_argument("--years", type=int, default=5, help="inclusive history window, 3-10 years")
    run.add_argument("--config", help="JSON object of kernel overrides")
    for alias in ("train", "predict"):
        alias_parser = sub.add_parser(alias, help=f"{alias} alias for the shared run workflow")
        alias_parser.add_argument("--mode", choices=[mode.value for mode in UniverseMode])
        alias_parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="balanced")
        alias_parser.add_argument("--years", type=int, default=5)
        alias_parser.add_argument("--config", help="JSON object of kernel overrides")
    results = sub.add_parser("results", help="inspect a completed run")
    results.add_argument("run_id")
    results.add_argument("--details", action="store_true")
    result_alias = sub.add_parser("result", help="inspect a completed run")
    result_alias.add_argument("run_id")
    result_alias.add_argument("--details", action="store_true")
    runs = sub.add_parser("runs", help="list recent runs")
    runs.add_argument("--limit", type=int, default=20)
    runs.add_argument("--cleanup-preview", action="store_true")
    runs.add_argument("--pin")
    cleanup = sub.add_parser("cleanup", help="preview or remove unpinned old successful runs")
    cleanup.add_argument("--confirm", action="store_true")
    cancel = sub.add_parser("cancel", help="request cooperative cancellation")
    cancel.add_argument("run_id")
    diagnostics = sub.add_parser("diagnostics", help="write a redacted local diagnostics bundle")
    diagnostics.add_argument("--output", type=Path)
    version = sub.add_parser("version", help="show installed version and optional release metadata")
    version.add_argument("--check", action="store_true")
    version.add_argument("--enable", action="store_true", help="enable optional manual/next-start release checks")
    version.add_argument("--disable", action="store_true", help="disable release checks")
    export = sub.add_parser("export", help="export exact result CSV and adjacent provenance manifest")
    export.add_argument("run_id")
    export.add_argument("--output", type=Path)
    export.add_argument("--overwrite", action="store_true")
    sub.add_parser("gui", help="launch the standalone Qt desktop application")

    def add_command_root(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--root", dest="command_root", help=argparse.SUPPRESS)
        for action in command_parser._actions:
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                for child in choices.values():
                    add_command_root(child)

    for command_parser in sub.choices.values():
        add_command_root(command_parser)
    return parser


def _codes(value: str) -> list[str]:
    path = Path(value).expanduser()
    if path.is_file():
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


def _interactive(root: str | None) -> int:
    """Small sequential prompt; intentionally not a full-screen TUI."""
    service = QuintaraService(root)
    try:
        print("Quintara 本地 A 股研究向导")
        print(json.dumps(service.bootstrap(), ensure_ascii=False, indent=2, default=str))
        print("输入 update / run / doctor / quit：")
        choice = input("> ").strip().lower()
        if choice == "update":
            _json(service.update_data())
        elif choice == "run":
            if service.consent_status()["status"] != "CONFIRMED":
                input("请阅读 docs/LEGAL_NOTICE.md 后输入 CONFIRM：")
                service.confirm_consent()
            _json(service.run())
        elif choice == "doctor":
            _json(service.doctor())
        return 0
    finally:
        service.close()


def _run_with_signal_cancellation(service: QuintaraService, operation: Any) -> Any:
    """Turn terminal/SSH termination into a cooperative job cancellation."""
    previous: dict[int, Any] = {}

    def request_stop(signum: int, _frame: Any) -> None:
        del signum
        service.cancel_active()

    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is not None:
            previous[number] = signal.getsignal(number)
            signal.signal(number, request_stop)
    try:
        return operation()
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def main(argv: list[str] | None = None) -> int:
    if argv is None and len(sys.argv) == 1 and sys.stdin.isatty():
        return _interactive(None)
    args = build_parser().parse_args(argv)
    root = args.root or getattr(args, "command_root", None)
    if args.command == "gui":
        try:
            from .qml_gui import launch
        except ModuleNotFoundError as exc:
            if exc.name in {"PySide6", "quintara.qml_gui"}:
                print("Quintara GUI 请使用独立的 quintara-gui 或 Quintara 图形入口。", file=sys.stderr)
                return 2
            raise
        return launch(root)
    service = QuintaraService(root)
    try:
        if args.command == "doctor":
            _json(service.doctor())
        elif args.command == "bootstrap":
            _json(service.bootstrap())
        elif args.command == "consent":
            _json(service.consent_status() if args.consent_command == "status" else service.confirm_consent())
        elif args.command == "data":
            if args.data_command in {"status", "list"}:
                _json(service.data_status())
            elif args.data_command == "validate":
                mapping = json.loads(args.mapping) if args.mapping else None
                units = json.loads(args.units) if args.units else None
                report = validate_csv(args.path, mapping, units=units)
                _json(report)
                if args.issue_sample:
                    _json({"issue_sample": str(export_issue_sample(args.path, args.issue_sample, report, mapping=mapping, units=units))})
                if report["status"] == "FAIL":
                    return 3
            elif args.data_command in {"update", "initialize"}:
                _json(service.update_data(start_date=args.start_date, end_date=args.end_date, pit_membership_csv=getattr(args, "pit_membership_csv", None), codes=_codes(args.codes) if getattr(args, "codes", None) else None, allow_non_pit=getattr(args, "allow_non_pit", False)))
            elif args.data_command == "import-package":
                _json(service.import_provider_package(args.package, platform_tag=args.platform_tag))
            else:
                mapping = json.loads(args.mapping) if args.mapping else None
                units = json.loads(args.units) if args.units else None
                _json(service.import_csv(args.market_csv, membership_csv=args.membership_csv, listing_csv=args.listing_csv, mapping=mapping, units=units, merge_active=args.merge_active, conflict_precedence=args.conflict_precedence))
        elif args.command == "csv":
            mapping = json.loads(args.mapping) if args.mapping else None
            units = json.loads(args.units) if args.units else None
            report = validate_csv(args.path, mapping, units=units)
            _json(report)
            if args.issue_sample:
                _json({"issue_sample": str(export_issue_sample(args.path, args.issue_sample, report, mapping=mapping, units=units))})
            if report["status"] == "FAIL":
                return 3
        elif args.command == "universe":
            if args.universe_command == "list":
                _json(service.universes())
            elif args.universe_command in {"activate", "switch"}:
                service.activate_universe(args.universe_id)
                _json({"active": args.universe_id})
            elif args.universe_command == "import":
                _json(service.create_universe(args.name, UniverseMode.CUSTOM_UNIVERSE, _codes(args.codes)))
            elif args.universe_command == "add":
                _json(service.edit_custom_universe(args.universe_id, add_codes=_codes(args.codes)))
            elif args.universe_command == "remove":
                _json(service.edit_custom_universe(args.universe_id, remove_codes=_codes(args.codes)))
            elif args.universe_command == "search":
                _json(service.search_stocks(args.query, limit=args.limit))
            else:
                mode = UniverseMode(args.mode)
                status_filter = "include_special_experiment" if args.include_special_status else "exclude_special"
                _json(service.create_universe(args.name, mode, _codes(args.codes), warning_ack=args.ack_warning, status_filter=status_filter))
        elif args.command in {"run", "train", "predict"}:
            config = json.loads(args.config) if args.config else None
            config = config or {}
            config["training_years"] = args.years
            mode = UniverseMode(args.mode) if args.mode else None
            label_contract = getattr(args, "label_contract", DEFAULT_LABEL)
            _json(_run_with_signal_cancellation(service, lambda: service.run(mode=mode, strategy=args.strategy, label_contract=label_contract, config=config)))
        elif args.command in {"results", "result"}:
            _json(service.result_details(args.run_id) if args.details else service.result_manifest(args.run_id))
        elif args.command == "runs":
            if args.pin:
                service.registry.pin_run(args.pin)
                _json({"pinned": args.pin})
            else:
                _json(service.retention_preview() if args.cleanup_preview else service.runs(args.limit))
        elif args.command == "cleanup":
            _json(service.cleanup_retention(confirm=args.confirm))
        elif args.command == "cancel":
            service.cancel(args.run_id)
            _json({"run_id": args.run_id, "status": "CANCEL_REQUESTED"})
        elif args.command == "diagnostics":
            _json(service.export_diagnostics(args.output))
        elif args.command == "version":
            if args.enable or args.disable:
                _json(service.set_version_check(args.enable and not args.disable))
            else:
                _json(service.version_info(check=args.check))
        elif args.command == "export":
            _json(service.export_result(args.run_id, args.output, overwrite=args.overwrite))
        return 0
    except (ServiceError, ValueError, OSError, RuntimeError) as exc:
        print(f"quintara: {exc}", file=sys.stderr)
        return 4 if "取消" in str(exc) or "cancel" in str(exc).lower() else 2
    finally:
        service.close()
