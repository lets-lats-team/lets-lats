"""실제 API를 부르지 않고(가짜 HTTP 응답) 공급자 코드가 SDK와 맞는지 확인한다.
요청 본문에 이미지·스키마·추론 강도가 들어가는지, 응답에서 JSON과 토큰 수를 읽는지 본다."""
import json
import sys
from pathlib import Path

import httpx
import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vision_kit import prompt as P  # noqa: E402
from vision_kit.providers import CallOptions, get_provider  # noqa: E402

ANSWER = {"task": "REGION_TEXT", "status": "READ", "readings": [{"raw_text": "Ø19.05"}]}
PNG = b"\x89PNG\r\n\x1a\nfake"


def mock_client(sdk_cls, response_json, seen, http=httpx, **kw):
    # anthropic 2.x SDK는 httpx2, openai SDK는 httpx를 쓴다.
    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return http.Response(200, json=response_json)
    return sdk_cls(api_key="test", http_client=http.Client(transport=http.MockTransport(handler)), **kw)


def test_anthropic_request_and_parse(monkeypatch):
    import anthropic
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    p = get_provider("anthropic", CallOptions(model="claude-haiku-5-5", effort="low"))
    seen = {}
    p.client = mock_client(anthropic.Anthropic, {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
        "content": [{"type": "text", "text": json.dumps(ANSWER)}],
        "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 1200, "output_tokens": 40},
    }, seen, http=httpx2)
    r = p.call(PNG, P.PROMPT, P.SCHEMA)
    assert r.error is None and r.parsed == ANSWER
    assert (r.input_tokens, r.output_tokens) == (1200, 40)
    body = seen["body"]
    assert seen["url"].endswith("/v1/messages")
    assert body["output_config"] == {"format": {"type": "json_schema", "schema": P.SCHEMA}, "effort": "low"}
    assert body["messages"][0]["content"][0]["type"] == "image"


def test_anthropic_refusal(monkeypatch):
    import anthropic
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    p = get_provider("anthropic", CallOptions(model="claude-haiku-5-5"))
    p.client = mock_client(anthropic.Anthropic, {
        "id": "msg_2", "type": "message", "role": "assistant", "model": "claude-haiku-5-5", "content": [],
        "stop_reason": "refusal", "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 0},
    }, {}, http=httpx2)
    assert p.call(PNG, P.PROMPT, P.SCHEMA).error == "REFUSAL"


def test_openai_responses_request_and_parse(monkeypatch):
    import openai
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    p = get_provider("openai", CallOptions(model="gpt-6-luna", effort="low", detail="high"))
    seen = {}
    p.client = mock_client(openai.OpenAI, {
        "id": "resp_1", "object": "response", "created_at": 0, "status": "completed", "model": "gpt-6-luna",
        "output": [{"type": "message", "id": "m1", "status": "completed", "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(ANSWER), "annotations": []}]}],
        "usage": {"input_tokens": 900, "output_tokens": 30, "total_tokens": 930,
                  "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
        "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
    }, seen)
    r = p.call(PNG, P.PROMPT, P.SCHEMA)
    assert r.error is None and r.parsed == ANSWER
    assert (r.input_tokens, r.output_tokens) == (900, 30)
    body = seen["body"]
    assert seen["url"].endswith("/responses")
    assert body["store"] is False and body["reasoning"] == {"effort": "low"}
    assert body["text"]["format"]["strict"] is True
    assert body["input"][0]["content"][1] == {"type": "input_image", "image_url": body["input"][0]["content"][1]["image_url"], "detail": "high"}


def test_openai_compat_chat(monkeypatch):
    import openai
    p = get_provider("openai_compat", CallOptions(model="exaone", base_url="http://localhost:9/v1"))
    seen = {}
    p.client = mock_client(openai.OpenAI, {
        "id": "c1", "object": "chat.completion", "created": 0, "model": "exaone",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(ANSWER)}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 5, "total_tokens": 55},
    }, seen, base_url="http://localhost:9/v1")
    r = p.call(PNG, P.PROMPT, P.SCHEMA)
    assert r.error is None and r.parsed == ANSWER and r.input_tokens == 50
    assert seen["body"]["response_format"]["type"] == "json_schema"
