from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def call_google_genai(prompt: str, api_key: str, *, timeout_sec: int = 30) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.warning("Google Gemini fallback failed: %s", exc)
    return None


async def call_anthropic(prompt: str, api_key: str, *, timeout_sec: int = 30) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
    except Exception as exc:
        logger.warning("Anthropic Claude fallback failed: %s", exc)
    return None


async def call_openai(prompt: str, api_key: str, *, timeout_sec: int = 30) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("OpenAI fallback failed: %s", exc)
    return None
