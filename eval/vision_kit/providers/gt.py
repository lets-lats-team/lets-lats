"""정답을 그대로 돌려주는 가짜 공급자. 채점기 자체 점검용 (100%가 나와야 정상)."""
from __future__ import annotations

import time

from .base import CallOptions, CallResult


class GTProvider:
    name = "gt"

    def __init__(self, opts: CallOptions):
        self.opts = opts

    def call(self, image_png: bytes, prompt: str, schema: dict, *, tile_full_texts: list[str]) -> CallResult:
        t0 = time.perf_counter()
        parsed = {"task": "REGION_TEXT", "status": "READ", "readings": [{"raw_text": t} for t in tile_full_texts]}
        return CallResult(parsed=parsed, raw_text="", latency_ms=int((time.perf_counter() - t0) * 1000))
