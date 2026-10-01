"""Histórico local (SQLite) e estatísticas de uso."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

TYPING_WPM = 40  # velocidade média de digitação usada para estimar o tempo economizado

SCHEMA = """
CREATE TABLE IF NOT EXISTS ditados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    app TEXT, style TEXT, mode TEXT,
    raw TEXT, final TEXT,
    audio_seconds REAL, latency_seconds REAL, words INTEGER
)
"""


@dataclass
class Entry:
    id: int
    ts: float
    app: str
    style: str
    mode: str
    raw: str
    final: str
    audio_seconds: float
    latency_seconds: float
    words: int


class History:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute(SCHEMA)
        self._lock = threading.Lock()

    def add(self, *, app: str, style: str, mode: str, raw: str, final: str,
            audio_seconds: float, latency_seconds: float) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO ditados (ts, app, style, mode, raw, final, audio_seconds, latency_seconds, words)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (time.time(), app, style, mode, raw, final, audio_seconds, latency_seconds,
                 len(final.split())),
            )

    def recent(self, limit: int = 20, search: Optional[str] = None) -> List[Entry]:
        sql = "SELECT * FROM ditados"
        args: list = []
        if search:
            sql += " WHERE final LIKE ?"
            args.append(f"%{search}%")
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            return [Entry(*row) for row in self._db.execute(sql, args)]

    def last(self) -> Optional[Entry]:
        rows = self.recent(1)
        return rows[0] if rows else None

    def stats(self) -> dict:
        with self._lock:
            n, words, audio, latency = self._db.execute(
                "SELECT COUNT(*), COALESCE(SUM(words),0), COALESCE(SUM(audio_seconds),0),"
                " COALESCE(AVG(latency_seconds),0) FROM ditados").fetchone()
        typing_minutes = words / TYPING_WPM
        return {
            "ditados": n,
            "palavras": words,
            "minutos_falando": round(audio / 60, 1),
            "minutos_economizados": round(max(typing_minutes - audio / 60, 0), 1),
            "palavras_por_minuto": round(words / (audio / 60), 0) if audio else 0,
            "espera_media_s": round(latency, 2),
        }

    def clear(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM ditados")
