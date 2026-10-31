"""Provider-agnostic LLM client.

Works with any **OpenAI-compatible** endpoint (OpenAI, Groq, Together, Fireworks,
OpenRouter, vLLM, LM Studio, llama.cpp server, Ollama's /v1 shim) using only
``requests`` — no vendor SDK, no lock-in.

    LLM_PROVIDER=openai_compatible
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_MODEL=llama-3.3-70b-versatile
    LLM_API_KEY=...            # GitHub Secret / server env, never in the repo

    # or fully local and free:
    LLM_PROVIDER=ollama
    LLM_BASE_URL=http://localhost:11434
    LLM_MODEL=llama3.1:8b

If nothing is configured, ``available`` is False and every caller falls back to its
deterministic offline implementation — the platform never breaks because of a missing key.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    latency_ms: int
    raw: Optional[Dict[str, Any]] = None
    fallback: bool = False

    def json(self) -> Any:
        """Extract the first JSON object/array from the answer."""
        return extract_json(self.text)


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> Any:
    """LLMs wrap JSON in prose or fences; pull out the first valid structure."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(text)
    for candidate in candidates:
        candidate = candidate.strip()
        for opener, closer in (("{", "}"), ("[", "]")):
            start = candidate.find(opener)
            end = candidate.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(candidate[start : end + 1])
                except Exception:
                    continue
    return None


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        self.base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
        self.model = os.getenv("LLM_MODEL", "").strip()
        self.api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("HF_TOKEN", "").strip()
        self.timeout = float(os.getenv("LLM_TIMEOUT", "120"))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))

        if self.provider in ("hf", "huggingface", "hf_router"):
            self.provider = "huggingface"
            self.base_url = self.base_url or "https://router.huggingface.co/v1"

        if not self.provider:
            # Sensible defaults so a single env var is enough in practice.
            if self.base_url and "11434" in self.base_url:
                self.provider = "ollama"
            elif self.base_url and "huggingface" in self.base_url:
                self.provider = "huggingface"
            elif self.base_url and self.api_key:
                self.provider = "openai_compatible"

    # ------------------------------------------------------------------ status
    @property
    def available(self) -> bool:
        if self.provider == "ollama":
            return bool(self.base_url and self.model)
        if self.provider in ("openai_compatible", "huggingface"):
            return bool(self.base_url and self.model and self.api_key)
        return False

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider or None,
            "model": self.model or None,
            "base_url": self.base_url or None,
            "has_api_key": bool(self.api_key),
            "available": self.available,
            "hint": (
                "Set LLM_PROVIDER + LLM_BASE_URL + LLM_MODEL (+ LLM_API_KEY or HF_TOKEN for hosted APIs). "
                "Hugging Face: LLM_PROVIDER=huggingface, LLM_MODEL=Qwen/Qwen2.5-72B-Instruct, HF_TOKEN=hf_... "
                "Without them the writer/editor run in deterministic offline mode."
            ),
            "hf_token_present": bool(os.getenv("HF_TOKEN", "").strip()),
        }

    # ------------------------------------------------------------------- calls
    def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: int = 3000,
        json_mode: bool = False,
    ) -> LLMResult:
        if not self.available:
            raise LLMError("LLM is not configured (see LLM_* environment variables)")

        started = time.time()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                if self.provider == "ollama":
                    text, raw = self._call_ollama(system, user, temperature, max_tokens, json_mode)
                else:
                    text, raw = self._call_openai(system, user, temperature, max_tokens, json_mode)
                return LLMResult(
                    text=text,
                    model=self.model,
                    provider=self.provider,
                    latency_ms=int((time.time() - started) * 1000),
                    raw=raw,
                )
            except Exception as exc:  # network / quota / malformed
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))

        raise LLMError(f"{self.provider} call failed: {last_error}")

    # --------------------------------------------------------------- backends
    def _call_openai(self, system, user, temperature, max_tokens, json_mode):
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return text, data

    def _call_ollama(self, system, user, temperature, max_tokens, json_mode):
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"

        response = requests.post(
            f"{self.base_url}/api/chat", data=json.dumps(payload),
            headers={"Content-Type": "application/json"}, timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", ""), data


def get_llm() -> LLMClient:
    return LLMClient()


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+", text or "") if s.strip()]
