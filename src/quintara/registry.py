"""Small SQLite metadata registry for local generations and runs."""
from __future__ import annotations

import json
import sqlite3
import threading
from functools import wraps
from typing import Any

from .core import AppPaths, now_utc


def _synchronized(function: Any) -> Any:
    """Serialize access to the shared SQLite connection across GUI threads."""
    @wraps(function)
    def wrapper(self: Registry, *args: Any, **kwargs: Any) -> Any:
        with self._mutex:
            return function(self, *args, **kwargs)

    return wrapper


class Registry:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self.paths.ensure()
        # GUI refreshes and its worker thread share one service facade.  SQLite
        # serializes the short metadata transactions while the filesystem lock
        # protects long-running publication.
        self.connection = sqlite3.connect(self.paths.registry, timeout=30, check_same_thread=False)
        self.connection.execute("PRAGMA busy_timeout=30000")
        self._mutex = threading.RLock()
        self.connection.row_factory = sqlite3.Row
        self._init()

    @_synchronized
    def _init(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS generations (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, mode TEXT, universe_id TEXT,
              manifest TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS universes (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL,
              definition TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY, state TEXT NOT NULL, mode TEXT, universe_id TEXT,
              data_generation TEXT, model_generation TEXT, result_generation TEXT,
              error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, uri TEXT, metadata TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS models (
              id TEXT PRIMARY KEY, identity TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS results (
              id TEXT PRIMARY KEY, identity TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, run_id TEXT NOT NULL, state TEXT NOT NULL, events_path TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pins (
              run_id TEXT PRIMARY KEY, pinned INTEGER NOT NULL, updated_at TEXT NOT NULL
            );
            """
        )
        for column, definition in (
            ("stage", "TEXT"),
            ("progress", "REAL"),
            ("events_path", "TEXT"),
        ):
            try:
                self.connection.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        self.connection.commit()

    @_synchronized
    def close(self) -> None:
        self.connection.close()

    @_synchronized
    def put_generation(self, generation_id: str, kind: str, manifest: dict[str, Any], *, mode: str | None = None, universe_id: str | None = None, status: str = "active") -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO generations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (generation_id, kind, mode, universe_id, json.dumps(manifest, ensure_ascii=False), status, now_utc()),
        )
        if kind == "model":
            self.connection.execute(
                "INSERT OR REPLACE INTO models (id, identity, status, created_at) VALUES (?, ?, ?, ?)",
                (generation_id, json.dumps(manifest.get("model_identity", {}), ensure_ascii=False), status, now_utc()),
            )
        elif kind == "result":
            self.connection.execute(
                "INSERT OR REPLACE INTO results (id, identity, status, created_at) VALUES (?, ?, ?, ?)",
                (generation_id, json.dumps(manifest.get("model_identity", {}), ensure_ascii=False), status, now_utc()),
            )
        self.connection.commit()

    @_synchronized
    def list_generations(self, kind: str | None = None) -> list[sqlite3.Row]:
        if kind:
            return list(self.connection.execute("SELECT * FROM generations WHERE kind=? ORDER BY created_at DESC", (kind,)))
        return list(self.connection.execute("SELECT * FROM generations ORDER BY created_at DESC"))

    @_synchronized
    def mark_models_stale_for_data(self, active_generation: str) -> int:
        """Mark models whose bound data generation differs from the new active one."""
        rows = list(self.connection.execute("SELECT id, identity FROM models WHERE status='active'"))
        stale = []
        for row in rows:
            try:
                identity = json.loads(row["identity"])
            except (TypeError, json.JSONDecodeError):
                identity = {}
            if identity.get("market_data_generation") != active_generation:
                stale.append(str(row["id"]))
        self.connection.executemany("UPDATE models SET status='stale' WHERE id=?", ((item,) for item in stale))
        self.connection.commit()
        return len(stale)

    @_synchronized
    def put_universe(self, universe_id: str, name: str, mode: str, definition: dict[str, Any], active: bool = False) -> None:
        if active:
            self.connection.execute("UPDATE universes SET active=0")
        self.connection.execute(
            "INSERT OR REPLACE INTO universes VALUES (?, ?, ?, ?, ?, ?)",
            (universe_id, name, mode, json.dumps(definition, ensure_ascii=False), int(active), now_utc()),
        )
        self.connection.commit()

    @_synchronized
    def list_universes(self) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM universes ORDER BY name"))

    @_synchronized
    def active_universe(self) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM universes WHERE active=1 LIMIT 1").fetchone()

    @_synchronized
    def activate_universe(self, universe_id: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE universes SET active=0")
            cur = self.connection.execute("UPDATE universes SET active=1 WHERE id=?", (universe_id,))
            if cur.rowcount != 1:
                raise KeyError(f"universe not found: {universe_id}")

    @_synchronized
    def setting(self, key: str, default: Any = None) -> Any:
        row = self.connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    @_synchronized
    def set_setting(self, key: str, value: Any) -> None:
        self.connection.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value)))
        self.connection.commit()

    @_synchronized
    def start_run(self, run_id: str, mode: str, universe_id: str, events_path: str | None = None) -> None:
        self.connection.execute(
            "INSERT INTO runs (id,state,mode,universe_id,data_generation,model_generation,result_generation,error,created_at,updated_at,pinned,stage,progress,events_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
            (run_id, "RUNNING", mode, universe_id, None, None, None, None, now_utc(), now_utc(), "queued", 0.0, events_path),
        )
        self.connection.execute(
            "INSERT OR REPLACE INTO jobs (id, run_id, state, events_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, run_id, "RUNNING", events_path, now_utc()),
        )
        self.connection.commit()

    @_synchronized
    def finish_run(self, run_id: str, state: str, **values: Any) -> None:
        allowed = {k: v for k, v in values.items() if k in {"data_generation", "model_generation", "result_generation", "error", "stage", "progress", "events_path"}}
        sets = ["state=?", "updated_at=?"]
        params: list[Any] = [state, now_utc()]
        for key, value in allowed.items():
            sets.append(f"{key}=?")
            params.append(value)
        params.append(run_id)
        self.connection.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id=?", params)
        self.connection.execute("UPDATE jobs SET state=? WHERE run_id=?", (state, run_id))
        self.connection.commit()

    @_synchronized
    def list_runs(self, limit: int = 20) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM runs ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT ?", (limit,)))

    @_synchronized
    def run(self, run_id: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()

    @_synchronized
    def pin_run(self, run_id: str, pinned: bool = True) -> None:
        self.connection.execute("UPDATE runs SET pinned=? WHERE id=?", (int(pinned), run_id))
        self.connection.execute("INSERT OR REPLACE INTO pins (run_id, pinned, updated_at) VALUES (?, ?, ?)", (run_id, int(pinned), now_utc()))
        self.connection.commit()

    @_synchronized
    def cleanup_preview(self, keep_successes: int = 5) -> list[dict[str, Any]]:
        rows = list(self.connection.execute("SELECT * FROM runs WHERE state='SUCCEEDED' AND pinned=0 ORDER BY created_at DESC"))
        return [dict(row) for row in rows[max(0, keep_successes):]]
