"""
Gemini API wrapper.

CRITICAL: authentication uses the "x-goog-api-key" HTTP header.
Do NOT use "?key=" query param or "Authorization: Bearer" — some key
formats (the newer "AQ." prefixed keys) only work with this header.
"""
import httpx
from fastapi import HTTPException
from .config import settings

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
CHAT_MODEL = "gemini-2.5-flash"
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768


def _headers() -> dict:
    return {
        "x-goog-api-key": settings.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }


async def generate_content(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.4,
) -> str:
    """Single-turn (or pre-assembled) text generation using gemini-2.5-flash."""
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GEMINI_BASE}/{CHAT_MODEL}:generateContent",
            headers=_headers(),
            json=body,
            timeout=60.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Gemini generateContent error: {resp.text}")

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise HTTPException(status_code=502, detail=f"Unexpected Gemini response shape: {data}")


async def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    task_type: "RETRIEVAL_DOCUMENT" when embedding note chunks to store,
               "RETRIEVAL_QUERY" when embedding a user's chat question.
    Returns a 768-dim float vector (gemini-embedding-001 truncated via
    outputDimensionality — MRL-trained so truncation stays high quality).
    """
    body = {
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": EMBED_DIM,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GEMINI_BASE}/{EMBED_MODEL}:embedContent",
            headers=_headers(),
            json=body,
            timeout=60.0,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Gemini embedContent error: {resp.text}")

    data = resp.json()
    try:
        return data["embedding"]["values"]
    except KeyError:
        raise HTTPException(status_code=502, detail=f"Unexpected embedding response shape: {data}")
