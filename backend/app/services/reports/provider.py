"""Generate a lifecycle report with DeepSeek chat completions."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import dotenv_values
from fastapi import HTTPException

from app.schemas.reports import ReportFollowUpRequest

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
        self, facts: dict, *, initial_prompt: str | None = None,
        follow_up: ReportFollowUpRequest | None = None,
    ) -> AsyncIterator[AsyncIterator[dict]]:
        body = {
            "model": self.model, "stream": True, "max_tokens": 8192,
            "messages": report_messages(facts, follow_up, initial_prompt=initial_prompt),
        }
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(60, connect=8)) as client:
                def completion(**options):
                    return client.stream(
                        "POST", f"{self.base_url}/chat/completions", json={**body, **options},
                        headers={"Authorization": f"Bearer {self.api_key}", "Accept": "text/event-stream"},
                    )

                async with completion(thinking={"type": "enabled"}, reasoning_effort="high") as response:
                    _check_provider_response(response)
                    yield self._events(response, direct_answer=completion(thinking={"type": "disabled"}))
        except httpx.TimeoutException:
            raise HTTPException(504, "The report provider timed out. Try again.") from None
        except httpx.RequestError:
            raise HTTPException(502, "Could not reach the report provider. Check LLM_BASE_URL and try again.") from None

    async def _events(
        self, response: httpx.Response, *,
        direct_answer: AbstractAsyncContextManager[httpx.Response] | None = None, started: bool = False,
    ) -> AsyncIterator[dict]:
        has_answer = False
        finish_reason = None
        try:
            async for chunk in _completion_chunks(response):
                choice = chunk["choices"][0]
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}
                for field, event_type in (("reasoning_content", "thinking"), ("content", "delta")):
                    content = delta.get(field)
                    if not isinstance(content, str) or not content:
                        continue
                    if not started:
                        started = True
                        yield {"type": "start", "model": chunk.get("model") or self.model}
                    if event_type == "delta" and content.strip():
                        has_answer = True
                    yield {"type": event_type, "content": content}
            if has_answer:
                yield {"type": "done"}
            elif finish_reason == "length" and direct_answer is not None:
                await response.aclose()
                async with direct_answer as retry:
                    _check_provider_response(retry)
                    async for event in self._events(retry, started=started):
                        yield event
            elif finish_reason == "length":
                yield {"type": "error", "detail": "The report provider reached its output limit before answering. Try again."}
            else:
                yield {"type": "error", "detail": "The report provider returned no text. Try again."}
        except HTTPException as error:
            yield {"type": "error", "detail": error.detail}
        except httpx.TimeoutException:
            yield {"type": "error", "detail": "The report provider timed out. Try again."}
        except (httpx.RequestError, ValueError, AttributeError, TypeError, IndexError):
            yield {"type": "error", "detail": "The report stream was interrupted. Try again."}


async def _completion_chunks(response: httpx.Response) -> AsyncIterator[dict]:
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        if data:
            chunk = json.loads(data)
            if chunk.get("error"):
                break
            if chunk.get("choices"):
                yield chunk
    raise ValueError("Incomplete report stream")


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
