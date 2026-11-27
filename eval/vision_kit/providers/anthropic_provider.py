"""Claude (Anthropic SDK). 응답 형식은 구조화 출력(output_config.format)으로 강제한다.

AI 설계 11.1은 'Haiku는 도구 하나를 강제'라고 적었지만, Haiku 5.5는 생각(thinking)이 기본으로 켜져 있어
JSON 스키마 구조화 출력을 쓴다. 키는 ANTHROPIC_API_KEY 등 SDK 기본 경로에서 읽는다.
"""
from __future__ import annotations

import base64
import json
import time

import anthropic

from .base import CallOptions, CallResult


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, opts: CallOptions):
        self.opts = opts
        # AI 설계 11.2: 재시도 1회 (429·5xx)
        self.client = anthropic.Anthropic(timeout=opts.timeout_s, max_retries=1)

    def call(self, image_png: bytes, prompt: str, schema: dict, **_) -> CallResult:
        b64 = base64.standard_b64encode(image_png).decode("ascii")
        output_config = {"format": {"type": "json_schema", "schema": schema}}
        if self.opts.effort:
            output_config["effort"] = self.opts.effort
        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(
                model=self.opts.model,
                max_tokens=self.opts.max_tokens,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                output_config=output_config,
            )
        except anthropic.APITimeoutError:
            return CallResult(None, error="TIMEOUT", latency_ms=_ms(t0))
        except anthropic.RateLimitError:
            return CallResult(None, error="HTTP_429", latency_ms=_ms(t0))
        except anthropic.APIStatusError as e:
            return CallResult(None, error=f"HTTP_{e.status_code}", latency_ms=_ms(t0), extra={"message": str(e.message)[:500]})
        except anthropic.APIConnectionError:
            return CallResult(None, error="CONNECTION", latency_ms=_ms(t0))

        usage = resp.usage
        res = CallResult(None, input_tokens=usage.input_tokens or 0, output_tokens=usage.output_tokens or 0,
                         latency_ms=_ms(t0), response_id=resp.id, extra={"stop_reason": resp.stop_reason})
        if resp.stop_reason == "refusal":
            res.error = "REFUSAL"
            return res
        if resp.stop_reason == "max_tokens":
            res.error = "MAX_TOKENS"
            return res
        text = next((b.text for b in resp.content if b.type == "text"), "")
        res.raw_text = text
        try:
            res.parsed = json.loads(text)
        except json.JSONDecodeError:
            res.error = "SCHEMA"
        return res


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)
