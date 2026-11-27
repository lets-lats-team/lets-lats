"""GPT-6 Luna (OpenAI Responses API, Structured Outputs strict, store=false).

openai_compat: OpenAI 호환 서버(EXAONE 4.5를 vLLM 등으로 띄운 경우)용. Chat Completions + json_schema.
키는 OPENAI_API_KEY (openai_compat는 OPENAI_COMPAT_API_KEY, 없으면 'none').
"""
from __future__ import annotations

import base64
import json
import os
import time

import openai

from .base import CallOptions, CallResult


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _err(e: Exception, t0: float) -> CallResult:
    if isinstance(e, openai.APITimeoutError):
        return CallResult(None, error="TIMEOUT", latency_ms=_ms(t0))
    if isinstance(e, openai.RateLimitError):
        return CallResult(None, error="HTTP_429", latency_ms=_ms(t0))
    if isinstance(e, openai.APIStatusError):
        return CallResult(None, error=f"HTTP_{e.status_code}", latency_ms=_ms(t0), extra={"message": str(e.message)[:500]})
    if isinstance(e, openai.APIConnectionError):
        return CallResult(None, error="CONNECTION", latency_ms=_ms(t0))
    raise e


class OpenAIProvider:
    name = "openai"

    def __init__(self, opts: CallOptions):
        self.opts = opts
        self.client = openai.OpenAI(timeout=opts.timeout_s, max_retries=1)

    def call(self, image_png: bytes, prompt: str, schema: dict, **_) -> CallResult:
        url = "data:image/png;base64," + base64.standard_b64encode(image_png).decode("ascii")
        image = {"type": "input_image", "image_url": url}
        if self.opts.detail:
            image["detail"] = self.opts.detail
        kwargs = dict(
            model=self.opts.model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}, image]}],
            text={"format": {"type": "json_schema", "name": "region_text", "schema": schema, "strict": True}},
            max_output_tokens=self.opts.max_tokens,
            store=False,
        )
        if self.opts.effort:
            kwargs["reasoning"] = {"effort": self.opts.effort}
        t0 = time.perf_counter()
        try:
            resp = self.client.responses.create(**kwargs)
        except Exception as e:  # noqa: BLE001 - _err가 아는 오류만 처리하고 나머지는 다시 던진다
            return _err(e, t0)
        usage = resp.usage
        res = CallResult(None, input_tokens=getattr(usage, "input_tokens", 0) or 0,
                         output_tokens=getattr(usage, "output_tokens", 0) or 0,
                         latency_ms=_ms(t0), response_id=resp.id, extra={"status": getattr(resp, "status", None)})
        if getattr(resp, "status", "completed") == "incomplete":
            res.error = "MAX_TOKENS"
            return res
        res.raw_text = resp.output_text or ""
        try:
            res.parsed = json.loads(res.raw_text)
        except json.JSONDecodeError:
            res.error = "SCHEMA"
        return res


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, opts: CallOptions):
        if not opts.base_url:
            raise SystemExit("--base-url 이 필요합니다 (예: http://localhost:8000/v1)")
        self.opts = opts
        self.client = openai.OpenAI(base_url=opts.base_url, api_key=os.environ.get("OPENAI_COMPAT_API_KEY", "none"),
                                    timeout=opts.timeout_s, max_retries=1)

    def call(self, image_png: bytes, prompt: str, schema: dict, **_) -> CallResult:
        url = "data:image/png;base64," + base64.standard_b64encode(image_png).decode("ascii")
        t0 = time.perf_counter()
        try:
            resp = self.client.chat.completions.create(
                model=self.opts.model,
                max_tokens=self.opts.max_tokens,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": url}},
                ]}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "region_text", "schema": schema, "strict": True}},
            )
        except Exception as e:  # noqa: BLE001
            return _err(e, t0)
        usage = resp.usage
        res = CallResult(None, input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                         output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                         latency_ms=_ms(t0), response_id=resp.id,
                         extra={"finish_reason": resp.choices[0].finish_reason})
        if resp.choices[0].finish_reason == "length":
            res.error = "MAX_TOKENS"
            return res
        res.raw_text = resp.choices[0].message.content or ""
        try:
            res.parsed = json.loads(res.raw_text)
        except json.JSONDecodeError:
            res.error = "SCHEMA"
        return res
