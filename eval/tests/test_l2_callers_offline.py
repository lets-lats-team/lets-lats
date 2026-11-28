"""L2 실제 호출 함수가 SDK와 맞는지 가짜 HTTP 응답으로 확인 (네트워크 없음).
요청 본문에 strict 스키마·store=false가 들어가는지, 응답에서 JSON과 토큰 수를 읽는지, 실패를 None으로 돌리는지 본다."""
import json
import sys
from pathlib import Path

import httpx
import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from l2_eval import callers as C  # noqa: E402
from l2_eval.callers import anthropic_caller, openai_caller  # noqa: E402
from worker.steps.s5_docs.l2.prompt import SCHEMAS  # noqa: E402

TASK = {"role": "L2", "target_key": "x.xlsx#내역서#rows4-7", "affects_output": True,
        "payload": {"kind": "BOQ_ROWS", "prompt": "4 | A:1. 배관", "schema_name": "BOQ_ROWS",
                    "prompt_version": "L2.v3", "system": "sys", "meta": {}}}
ANSWER = {"task": "BOQ_ROWS", "rows": [{"row": 4, "class": "공종 제목"}]}


def mock(sdk_cls, status, body, seen, http):
    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return http.Response(status, json=body)
    return sdk_cls(api_key="test", max_retries=0, http_client=http.Client(transport=http.MockTransport(handler)))


ANTH_OK = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
           "content": [{"type": "text", "text": json.dumps(ANSWER, ensure_ascii=False)}],
           "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 300, "output_tokens": 20}}
OAI_OK = {"id": "resp_1", "object": "response", "created_at": 0, "status": "completed", "model": "gpt-6-luna",
          "output": [{"type": "message", "id": "m1", "status": "completed", "role": "assistant",
                      "content": [{"type": "output_text", "text": json.dumps(ANSWER, ensure_ascii=False), "annotations": []}]}],
          "usage": {"input_tokens": 250, "output_tokens": 15, "total_tokens": 265,
                    "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
          "parallel_tool_calls": True, "tool_choice": "auto", "tools": []}


def test_anthropic_l2_call():
    import anthropic
    C.CALL_LOG.clear()
    seen = {}
    call = anthropic_caller(client=mock(anthropic.Anthropic, 200, ANTH_OK, seen, httpx2))
    assert call(TASK, "claude-haiku-5-5") == ANSWER
    b = seen["body"]
    assert b["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMAS["BOQ_ROWS"]}}
    assert b["system"] == "sys" and b["model"] == "claude-haiku-5-5"
    assert C.CALL_LOG[-1]["in_tok"] == 300 and C.CALL_LOG[-1]["error"] == ""


def test_anthropic_l2_error_and_truncation():
    import anthropic
    C.CALL_LOG.clear()
    call = anthropic_caller(client=mock(anthropic.Anthropic, 529, {"type": "error", "error": {"type": "overloaded_error", "message": "x"}}, {}, httpx2))
    assert call(TASK, "claude-haiku-5-5") is None
    assert C.CALL_LOG[-1]["error"].endswith("529")
    call = anthropic_caller(client=mock(anthropic.Anthropic, 200, {**ANTH_OK, "stop_reason": "max_tokens"}, {}, httpx2))
    assert call(TASK, "claude-haiku-5-5") is None
    assert C.CALL_LOG[-1]["error"] == "stop_reason=max_tokens"


def test_openai_l2_call():
    import openai
    C.CALL_LOG.clear()
    seen = {}
    call = openai_caller(client=mock(openai.OpenAI, 200, OAI_OK, seen, httpx))
    assert call(TASK, "gpt-6-luna") == ANSWER
    b = seen["body"]
    assert seen["url"].endswith("/responses")
    assert b["store"] is False and b["reasoning"] == {"effort": "low"} and b["instructions"] == "sys"
    assert b["text"]["format"] == {"type": "json_schema", "name": "boq_rows", "schema": SCHEMAS["BOQ_ROWS"], "strict": True}
    assert C.CALL_LOG[-1]["in_tok"] == 250


def test_openai_l2_incomplete():
    import openai
    C.CALL_LOG.clear()
    call = openai_caller(client=mock(openai.OpenAI, 200, {**OAI_OK, "status": "incomplete"}, {}, httpx))
    assert call(TASK, "gpt-6-luna") is None
    assert C.CALL_LOG[-1]["error"] == "status=incomplete"
