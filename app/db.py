import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import settings


def _connect() -> sqlite3.Connection:
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              genre TEXT NOT NULL DEFAULT '',
              premise TEXT NOT NULL DEFAULT '',
              target_chapters INTEGER NOT NULL DEFAULT 20,
              target_words_per_chapter INTEGER NOT NULL DEFAULT 2500,
              style_guide TEXT NOT NULL DEFAULT '',
              story_bible TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chapters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              number INTEGER NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              outline TEXT NOT NULL DEFAULT '',
              draft TEXT NOT NULL DEFAULT '',
              final_text TEXT NOT NULL DEFAULT '',
              summary TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'planned',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(project_id, number)
            );

            CREATE TABLE IF NOT EXISTS memories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              source_type TEXT NOT NULL,
              source_id TEXT NOT NULL DEFAULT '',
              title TEXT NOT NULL DEFAULT '',
              body TEXT NOT NULL,
              metadata TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
              title,
              body,
              content='memories',
              content_rowid='id',
              tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
              INSERT INTO memory_fts(rowid, title, body)
              VALUES (new.id, new.title, new.body);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
              INSERT INTO memory_fts(memory_fts, rowid, title, body)
              VALUES ('delete', old.id, old.title, old.body);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
              INSERT INTO memory_fts(memory_fts, rowid, title, body)
              VALUES ('delete', old.id, old.title, old.body);
              INSERT INTO memory_fts(rowid, title, body)
              VALUES (new.id, new.title, new.body);
            END;
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("story_bible", "metadata"):
        if key in data:
            data[key] = json.loads(data[key] or "{}")
    return data
