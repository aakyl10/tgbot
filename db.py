import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from utils import json_dumps, user_hash

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  user_hash TEXT NOT NULL,
  chat_id INTEGER,
  city TEXT,
  home_type TEXT,
  heating TEXT,
  people TEXT,
  knows_tariff INTEGER DEFAULT 0,
  reminders INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,                -- current / prev / second
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  days INTEGER NOT NULL,
  kwh REAL,
  money REAL,
  tariff REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions_done (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  action_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  user_hash TEXT NOT NULL,
  session_id TEXT NOT NULL,
  state TEXT NOT NULL,
  event_name TEXT NOT NULL,
  command TEXT,
  payload_json TEXT,
  is_demo INTEGER DEFAULT 0,
  app_version TEXT
);
"""

class DB:
    def __init__(self, path: str = "data.db") -> None:
        self.path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat(timespec="seconds")

    def upsert_user(self, user_id: int, chat_id: int) -> None:
        now = self._now()
        with self._conn() as c:
            row = c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row:
                c.execute(
                    "UPDATE users SET chat_id=?, updated_at=? WHERE user_id=?",
                    (chat_id, now, user_id)
                )
            else:
                c.execute(
                    "INSERT INTO users(user_id,user_hash,chat_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (user_id, user_hash(user_id), chat_id, now, now)
                )

    def set_user_profile(self, user_id: int, **kwargs) -> None:
        if not kwargs:
            return
        now = self._now()
        cols = ", ".join([f"{k}=?" for k in kwargs.keys()])
        vals = list(kwargs.values()) + [now, user_id]
        with self._conn() as c:
            c.execute(f"UPDATE users SET {cols}, updated_at=? WHERE user_id=?", vals)

    def get_user(self, user_id: int) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(r) if r else None

    def save_bill(self, user_id: int, kind: str, start_ts: str, end_ts: str, days: int,
                  kwh: Optional[float], money: Optional[float], tariff: Optional[float]) -> None:
        now = self._now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO bills(user_id,kind,start_ts,end_ts,days,kwh,money,tariff,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (user_id, kind, start_ts, end_ts, days, kwh, money, tariff, now)
            )

    def get_latest_bill(self, user_id: int, kind: str) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute(
                "SELECT * FROM bills WHERE user_id=? AND kind=? ORDER BY id DESC LIMIT 1",
                (user_id, kind)
            ).fetchone()
            return dict(r) if r else None

    def add_action_done(self, user_id: int, action_id: str) -> None:
        now = self._now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO actions_done(user_id,action_id,created_at) VALUES(?,?,?)",
                (user_id, action_id, now)
            )

    def reset_user_data(self, user_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM bills WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM actions_done WHERE user_id=?", (user_id,))
            c.execute("UPDATE users SET city=NULL,home_type=NULL,heating=NULL,people=NULL,knows_tariff=0,reminders=0 WHERE user_id=?", (user_id,))

    def log_event(self, user_id: int, session_id: str, state: str, event_name: str,
                  command: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
                  is_demo: int = 0, app_version: Optional[str] = None) -> None:
        now = self._now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO events(ts_utc,user_hash,session_id,state,event_name,command,payload_json,is_demo,app_version)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    now,
                    user_hash(user_id),
                    session_id,
                    state,
                    event_name,
                    command,
                    json_dumps(payload) if payload is not None else None,
                    is_demo,
                    app_version
                )
            )
