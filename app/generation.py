import json
import re
import sqlite3
from typing import Any

from . import prompts
from .llm import chat_completion
from .rag import add_memory, pack_context, retrieve_memories
from .schemas import MemoryCreate


def parse_outline(markdown: str) -> list[dict[str, Any]]:
    pattern = re.compile(r"^##\s*第\s*(\d+)\s*章[：: -]*(.*)$", re.MULTILINE)
    matches = list(pattern.finditer(markdown))
    chapters: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        chapters.append(
            {
                "number": int(match.group(1)),
                "title": match.group(2).strip() or f"第{match.group(1)}章",
                "outline": markdown[start:end].strip(),
            }
        )
    return chapters


async def generate_story_bible(db: sqlite3.Connection, project: dict[str, Any]) -> dict[str, Any]:
    response = await chat_completion(prompts.story_bible_prompt(project), max_tokens=4096)
    story_bible = json.loads(_strip_json_fence(response))
    db.execute(
        "UPDATE projects SET story_bible = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(story_bible, ensure_ascii=False), project["id"]),
    )
    add_memory(
        db,
        project["id"],
        MemoryCreate(
            source_type="story_bible",
            source_id=str(project["id"]),
            title="故事圣经",
            body=json.dumps(story_bible, ensure_ascii=False, indent=2),
            metadata={"kind": "story_bible"},
        ),
    )
    return story_bible


async def generate_outline(db: sqlite3.Connection, project: dict[str, Any]) -> list[dict[str, Any]]:
    response = await chat_completion(prompts.outline_prompt(project), max_tokens=8192)
    chapters = parse_outline(response)
    if not chapters:
        raise ValueError("LLM did not return parseable chapter outline.")
    for chapter in chapters:
        db.execute(
            """
            INSERT INTO chapters(project_id, number, title, outline, status)
            VALUES (?, ?, ?, ?, 'outlined')
            ON CONFLICT(project_id, number) DO UPDATE SET
              title = excluded.title,
              outline = excluded.outline,
              status = 'outlined',
              updated_at = CURRENT_TIMESTAMP
            """,
            (project["id"], chapter["number"], chapter["title"], chapter["outline"]),
        )
        add_memory(
            db,
            project["id"],
            MemoryCreate(
                source_type="chapter_outline",
                source_id=str(chapter["number"]),
                title=f"第{chapter['number']}章大纲：{chapter['title']}",
                body=chapter["outline"],
                metadata={"chapter": chapter["number"]},
            ),
        )
    return chapters


async def generate_chapter(
    db: sqlite3.Connection,
    project: dict[str, Any],
    chapter: dict[str, Any],
    user_instruction: str = "",
    save_draft: bool = True,
) -> dict[str, Any]:
    query = "\n".join(
        [
            project.get("title", ""),
            project.get("genre", ""),
            chapter.get("title", ""),
            chapter.get("outline", ""),
            user_instruction,
        ]
    )
    memories = retrieve_memories(db, project["id"], query, limit=10)
    context = pack_context(memories)
    draft = await chat_completion(prompts.chapter_prompt(project, chapter, context, user_instruction), max_tokens=8192)
    if save_draft:
        db.execute(
            """
            UPDATE chapters
            SET draft = ?, status = 'drafted', updated_at = CURRENT_TIMESTAMP
            WHERE project_id = ? AND number = ?
            """,
            (draft, project["id"], chapter["number"]),
        )
    return {"draft": draft, "retrieved_memories": memories}


async def finalize_chapter(
    db: sqlite3.Connection,
    project: dict[str, Any],
    chapter: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    response = await chat_completion(prompts.finalize_prompt(project, chapter, text), max_tokens=4096)
    extracted = json.loads(_strip_json_fence(response))
    summary = extracted.get("chapter_summary", "")
    db.execute(
        """
        UPDATE chapters
        SET final_text = ?, summary = ?, status = 'final', updated_at = CURRENT_TIMESTAMP
        WHERE project_id = ? AND number = ?
        """,
        (text, summary, project["id"], chapter["number"]),
    )
    add_memory(
        db,
        project["id"],
        MemoryCreate(
            source_type="chapter_summary",
            source_id=str(chapter["number"]),
            title=f"第{chapter['number']}章摘要",
            body=summary,
            metadata={"chapter": chapter["number"]},
        ),
    )
    for memory in extracted.get("memories", []):
        add_memory(
            db,
            project["id"],
            MemoryCreate(
                source_type=memory.get("source_type", "note"),
                source_id=str(chapter["number"]),
                title=memory.get("title", ""),
                body=memory.get("body", ""),
                metadata=memory.get("metadata", {}),
            ),
        )
    return extracted


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()
