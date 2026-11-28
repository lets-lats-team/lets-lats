"""L3 평가용 호출 함수. call(task: AITask, model) -> dict | None

- gt          : 정답을 모델 응답 모양으로. 묶음이 맡은 조항(private['owned'])의 정답만 돌려준다
- fake-wrong  : gt를 일부러 틀리게 (값 바꿈, 인용문 지어냄, 규칙 빠뜨림, 단위 바꿈)
- claude-*    : Anthropic SDK 구조화 출력 / gpt-* : OpenAI Responses API Structured Outputs strict, store=false
실제 모델은 시방서 조항 원문을 외부로 보낸다 (AI 설계 16장: 동의 후 실행). 키는 환경 변수로만.
"""
from __future__ import annotations

import json
import random
import time

from worker.roles.l3_spec import checks
from worker.roles.l3_spec.module import MODULE

from .answers import SetAnswers

CALL_LOG: list[dict] = []
FAILED_RAW: list[dict] = []   # 끊김·해석 실패 호출의 원래 응답 (진단용, run_l3_eval이 failed_raw/에 저장)
L3_MAX_TOKENS = 4096        # AI 설계 11.2: Haiku L3 4,096
L3_TIMEOUT = 40.0           # AI 설계 11.2: L3 40초
# Haiku 5.5는 thinking을 안 주면 adaptive thinking이 켜져 생각 토큰이 max_tokens를 먹는다 (2026-11-26 실측:
# 5천 자 묶음에서 16000토큰도 끊김, 보이는 JSON은 3.5천 자). 설계서 11.2에 항목 없음 → 끔으로 명시 (트러블슈팅 기록 참고)
L3_HAIKU_THINKING = {"type": "disabled"}


def _log(task, model, t0, inp=0, out=0, error="", raw=None):
    CALL_LOG.append({"target_key": task.target_key, "model": model, "sec": round(time.monotonic() - t0, 2),
                     "in_tok": inp or 0, "out_tok": out or 0, "error": error})
    if raw is not None:
        FAILED_RAW.append({"target_key": task.target_key, "model": model, "error": error,
                           "in_tok": inp or 0, "out_tok": out or 0, "raw": raw})


def gt_caller(answers: dict[str, SetAnswers], doc_sets: dict[str, str]):
    """doc_sets: document_id(str) → 세트."""
    def call(task, model):
        sa = answers.get(doc_sets.get(task.private["document_id"], ""))
        if sa is None:
            return None
        owned = {checks.squash(no) for no in task.private["owned"]}
        rules = [{"clause_no": r.clause_no, "item": r.item, "attribute": r.attribute, "operator": r.operator,
                  "value": r.value, "unit": r.unit, "quote": r.quote}
                 for r in sa.rules if checks.squash(r.clause_no) in owned]
        return {"task": "SPEC_RULES", "rules": rules}
    return call


def fake_wrong_caller(answers, doc_sets, seed: int = 7):
    base = gt_caller(answers, doc_sets)
    rnd = random.Random(seed)

    def call(task, model):
        r = base(task, model)
        if r is None:
            return None
        rules = []
        for x in json.loads(json.dumps(r["rules"])):
            p = rnd.random()
            if p < 0.10:
                continue                                         # 빠뜨림
            if p < 0.25 and any(ch.isdigit() for ch in x["value"]):
                x["value"] = "".join(str((int(ch) + 1) % 10) if ch.isdigit() else ch for ch in x["value"])  # 숫자 바꿈
            elif p < 0.35:
                x["quote"] = "지어낸 인용문 " + x["quote"][:5]   # 인용문 지어냄
            elif p < 0.40 and checks.is_numeric_value(x["value"]):
                x["unit"] = "평"                                 # 목록 밖 단위
            rules.append(x)
        return {"task": "SPEC_RULES", "rules": rules}
    return call


def anthropic_caller(client=None):
    import anthropic
    client = client or anthropic.Anthropic(timeout=L3_TIMEOUT, max_retries=1)

    def call(task, model):
        t0 = time.monotonic()
        try:
            resp = client.messages.create(model=model, max_tokens=L3_MAX_TOKENS, system=MODULE.system_prompt,
                                          thinking=L3_HAIKU_THINKING,
                                          messages=[{"role": "user", "content": task.parts[0].text}],
                                          output_config={"format": {"type": "json_schema", "schema": MODULE.schema}})
        except anthropic.APIStatusError as e:
            _log(task, model, t0, error=f"{type(e).__name__} {e.status_code}")
            return None
        except anthropic.APIConnectionError as e:
            _log(task, model, t0, error=type(e).__name__)
            return None
        u = resp.usage
        text = next((b.text for b in resp.content if b.type == "text"), "")
        blocks = ",".join(b.type for b in resp.content)
        if resp.stop_reason in ("refusal", "max_tokens"):
            _log(task, model, t0, u.input_tokens, u.output_tokens, f"stop_reason={resp.stop_reason}",
                 raw=f"[블록 {blocks}]\n{text}")
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            _log(task, model, t0, u.input_tokens, u.output_tokens, "JSON 해석 실패", raw=f"[블록 {blocks}]\n{text}")
            return None
        _log(task, model, t0, u.input_tokens, u.output_tokens)
        return parsed
    return call


def openai_caller(effort: str | None = "low", client=None):
    import openai
    client = client or openai.OpenAI(timeout=L3_TIMEOUT, max_retries=1)

    def call(task, model):
        kw = dict(model=model, instructions=MODULE.system_prompt, input=task.parts[0].text, store=False,
                  max_output_tokens=L3_MAX_TOKENS,
                  text={"format": {"type": "json_schema", "name": "spec_rules", "schema": MODULE.schema, "strict": True}})
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
            _log(task, model, t0, inp, out, f"status={resp.status}", raw=getattr(resp, "output_text", "") or "")
            return None
        try:
            parsed = json.loads(resp.output_text or "")
        except json.JSONDecodeError:
            _log(task, model, t0, inp, out, "JSON 해석 실패", raw=resp.output_text or "")
            return None
        _log(task, model, t0, inp, out)
        return parsed
    return call


def make_router(answers, doc_sets):
    cache = {}

    def call(task, model):
        if model not in cache:
            if model == "gt":
                cache[model] = gt_caller(answers, doc_sets)
            elif model == "fake-wrong":
                cache[model] = fake_wrong_caller(answers, doc_sets)
            elif model.startswith("claude-"):
                cache[model] = anthropic_caller()
            elif model.startswith("gpt-"):
                cache[model] = openai_caller()
            else:
                raise SystemExit(f"알 수 없는 모델: {model}")
        return cache[model](task, model)
    return call
