import httpx

from .config import settings


class LLMNotConfigured(RuntimeError):
    pass


async def chat_completion(prompt: str, *, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    if not settings.llm_base_url or not settings.llm_api_key or not settings.llm_model:
        raise LLMNotConfigured("LLM_BASE_URL, LLM_API_KEY and LLM_MODEL must be configured.")

    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
