"""L2 평가용 호출 함수. call(task, model) -> dict | None

- gt          : 정답을 모델 응답 모양으로 돌려준다 (채점기·파이프라인 자체 점검). 정답이 없는 항목은 답하지 않는다.
- fake-wrong  : gt를 일부러 틀리게 바꾼다 (검사·채점이 틀림을 잡는지 확인)
- claude-*    : Anthropic SDK, 구조화 출력 (output_config.format)
- gpt-*       : OpenAI Responses API, Structured Outputs strict, store=false
실제 모델은 내역서 셀 글자를 외부로 보낸다 (AI 설계 16장: 동의 후 실행).
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # lets-lats
sys.path.insert(0, str(ROOT))

from worker.steps.s5_docs.l2.prompt import SCHEMAS  # noqa: E402

from .answers import SetAnswers  # noqa: E402

# 실제 호출 기록 (원문 없음): 작업 키, 모델, 걸린 초, 입력·출력 토큰, 실패 사유
CALL_LOG: list[dict] = []


def _log(task, model, t0, inp=0, out=0, error=""):
    CALL_LOG.append({"target_key": task["target_key"], "kind": task["payload"]["kind"], "model": model,
                     "sec": round(time.monotonic() - t0, 2), "in_tok": inp or 0, "out_tok": out or 0, "error": error})


def gt_caller(answers: dict[str, SetAnswers]):
    by_file = {sa.file: sa for sa in answers.values()}

    def call(task: dict, model: str) -> dict | None:
        p = task["payload"]
        meta = p["meta"]
        sa = by_file.get(meta["file"])
        if sa is None:
            return None
        if p["kind"] == "BOQ_SHEETS":
            items = [{"sheet": n, "sheet_kind": sa.sheets[n]["kind"], "is_qty_sheet": sa.sheets[n]["yn"]}
                     for n in meta["sheets"] if n in sa.sheets and sa.sheets[n]["kind"] and sa.sheets[n]["yn"]]
            return {"task": "BOQ_SHEETS", "sheets": items}
        if p["kind"] == "BOQ_COLUMNS":
            items = []
            for c in meta["cols"]:
                a = sa.columns.get((meta["sheet"], c))
                if a and a["role"]:
                    items.append({"col": c, "role": a["role"], "header_quote": a["header_text"]})
            return {"task": "BOQ_COLUMNS", "columns": items}
        if p["kind"] == "BOQ_ROWS":
            items = [{"row": r, "class": sa.rows[(meta["sheet"], r)]["cls"]}
                     for r in meta["rows"] if (meta["sheet"], r) in sa.rows and sa.rows[(meta["sheet"], r)]["cls"]]
            return {"task": "BOQ_ROWS", "rows": items}
        return None
    return call


def fake_wrong_caller(answers: dict[str, SetAnswers], seed: int = 7):
    """정답에서 일부를 틀리게: 행 분류 10% 바꿈, 열 하나의 인용문 변조, 시트 하나 종류 바꿈."""
    base = gt_caller(answers)
    rnd = random.Random(seed)

    def call(task: dict, model: str) -> dict | None:
        r = base(task, model)
        if r is None:
            return r
        r = json.loads(json.dumps(r))
        if r["task"] == "BOQ_ROWS":
            for x in r["rows"]:
                if rnd.random() < 0.10:
                    x["class"] = "기타" if x["class"] != "기타" else "품목"
        elif r["task"] == "BOQ_COLUMNS" and r["columns"]:
            r["columns"][0]["header_quote"] = "지어낸 머리글"
        elif r["task"] == "BOQ_SHEETS" and r["sheets"]:
            r["sheets"][0]["sheet_kind"] = "기타" if r["sheets"][0]["sheet_kind"] != "기타" else "표지"
        return r
    return call


def anthropic_caller(max_tokens: int = 16000, effort: str | None = None, timeout: float = 60.0, client=None):
    import anthropic
    client = client or anthropic.Anthropic(timeout=timeout, max_retries=1)

    def call(task: dict, model: str) -> dict | None:
        p = task["payload"]
        oc = {"format": {"type": "json_schema", "schema": SCHEMAS[p["schema_name"]]}}
        if effort:
            oc["effort"] = effort
        t0 = time.monotonic()
        try:
            resp = client.messages.create(model=model, max_tokens=max_tokens, system=p["system"],
                                          messages=[{"role": "user", "content": p["prompt"]}], output_config=oc)
        except anthropic.APIStatusError as e:
            _log(task, model, t0, error=f"{type(e).__name__} {e.status_code}")
            return None
        except anthropic.APIConnectionError as e:
            _log(task, model, t0, error=type(e).__name__)
            return None
        u = resp.usage
        if resp.stop_reason in ("refusal", "max_tokens"):
            _log(task, model, t0, u.input_tokens, u.output_tokens, f"stop_reason={resp.stop_reason}")
            return None
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            _log(task, model, t0, u.input_tokens, u.output_tokens, "JSON 해석 실패")
            return None
        _log(task, model, t0, u.input_tokens, u.output_tokens)
        return parsed
    return call


def openai_caller(max_tokens: int = 16000, effort: str | None = "low", timeout: float = 60.0, client=None):
    import openai
    client = client or openai.OpenAI(timeout=timeout, max_retries=1)

    def call(task: dict, model: str) -> dict | None:
        p = task["payload"]
        kw = dict(model=model, instructions=p["system"], input=p["prompt"], store=False, max_output_tokens=max_tokens,
                  text={"format": {"type": "json_schema", "name": p["schema_name"].lower(),
                                   "schema": SCHEMAS[p["schema_name"]], "strict": True}})
        if effort:
            kw["reasoning"] = {"effort": effort}
        t0 = time.monotonic()
        try:
            resp = client.responses.create(**kw)
        except openai.APIStatusError as e:
            _log(task, model, t0, error=f"{type(e).__name__} {e.status_code}")
            return None
        except openai.APIConnectionError as e:
            _log(task, model, t0, error=type(e).__name__)
            return None
        u = getattr(resp, "usage", None)
        inp, out = (getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0)) if u else (0, 0)
        if getattr(resp, "status", "completed") != "completed":
            _log(task, model, t0, inp, out, f"status={resp.status}")
            return None
        try:
            parsed = json.loads(resp.output_text or "")
        except json.JSONDecodeError:
            _log(task, model, t0, inp, out, "JSON 해석 실패")
            return None
        _log(task, model, t0, inp, out)
        return parsed
    return call


def make_router(answers, effort_claude=None, effort_gpt="low"):
    """모델 이름으로 호출 함수를 고른다. 실제 SDK는 처음 쓸 때만 만든다."""
    cache = {}

    def call(task, model):
        if model not in cache:
            if model == "gt":
                cache[model] = gt_caller(answers)
            elif model == "fake-wrong":
                cache[model] = fake_wrong_caller(answers)
            elif model.startswith("claude-"):
                cache[model] = anthropic_caller(effort=effort_claude)
            elif model.startswith("gpt-"):
                cache[model] = openai_caller(effort=effort_gpt)
            else:
                raise SystemExit(f"알 수 없는 모델: {model}")
        return cache[model](task, model)
    return call
