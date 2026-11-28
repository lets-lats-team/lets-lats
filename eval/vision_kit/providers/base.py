from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CallResult:
    parsed: Optional[dict]          # 스키마에 맞는 응답 (실패 시 None)
    raw_text: str = ""              # 모델이 돌려준 원문 (평가 결과 폴더에만 저장)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: Optional[str] = None     # TIMEOUT / HTTP_429 / HTTP_5xx / SCHEMA / REFUSAL / MAX_TOKENS ...
    response_id: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class CallOptions:
    model: str
    max_tokens: int = 16000
    timeout_s: float = 120.0
    effort: Optional[str] = None    # 추론 강도 (Luna reasoning.effort / Haiku output_config.effort)
    detail: Optional[str] = None    # Luna 이미지 detail (high / original 등)
    base_url: Optional[str] = None  # openai_compat 전용
