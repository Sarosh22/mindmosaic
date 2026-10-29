"""Local SQLite storage. The database file never leaves this machine."""
import json
import os
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("MINDMOSAIC_DB", Path(__file__).resolve().parent.parent / "data" / "mindmosaic.db"))


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                text TEXT NOT NULL,
                mood INTEGER,
                emotions TEXT NOT NULL DEFAULT '[]',
                analysis TEXT,
                crisis INTEGER NOT NULL DEFAULT 0
            )"""
        )


def _row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "text": r["text"],
        "mood": r["mood"],
        "emotions": json.loads(r["emotions"]),
        "analysis": json.loads(r["analysis"]) if r["analysis"] else None,
        "crisis": bool(r["crisis"]),
    }


def add_entry(text: str, mood: int | None, emotions: list[str], analysis: dict | None, crisis: bool) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as c:
        cur = c.execute(
            "INSERT INTO entries (created_at, text, mood, emotions, analysis, crisis) VALUES (?,?,?,?,?,?)",
            (now, text, mood, json.dumps(emotions), json.dumps(analysis) if analysis else None, int(crisis)),
        )
        row = c.execute("SELECT * FROM entries WHERE id=?", (cur.lastrowid,)).fetchone()
    return _row(row)


def list_entries(limit: int = 100) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM entries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_row(r) for r in rows]


def delete_entry(entry_id: int) -> bool:
    with connect() as c:
        cur = c.execute("DELETE FROM entries WHERE id=?", (entry_id,))
    return cur.rowcount > 0


def delete_all() -> None:
    with connect() as c:
        c.execute("DELETE FROM entries")


def insights() -> dict:
    """Mood trend and distortion frequency across all entries."""
    entries = list(reversed(list_entries(limit=1000)))
    mood_trend = [{"date": e["created_at"][:10], "mood": e["mood"]} for e in entries if e["mood"] is not None]
    distortions = Counter()
    emotions = Counter()
    for e in entries:
        for em in e["emotions"]:
            emotions[em] += 1
        if e["analysis"]:
            for d in e["analysis"].get("distortions", []):
                distortions[d["name"]] += 1
    return {
        "total_entries": len(entries),
        "mood_trend": mood_trend,
        "distortion_counts": [{"name": k, "count": v} for k, v in distortions.most_common()],
        "emotion_counts": [{"name": k, "count": v} for k, v in emotions.most_common(8)],
    }
