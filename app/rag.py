import json
import re
import sqlite3
from typing import Any

from .db import row_to_dict
from .schemas import MemoryCreate


def _fts_query(text: str) -> str:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    if not tokens:
        return '""'
    return " OR ".join(tokens[:24])


def _query_terms(text: str) -> list[str]:
    return [token for token in re.findall(r"[\w\u4e00-\u9fff]+", text) if token]


def add_memory(db: sqlite3.Connection, project_id: int, payload: MemoryCreate) -> dict[str, Any]:
    cursor = db.execute(
        """
        INSERT INTO memories(project_id, source_type, source_id, title, body, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            payload.source_type,
            payload.source_id,
            payload.title,
            payload.body,
            json.dumps(payload.metadata, ensure_ascii=False),
        ),
    )
    row = db.execute("SELECT * FROM memories WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return row_to_dict(row) or {}


def retrieve_memories(db: sqlite3.Connection, project_id: int, query: str, limit: int = 8) -> list[dict[str, Any]]:
    fts_query = _fts_query(query)
    rows: list[sqlite3.Row] = []
    try:
        rows = db.execute(
            """
            SELECT
              m.*,
              bm25(memory_fts) AS rank
            FROM memory_fts
            JOIN memories m ON m.id = memory_fts.rowid
            WHERE memory_fts MATCH ?
              AND m.project_id = ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, project_id, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []

    if rows:
        return [row_to_dict(row) or {} for row in rows]

    terms = _query_terms(query)
    if not terms:
        return []
    clauses = " OR ".join(["m.title LIKE ? OR m.body LIKE ?" for _ in terms])
    params: list[Any] = []
    for term in terms:
        params.extend([f"%{term}%", f"%{term}%"])
    rows = db.execute(
        f"""
        SELECT m.*
        FROM memories m
        WHERE m.project_id = ?
          AND ({clauses})
        ORDER BY m.id DESC
        LIMIT ?
        """,
        [project_id, *params, limit],
    ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def pack_context(memories: list[dict[str, Any]], max_chars: int = 12000) -> str:
    chunks: list[str] = []
    used = 0
    for memory in memories:
        title = memory.get("title") or memory.get("source_type") or "memory"
        body = memory.get("body") or ""
        chunk = f"## {title}\n来源：{memory.get('source_type')}:{memory.get('source_id')}\n{body}".strip()
        if used + len(chunk) > max_chars:
            remaining = max_chars - used
            if remaining > 300:
                chunks.append(chunk[:remaining])
            break
        chunks.append(chunk)
        used += len(chunk)
    return "\n\n".join(chunks)


def index_project_seed(db: sqlite3.Connection, project: dict[str, Any]) -> None:
    story_bible = project.get("story_bible") or {}
    seed_body = "\n".join(
        [
            f"标题：{project.get('title', '')}",
            f"类型：{project.get('genre', '')}",
            f"前提：{project.get('premise', '')}",
            f"风格：{project.get('style_guide', '')}",
            f"故事圣经：{json.dumps(story_bible, ensure_ascii=False)}",
        ]
    )
    add_memory(
        db,
        int(project["id"]),
        MemoryCreate(
            source_type="story_bible",
            source_id=str(project["id"]),
            title="项目基础设定",
            body=seed_body,
            metadata={"kind": "seed"},
        ),
    )
