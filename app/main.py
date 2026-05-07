import json
from typing import Any

from fastapi import FastAPI, HTTPException

from .db import get_db, init_db, row_to_dict
from .generation import finalize_chapter, generate_chapter, generate_outline, generate_story_bible
from .rag import add_memory, index_project_seed, retrieve_memories
from .schemas import (
    ChapterUpsert,
    FinalizeChapterRequest,
    GenerateChapterRequest,
    MemoryCreate,
    ProjectCreate,
    RetrieveRequest,
)

app = FastAPI(title="Novel RAG MVP", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects")
def create_project(payload: ProjectCreate) -> dict[str, Any]:
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO projects(title, genre, premise, target_chapters, target_words_per_chapter, style_guide)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.title,
                payload.genre,
                payload.premise,
                payload.target_chapters,
                payload.target_words_per_chapter,
                payload.style_guide,
            ),
        )
        project = row_to_dict(db.execute("SELECT * FROM projects WHERE id = ?", (cursor.lastrowid,)).fetchone())
        if project:
            index_project_seed(db, project)
        return project or {}


@app.get("/projects")
def list_projects() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
        return [row_to_dict(row) or {} for row in rows]


@app.get("/projects/{project_id}")
def get_project(project_id: int) -> dict[str, Any]:
    with get_db() as db:
        project = _get_project_or_404(db, project_id)
        chapters = db.execute(
            "SELECT * FROM chapters WHERE project_id = ? ORDER BY number",
            (project_id,),
        ).fetchall()
        project["chapters"] = [row_to_dict(row) or {} for row in chapters]
        return project


@app.post("/projects/{project_id}/story-bible")
async def create_story_bible(project_id: int) -> dict[str, Any]:
    with get_db() as db:
        project = _get_project_or_404(db, project_id)
        story_bible = await generate_story_bible(db, project)
        return {"story_bible": story_bible}


@app.post("/projects/{project_id}/outline")
async def create_outline(project_id: int) -> dict[str, Any]:
    with get_db() as db:
        project = _get_project_or_404(db, project_id)
        if not project.get("story_bible"):
            raise HTTPException(status_code=409, detail="Generate story bible first.")
        chapters = await generate_outline(db, project)
        return {"chapters": chapters}


@app.put("/projects/{project_id}/chapters/{chapter_number}")
def upsert_chapter(project_id: int, chapter_number: int, payload: ChapterUpsert) -> dict[str, Any]:
    with get_db() as db:
        _get_project_or_404(db, project_id)
        db.execute(
            """
            INSERT INTO chapters(project_id, number, title, outline, draft, final_text, summary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, number) DO UPDATE SET
              title = excluded.title,
              outline = excluded.outline,
              draft = excluded.draft,
              final_text = excluded.final_text,
              summary = excluded.summary,
              status = excluded.status,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                project_id,
                chapter_number,
                payload.title,
                payload.outline,
                payload.draft,
                payload.final_text,
                payload.summary,
                payload.status,
            ),
        )
        row = db.execute(
            "SELECT * FROM chapters WHERE project_id = ? AND number = ?",
            (project_id, chapter_number),
        ).fetchone()
        return row_to_dict(row) or {}


@app.post("/projects/{project_id}/chapters/generate")
async def create_chapter_draft(project_id: int, payload: GenerateChapterRequest) -> dict[str, Any]:
    with get_db() as db:
        project = _get_project_or_404(db, project_id)
        chapter = _get_chapter_or_404(db, project_id, payload.chapter_number)
        return await generate_chapter(
            db,
            project,
            chapter,
            user_instruction=payload.user_instruction,
            save_draft=payload.save_draft,
        )


@app.post("/projects/{project_id}/chapters/finalize")
async def finalize(project_id: int, payload: FinalizeChapterRequest) -> dict[str, Any]:
    with get_db() as db:
        project = _get_project_or_404(db, project_id)
        chapter = _get_chapter_or_404(db, project_id, payload.chapter_number)
        return await finalize_chapter(db, project, chapter, payload.text)


@app.post("/projects/{project_id}/memories")
def create_memory(project_id: int, payload: MemoryCreate) -> dict[str, Any]:
    with get_db() as db:
        _get_project_or_404(db, project_id)
        return add_memory(db, project_id, payload)


@app.post("/projects/{project_id}/retrieve")
def retrieve(project_id: int, payload: RetrieveRequest) -> dict[str, Any]:
    with get_db() as db:
        _get_project_or_404(db, project_id)
        memories = retrieve_memories(db, project_id, payload.query, payload.limit)
        return {"query": payload.query, "memories": memories}


@app.get("/projects/{project_id}/export/markdown")
def export_markdown(project_id: int) -> dict[str, str]:
    with get_db() as db:
        project = _get_project_or_404(db, project_id)
        chapters = db.execute(
            "SELECT * FROM chapters WHERE project_id = ? ORDER BY number",
            (project_id,),
        ).fetchall()
        lines = [
            f"# {project['title']}",
            "",
            f"> 类型：{project.get('genre', '')}",
            f"> 前提：{project.get('premise', '')}",
            "",
        ]
        for row in chapters:
            chapter = row_to_dict(row) or {}
            text = chapter.get("final_text") or chapter.get("draft") or ""
            if not text:
                continue
            lines.extend([f"## 第{chapter['number']}章 {chapter.get('title', '')}", "", text, ""])
        return {"markdown": "\n".join(lines)}


def _get_project_or_404(db, project_id: int) -> dict[str, Any]:
    row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    project = row_to_dict(row)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if isinstance(project.get("story_bible"), str):
        project["story_bible"] = json.loads(project["story_bible"] or "{}")
    return project


def _get_chapter_or_404(db, project_id: int, chapter_number: int) -> dict[str, Any]:
    row = db.execute(
        "SELECT * FROM chapters WHERE project_id = ? AND number = ?",
        (project_id, chapter_number),
    ).fetchone()
    chapter = row_to_dict(row)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    return chapter
