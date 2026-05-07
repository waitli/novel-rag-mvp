# Novel RAG MVP

一个可容器化部署的小说生成 MVP。目标不是一次性写完整小说，而是建立“生成 -> 抽取记忆 -> RAG 检索 -> 继续生成”的最小闭环。

## 功能

- 项目创建与章节管理
- 故事圣经生成
- 章节大纲生成
- 基于 RAG 上下文生成章节草稿
- 章节定稿后抽取摘要、角色、伏笔、世界观等记忆
- SQLite + FTS5 轻量检索
- Markdown 导出
- Docker / Compose 部署

## 快速启动

```bash
cp .env.example .env
# 编辑 .env，填入 OpenAI 兼容模型配置
docker compose up --build
```

访问：

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- 健康检查: `http://localhost:8000/health`

## API 流程

1. 创建项目

```bash
curl -X POST http://localhost:8000/projects \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "科学修仙路",
    "genre": "科学修仙",
    "premise": "理工科学生穿越修仙世界，用科学方法理解灵气体系。",
    "target_chapters": 20,
    "target_words_per_chapter": 2500,
    "style_guide": "逻辑严谨，升级有代价，避免无脑爽文。"
  }'
```

2. 生成故事圣经

```bash
curl -X POST http://localhost:8000/projects/1/story-bible
```

3. 生成章节大纲

```bash
curl -X POST http://localhost:8000/projects/1/outline
```

4. 检索 RAG 记忆

```bash
curl -X POST http://localhost:8000/projects/1/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"query":"主角 灵气 科学 方法", "limit": 5}'
```

5. 生成章节草稿

```bash
curl -X POST http://localhost:8000/projects/1/chapters/generate \
  -H 'Content-Type: application/json' \
  -d '{"chapter_number":1,"user_instruction":"开篇要有强钩子","save_draft":true}'
```

6. 定稿并抽取记忆

```bash
curl -X POST http://localhost:8000/projects/1/chapters/finalize \
  -H 'Content-Type: application/json' \
  -d '{"chapter_number":1,"text":"这里放最终章节正文"}'
```

## 设计说明

当前 MVP 使用 SQLite FTS5 做轻量 RAG，适合单机容器和早期验证。后续生产化建议替换为：

- PostgreSQL + pgvector 或 Qdrant
- 混合检索：BM25 + embedding
- reranker
- JSON Schema 校验与自动修复
- 异步任务队列
- 前端工作台

## 本地开发

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
DATABASE_PATH=/tmp/novel_rag.sqlite3 uvicorn app.main:app --reload
```
