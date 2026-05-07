from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    title: str
    genre: str = ""
    premise: str = ""
    target_chapters: int = Field(default=20, ge=1, le=500)
    target_words_per_chapter: int = Field(default=2500, ge=300, le=10000)
    style_guide: str = ""


class ProjectOut(ProjectCreate):
    id: int
    story_bible: dict[str, Any] = {}


class ChapterUpsert(BaseModel):
    title: str = ""
    outline: str = ""
    draft: str = ""
    final_text: str = ""
    summary: str = ""
    status: str = "planned"


class MemoryCreate(BaseModel):
    source_type: str
    source_id: str = ""
    title: str = ""
    body: str
    metadata: dict[str, Any] = {}


class RetrieveRequest(BaseModel):
    query: str
    limit: int = Field(default=8, ge=1, le=30)


class GenerateChapterRequest(BaseModel):
    chapter_number: int = Field(ge=1)
    user_instruction: str = ""
    save_draft: bool = True


class FinalizeChapterRequest(BaseModel):
    chapter_number: int = Field(ge=1)
    text: str
