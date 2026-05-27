from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS push_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )

    def get_json(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_json(self, key: str, value: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO kv(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), int(time.time())),
            )

    def log_push(self, run_date: str, status: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO push_logs(run_date, status, message, created_at) VALUES (?, ?, ?, ?)",
                (run_date, status, message, int(time.time())),
            )

    def save_snapshot(self, run_date: str, kind: str, payload: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO snapshots(run_date, kind, payload, created_at) VALUES (?, ?, ?, ?)",
                (run_date, kind, json.dumps(payload, ensure_ascii=False), int(time.time())),
            )

