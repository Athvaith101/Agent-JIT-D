"""Nebius Token Factory (OpenAI-compatible) adapter for Nemotron. Proposes only; never a correctness authority."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")


# Process-wide cap on paid model calls. A public deployment with a live key must not be a way to burn tokens.
_budget_lock = threading.Lock()
_budget_used = 0


def budget_limit() -> int:
    try:
        return max(0, int(os.getenv("JITD_MAX_MODEL_CALLS", "300")))
    except ValueError:
        return 300


def persistent_store():
    path = os.getenv('JITD_BUDGET_DB')
    if path:
        from .platform import PlatformStore
        return PlatformStore(Path(path).parent)
    return None


def budget() -> dict:
    store = persistent_store()
    if store:
        used = store.usage()['used']
        return {'limit': budget_limit(), 'used': used, 'remaining': max(0, budget_limit()-used)}
    with _budget_lock:
        return {"limit": budget_limit(), "used": _budget_used, "remaining": max(0, budget_limit() - _budget_used)}


def reset_budget() -> None:
    global _budget_used
    with _budget_lock:
        _budget_used = 0


class BudgetExceeded(RuntimeError):
    """The process-wide model-call cap (JITD_MAX_MODEL_CALLS) is used up. Nothing was sent to the provider."""


def _spend() -> None:
    global _budget_used
    with _budget_lock:
        if _budget_used >= budget_limit():
            raise BudgetExceeded(f"model-call budget exhausted ({budget_limit()} calls; raise JITD_MAX_MODEL_CALLS)")
        _budget_used += 1


def available() -> bool:
    key, model = os.getenv('NEBIUS_API_KEY', '').strip(), os.getenv('NEBIUS_MODEL_ID', '').strip()
    return bool(key and model and not key.startswith('replace_') and not model.startswith('replace_'))


def sanitize(e: Exception) -> str:
    s = f"{type(e).__name__}: {e}"
    key = os.getenv("NEBIUS_API_KEY")
    if key:
        s = s.replace(key, "[redacted]")
    return re.sub(r"(sk|v1)[-_][A-Za-z0-9_\-]{16,}", "[redacted]", s)[:300]


class NebiusClient:
    def __init__(self, meter=None, model: str | None = None, client=None, timeout: float = 45.0):
        self.model = model or os.environ["NEBIUS_MODEL_ID"]
        self.meter = meter
        if client is None:
            from openai import OpenAI
            client = OpenAI(base_url=os.getenv("NEBIUS_BASE_URL", NEBIUS_BASE_URL), api_key=os.environ["NEBIUS_API_KEY"], timeout=timeout, max_retries=0)
        self.client = client
        self.latency_s: list[float] = []

    def complete(self, phase: str, system: str, user: str, max_tokens: int = 900) -> str:
        try:
            output_limit = int(os.getenv('JITD_MODEL_MAX_OUTPUT_TOKENS', str(max_tokens)))
            if not 1 <= output_limit <= 8192:
                raise ValueError()
        except ValueError:
            raise ValueError('Model output limit must be an integer from 1 to 8192; no request was sent') from None
        store = persistent_store()
        call_id = store.reserve_call(budget_limit(), self.model, phase) if store else None
        if not store:
            _spend()
        t0 = time.monotonic()
        try:
            r = self.client.chat.completions.create(model=self.model, max_tokens=output_limit, temperature=0,
                                                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        except Exception:
            elapsed = time.monotonic() - t0
            self.latency_s.append(elapsed)
            if store:
                store.finish_call(call_id, 'failed_usage_unknown', latency_ms=elapsed*1000)
            if self.meter:
                self.meter.record(phase, 0, model=self.model, latency_ms=elapsed*1000, status="failed_usage_unknown")
            raise
        self.latency_s.append(time.monotonic() - t0)
        u = getattr(r, "usage", None)
        if store:
            store.finish_call(call_id, 'completed' if u is not None else 'completed_usage_unknown',
                              getattr(u, 'prompt_tokens', None), getattr(u, 'completion_tokens', None), self.latency_s[-1]*1000)
        if self.meter:
            self.meter.record(phase, getattr(u, "total_tokens", 0) or 0,
                              input_tokens=getattr(u, "prompt_tokens", None),
                              output_tokens=getattr(u, "completion_tokens", None), model=self.model, latency_ms=self.latency_s[-1]*1000)
        return r.choices[0].message.content or ""


def extract_json(text: str):
    """First JSON object in a model reply (models wrap JSON in prose or code fences). Raises ValueError."""
    text = re.sub(r"```(?:json)?", "", text or "")
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in model reply")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            esc = (ch == "\\" and not esc)
            if ch == '"' and not esc:
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON object")
