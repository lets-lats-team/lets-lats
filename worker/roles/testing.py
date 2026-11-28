"""시험용 엔진 — 공통 엔진이 생기기 전까지 역할 모듈을 끝까지 돌려 보기 위한 가짜 (AI 설계 11.4).

임시본 (2026-11-25). 모델을 부르지 않는다. call(task, model) -> dict | None 로 가짜 응답을 받는다
(eval/l2_eval/callers.py의 gt·fake-wrong과 같은 모양).

11.4 '실행 순서'에서 흉내 내는 것
  3  라우팅: primary, verifier (affects_output이 False면 verifier 없음)
  4  G1 스키마 검사 (재요청은 없음 — 실패는 응답 없음과 같게)
  5  응답이 온 모델마다 module.postprocess
  6  pair_key 짝짓기, 같은 키 중복은 AI_OUT_OF_DOMAIN, 공통 정규화 뒤 value 비교(G5)
  8  상태: 보류 코드가 없으면 PENDING
흉내 내지 않는 것: 1 사전 검사(동의·예산), 7 G4 충돌(S7), 9 저장, 재시도·시간 초과, CallMeta 실측.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

import jsonschema

from .contract import (AIResult, AITask, Candidate, CallMeta, DocumentRef, RoleLimits, RoleModule,
                       first_hold, normalize_text, normalize_unit)

Caller = Callable[[AITask, str], "dict | None"]


@dataclass
class FakeContext:
    """RoleContext 가짜. 토큰 수는 글자 수로 센다 (한국어는 실제보다 크게 잡히는 쪽이라 안전)."""
    paths: dict[UUID, Path]
    role_limits: RoleLimits = field(default_factory=RoleLimits)
    analysis_id: UUID = field(default_factory=uuid4)
    images: dict[str, bytes] = field(default_factory=dict)

    def document_path(self, document_id: UUID) -> Path:
        return self.paths[document_id]

    def limits(self) -> RoleLimits:
        return self.role_limits

    def count_tokens(self, text: str) -> int:
        return len(text)

    def put_image(self, png: bytes, name: str) -> str:
        key = f"analyses/{self.analysis_id}/ai/{name}"
        self.images[key] = png
        return key


def _norm_value(v):
    if isinstance(v, dict):
        return {k: (normalize_unit(x) if k == "unit" and isinstance(x, str) else _norm_value(x)) for k, x in v.items()}
    if isinstance(v, list):
        return [_norm_value(x) for x in v]
    if isinstance(v, str):
        return normalize_text(v)
    return v


def _g1(module: RoleModule, body) -> dict | None:
    if body is None:
        return None
    try:
        jsonschema.validate(body, module.schema)
    except jsonschema.ValidationError:
        return None
    return body


def _keyed(module: RoleModule, cands: list[Candidate]) -> dict[str, Candidate]:
    """pair_key → 후보. 한 모델 응답 안에서 키가 겹치면 그 후보들은 모두 AI_OUT_OF_DOMAIN (11.4)."""
    out: dict[str, Candidate] = {}
    dup: set[str] = set()
    for c in cands:
        k = module.pair_key(c)
        if k in out:
            dup.add(k)
        out.setdefault(k, c)
    for k in dup:
        out[k] = out[k].model_copy(update={"hold_code": "AI_OUT_OF_DOMAIN", "note": "같은 pair_key 중복"})
    return out


def run_task(module: RoleModule, task: AITask, call: Caller, primary: str, verifier: str | None = None) -> list[AIResult]:
    verifier = verifier if task.affects_output else None
    models = [m for m in (primary, verifier) if m]
    bodies = {m: _g1(module, call(task, m)) for m in models}
    calls = [CallMeta(model=m, is_primary=(m == primary), response_id=None, latency_ms=0, tokens_in=0, tokens_out=0)
             for m in models]
    responded = [m for m in models if bodies[m] is not None]
    if primary not in responded and (verifier is None or verifier not in responded):
        return [AIResult(role=task.role, target_key=task.target_key, pair_key=None, status="HELD",
                         hold_code="AI_NO_RESPONSE", candidates={}, agreed=None, source=task.source, calls=calls)]
    keyed = {m: _keyed(module, module.postprocess(task, bodies[m])) for m in responded}
    keys = sorted({k for d in keyed.values() for k in d})
    one_side_missing = verifier is not None and len(responded) == 1
    if not keys:
        if module.allow_empty:
            return []
        code = "AI_NO_RESPONSE" if one_side_missing else "AI_UNREADABLE"
        return [AIResult(role=task.role, target_key=task.target_key, pair_key=None, status="HELD", hold_code=code,
                         candidates={}, agreed=None, source=task.source, calls=calls)]
    results = []
    for k in keys:
        cands = {m: keyed[m][k] for m in responded if k in keyed[m]}
        codes = [c.hold_code for c in cands.values()]
        agreed = None
        if verifier is not None:
            if one_side_missing:
                codes.append("AI_NO_RESPONSE")
            elif len(cands) < 2:
                codes.append("AI_DISAGREE")      # 한쪽 모델에만 있는 후보
                agreed = False
            else:
                a, b = cands[primary], cands[verifier]
                agreed = _norm_value(a.value) == _norm_value(b.value)
                if not agreed:
                    codes.append("AI_DISAGREE")
        code = first_hold(codes)
        results.append(AIResult(role=task.role, target_key=task.target_key, pair_key=k,
                                status="HELD" if code else "PENDING", hold_code=code, candidates=cands,
                                agreed=agreed, source=task.source, calls=calls))
    return results


def run_document(module: RoleModule, ctx: FakeContext, doc: DocumentRef, call: Caller, primary: str,
                 verifier: str | None = None) -> tuple[list[AITask], list[AIResult]]:
    """문서 하나: prepare → 작업마다 run_task. RoleInputError는 그대로 올린다 (감독이 처리)."""
    tasks = module.prepare(ctx, doc)
    results = [r for t in tasks for r in run_task(module, t, call, primary, verifier)]
    return tasks, results
