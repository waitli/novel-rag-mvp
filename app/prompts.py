import json


def story_bible_prompt(project: dict) -> str:
    return f"""
你是长篇小说总编剧。请基于用户输入生成一个可长期维护的故事圣经。

标题：{project["title"]}
类型：{project.get("genre", "")}
前提：{project.get("premise", "")}
目标章节数：{project.get("target_chapters")}
每章目标字数：{project.get("target_words_per_chapter")}
风格要求：{project.get("style_guide", "")}

请严格输出 JSON，不要解释：
{{
  "core_seed": "一句话故事核心",
  "themes": ["主题1", "主题2"],
  "world_rules": ["世界规则，包含限制"],
  "main_characters": [
    {{"name": "角色名", "role": "protagonist/supporting/antagonist", "goal": "目标", "conflict": "内外冲突"}}
  ],
  "plot_architecture": {{
    "act_1": "开端",
    "act_2": "发展",
    "act_3": "结局"
  }},
  "style_constraints": ["文风约束", "禁忌"]
}}
""".strip()


def outline_prompt(project: dict) -> str:
    return f"""
你是长篇小说策划编辑。请根据故事圣经生成完整章节大纲。

项目：{project["title"]}
类型：{project.get("genre", "")}
章节数：{project.get("target_chapters")}
故事圣经：
{json.dumps(project.get("story_bible", {{}}), ensure_ascii=False, indent=2)}

输出格式必须为 Markdown，每章使用如下格式：
## 第 N 章：标题
- 本章定位：
- 核心事件：
- 出场角色：
- 世界观/设定：
- 伏笔：
- 结尾钩子：

只输出大纲正文。
""".strip()


def chapter_prompt(project: dict, chapter: dict, context: str, user_instruction: str = "") -> str:
    return f"""
你是小说正文作者。请写第 {chapter["number"]} 章正文。

# 小说信息
标题：{project["title"]}
类型：{project.get("genre", "")}
目标字数：约 {project.get("target_words_per_chapter")} 字
风格要求：{project.get("style_guide", "")}

# 故事圣经
{json.dumps(project.get("story_bible", {{}}), ensure_ascii=False, indent=2)}

# 本章大纲
标题：{chapter.get("title", "")}
{chapter.get("outline", "")}

# RAG 检索上下文
{context or "(无检索上下文)"}

# 用户临时要求
{user_instruction or "(无)"}

写作要求：
1. 严格遵守 RAG 上下文中的角色状态、世界规则、伏笔状态。
2. 不要提前写出后续章节结局。
3. 保持章节内有明确场景推进、人物行动和结尾钩子。
4. 只输出正文，不要解释。
""".strip()


def finalize_prompt(project: dict, chapter: dict, text: str) -> str:
    return f"""
你是小说知识库维护系统。请从章节正文中抽取结构化记忆。

小说：{project["title"]}
章节：第 {chapter["number"]} 章 {chapter.get("title", "")}

正文：
{text}

请严格输出 JSON，不要解释：
{{
  "chapter_summary": "200-300字章节摘要",
  "memories": [
    {{
      "source_type": "chapter_summary/character/foreshadowing/world/timeline/style",
      "title": "记忆标题",
      "body": "可供后续 RAG 检索使用的具体信息",
      "metadata": {{"importance": 1, "characters": [], "chapter": {chapter["number"]}}}
    }}
  ]
}}
""".strip()
