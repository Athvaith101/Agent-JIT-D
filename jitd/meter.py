"""Central model-call accounting by phase. The executor never receives a model client; this only counts."""
from __future__ import annotations

import threading
import os
import math

PHASES = ("compile", "replay", "audit", "repair", "explain")


class ModelMeter:
    def __init__(self):
        self._lock = threading.Lock()
        self.calls = {p: 0 for p in PHASES}
        self.tokens = {p: 0 for p in PHASES}
        self.usage = []
        self.runtime_ms = {k: 0.0 for k in ("compile", "execution", "verification", "repair")}

    def record(self, phase: str, tokens: int = 0, *, input_tokens=None, output_tokens=None, model=None, latency_ms=None, status="succeeded"):
        if phase not in self.calls:
            raise ValueError(f"unknown phase {phase!r}")
        with self._lock:
            self.calls[phase] += 1
            self.tokens[phase] += tokens
            self.usage.append({"phase": phase, "input_tokens": input_tokens, "output_tokens": output_tokens,
                               "total_tokens": tokens, "model": model, "latency_ms": latency_ms, "status": status,
                               "source": "provider" if input_tokens is not None and output_tokens is not None else "count_only"})

    def record_runtime(self, phase, ms):
        with self._lock:
            self.runtime_ms[phase] += max(0.0, ms)

    def cost_summary(self, correct_outputs):
        def rate(name):
            try:
                r = float(os.environ[name])
                return r if math.isfinite(r) and r >= 0 else None
            except (KeyError, ValueError):
                return None
        cpu = rate("JITD_RUNTIME_USD_PER_MS")
        inp = rate("JITD_PRICE_INPUT_USD_PER_M")
        out = rate("JITD_PRICE_OUTPUT_USD_PER_M")
        priced = cpu is not None and (not self.usage or inp is not None and out is not None and all(u['source'] == 'provider' for u in self.usage))
        model_cost = sum((u['input_tokens']*inp + u['output_tokens']*out)/1e6 for u in self.usage) if priced and self.usage else 0.0 if priced else None
        total = model_cost + sum(self.runtime_ms.values())*cpu if priced else None
        return {"runtime_ms": dict(self.runtime_ms), "estimated_total_usd": total,
                "cost_per_correct_usd": total/correct_outputs if total is not None and correct_outputs else None,
                "correct_outputs": correct_outputs, "rates": {"runtime_usd_per_ms": cpu, "input_usd_per_m": inp, "output_usd_per_m": out},
                "note": "All attributable runtime stages included; USD is an estimate using configured rates, not provider billing. Missing rates or zero correct outputs => unpriced/undefined."}

    def snapshot(self) -> dict:
        with self._lock:
            return {**{f"{p}_model_calls": n for p, n in self.calls.items()}, "total_model_calls": sum(self.calls.values()),
                    "total_tokens": sum(self.tokens.values())}
