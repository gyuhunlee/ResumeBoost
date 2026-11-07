"""Thin Gemini client: JSON generation + function calling, with 429 backoff.

Uses the REST API over httpx (same approach as gmail/classify.py) so there's no
SDK dependency. Everything else in tailor/ talks to the `LLM` protocol, so tests
can swap in a scripted fake and you could swap providers later.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def generate_json(self, prompt: str, *, temperature: float = 0) -> Any: ...

    def generate(self, contents: list[dict], *, system: str, tools: list[dict],
                 temperature: float = 0.2) -> dict:
        """Returns the model turn: {"role": "model", "parts": [...]}."""
        ...


class Gemini:
    MAX_RETRIES = 3
    MAX_WAIT = 30  # seconds; free-tier RPM limits usually clear within this

    def __init__(self, api_key: str, model: str, timeout: float = 90) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post(self, body: dict) -> dict:
        import httpx  # imported here so the deterministic tools import without it

        url = API.format(model=self.model)
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                r = httpx.post(url, headers={"x-goog-api-key": self.api_key}, json=body, timeout=self.timeout)
            except httpx.TimeoutException as e:
                if attempt < 1:  # one retry; a second slow call would blow the run's time budget
                    log.info("Gemini timed out, retrying once")
                    continue
                raise LLMError(f"Gemini timeout after {self.timeout:.0f}s") from e
            except httpx.HTTPError as e:
                raise LLMError(f"Gemini network error: {e}") from e
            if r.status_code == 429 and "PerDay" in r.text:  # daily quota: waiting won't help
                raise LLMError(f"Gemini 429 daily quota exhausted: {r.text[:300]}")
            if r.status_code in (429, 500, 503) and attempt < self.MAX_RETRIES:
                wait = _retry_delay(r) or 2 ** (attempt + 1)
                log.info("Gemini %s, retrying in %.0fs", r.status_code, wait)
                time.sleep(min(wait, self.MAX_WAIT))
                continue
            if r.status_code >= 400:
                raise LLMError(f"Gemini {r.status_code} [{self.model}]: {r.text[:300]}")
            data = r.json()
            cands = data.get("candidates") or []
            if not cands or "content" not in cands[0]:
                reason = (cands[0].get("finishReason") if cands else None) or data.get("promptFeedback")
                raise LLMError(f"Gemini returned no content ({reason})")
            return cands[0]["content"]
        raise LLMError("Gemini: too many retries")

    def generate_json(self, prompt: str, *, temperature: float = 0) -> Any:
        content = self._post({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": temperature},
        })
        text = "".join(p.get("text", "") for p in content.get("parts", []))
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"Gemini returned invalid JSON: {e}") from e

    def generate(self, contents: list[dict], *, system: str, tools: list[dict],
                 temperature: float = 0.2) -> dict:
        content = self._post({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": tools}],
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"temperature": temperature},
        })
        content.setdefault("role", "model")
        content.setdefault("parts", [])
        return content


def _retry_delay(r: Any) -> float | None:
    """Gemini puts e.g. "retryDelay": "17s" in a RetryInfo error detail."""
    try:
        for d in r.json().get("error", {}).get("details", []):
            if m := re.match(r"([\d.]+)s", str(d.get("retryDelay", ""))):
                return float(m.group(1))
    except Exception:
        pass
    ra = r.headers.get("retry-after") if hasattr(r, "headers") else None
    return float(ra) if ra and ra.isdigit() else None


def get_llm() -> LLM | None:
    """The configured model, or None when no key is set (tools then use rule-based fallbacks)."""
    from ..config import settings

    if not settings.gemini_api_key:
        return None
    return Gemini(settings.gemini_api_key.strip(), clean_model(settings.tailor_model or settings.gemini_model))


def clean_model(name: str) -> str:
    """'models/gemini-3.5-flash', '"gemini-3.5-flash" ' -> 'gemini-3.5-flash' (each of those 404s as-is)."""
    name = name.strip().strip("'\"").strip()
    return name.removeprefix("models/") or "gemini-2.5-flash"
