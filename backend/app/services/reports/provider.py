"""Generate a lifecycle report with DeepSeek chat completions."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import dotenv_values
from fastapi import HTTPException

from app.schemas.reports import ReportFollowUpRequest

from .facts import ReportFacts
from .messages import report_messages

DEFAULT_MODEL = "deepseek-flash"


@dataclass(frozen=True)
class ReportClient:
    base_url: str
    api_key: str = field(repr=False)
    model: str
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls, path: Path) -> "ReportClient":
        config = {**dotenv_values(path, interpolate=False), **os.environ}
        return cls(
            base_url=(config.get("LLM_BASE_URL") or "").strip().rstrip("/"),
            api_key=(config.get("LLM_API_KEY") or "").strip(),
            model=(config.get("LLM_MODEL") or "").strip() or DEFAULT_MODEL,
        )

    def check_ready(self):
        if not self.base_url or not self.api_key:
            raise HTTPException(503, "Set LLM_BASE_URL and LLM_API_KEY in backend/.env, then restart the backend.")
        try:
            url = httpx.URL(self.base_url)
            if url.scheme not in ("http", "https") or not url.host or url.query or url.fragment or url.userinfo:
                raise ValueError()
        except (httpx.InvalidURL, ValueError) as error:
            raise HTTPException(503, "Check LLM_BASE_URL in backend/.env, then restart the backend.") from error

    @asynccontextmanager
    async def stream(
        self, facts: ReportFacts, *, follow_up: ReportFollowUpRequest | None = None,
    ) -> AsyncIterator[AsyncIterator[dict]]:
        body = {
            "model": self.model, "stream": True, "thinking": {"type": "enabled"},
            "max_tokens": 4096,
            "messages": report_messages(facts, follow_up),
        }
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(60, connect=8)) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions", json=body,
                    headers={"Authorization": f"Bearer {self.api_key}", "Accept": "text/event-stream"},
                ) as response:
                    _check_provider_response(response)
                    yield self._events(response, facts)
        except httpx.TimeoutException:
            raise HTTPException(504, "The report provider timed out. Try again.") from None
        except httpx.RequestError:
            raise HTTPException(502, "Could not reach the report provider. Check LLM_BASE_URL and try again.") from None

    async def _events(self, response: httpx.Response, facts: ReportFacts) -> AsyncIterator[dict]:
        started = False
        try:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    if started:
                        yield {"type": "done"}
                    else:
                        yield {"type": "error", "detail": "The report provider returned no text. Try again."}
                    return
                if not data:
                    continue
                chunk = json.loads(data)
                if chunk.get("error"):
                    break
                choices = chunk.get("choices")
                if not choices:
                    continue
                content = choices[0].get("delta", {}).get("content")
                if not isinstance(content, str) or not content:
                    continue
                if not started:
                    started = True
                    yield {
                        "type": "start",
                        "model": chunk.get("model") or self.model,
                        "node_labels": {alias: account for account, alias in facts.aliases.items()},
                    }
                yield {"type": "delta", "content": content}
        except httpx.TimeoutException:
            yield {"type": "error", "detail": "The report provider timed out. Try again."}
            return
        except (httpx.RequestError, ValueError, AttributeError, TypeError, IndexError):
            pass  # Preserve any text delivered before the stream failed.
        yield {"type": "error", "detail": "The report stream was interrupted. Try again."}


def _check_provider_response(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise HTTPException(502, "The report provider rejected the API key. Check backend/.env and restart the backend.")
    if response.status_code == 402:
        raise HTTPException(502, "The report provider reports insufficient credit.")
    if response.status_code == 429:
        raise HTTPException(429, "The report provider is rate-limiting requests. Try again shortly.")
    if response.status_code == 404:
        raise HTTPException(
            502,
            "The report endpoint or model was not found (HTTP 404). Check LLM_BASE_URL and LLM_MODEL.",
        )
    if response.status_code in (400, 422):
        raise HTTPException(
            502,
            f"The report provider rejected the chat request (HTTP {response.status_code}). "
            "Check the API model ID in LLM_MODEL. DeepSeek Flash uses deepseek-flash.",
        )
    if not response.is_success:
        raise HTTPException(502, "The report provider is unavailable. Try again.")
    if not response.headers.get("content-type", "").startswith("text/event-stream"):
        raise HTTPException(502, "The report provider did not return a readable stream. Try again.")
