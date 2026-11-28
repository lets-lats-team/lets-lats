"""L2 내역서 항목 연결 — 실행 순서와 결과 조립.

모델 호출은 이 모듈이 하지 않는다. 호출 함수(call)를 밖에서 받는다 (gateway는 공통 담당 몫).
  call(task: dict, model: str) -> dict | None     # 스키마 모양의 응답 (실패면 None)

순서
1. BOQ_SHEETS: 파일마다 시트 종류·수량 시트 여부
2. 수량 시트(Y)마다 BOQ_COLUMNS: 열 역할
3. 수량 시트마다 BOQ_ROWS: 행 분류 (50행 묶음)
4. 품목 행의 품명·규격·단위·수량을 원본 셀에서 가져와 문서 값(D06 후보)으로 만든다

교차 확인(AI 설계 7장): verifier가 있으면 같은 작업을 두 모델에 보내 항목별로 비교한다.
  둘 다 통과하고 값이 같으면 PENDING, 다르면 HELD/AI_DISAGREE, 한쪽만 통과하면 HELD/AI_NO_RESPONSE.
수량 시트 판단은 1단계 결과를 따른다. 1단계가 보류된 시트는 2·3단계로 가지 않고 보류로 남는다.

코드 안전장치 (2026-11-25)
- 수량 시트 규칙 (결정 가): 1단계가 PENDING이어도 원가계산서·일위대가 등을 Y로 답했으면 HELD/AI_OUT_OF_DOMAIN.
  ItemResult.rules에 규칙 이름, 시트 메모에 사유. 모델 답은 candidates에 남는다.
- 품목 내보내기: 품명·단위·수량 열이 모두 PENDING일 때만 4단계를 한다. 아니면 메모에 사유.
- 머리글 미탐지: 메모에 어느 행에 무엇만 있었는지 남긴다 (boq_header.header_diagnosis).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..boq_header import header_diagnosis
from ..reader_xlsx import Workbook, read_workbook
from . import gates
from .extract import extract_items
from .tasks import columns_task, header_for, rows_tasks, sheets_task
from .vocab import ITEM_COLS

Caller = Callable[[dict, str], "dict | None"]
AUTO = "코드 규칙"   # 모델이 아니라 코드가 정한 값의 후보 이름


@dataclass
class ItemResult:
    value: object = None
    status: str = "HELD"            # PENDING | HELD
    hold_code: str | None = None
    candidates: dict = field(default_factory=dict)   # 모델 → 값(통과 못 했으면 None)
    rules: list = field(default_factory=list)        # 코드 규칙으로 보류했으면 규칙 이름 ("규칙①", "규칙②")


@dataclass
class SheetResult:
    name: str
    kind: ItemResult
    header_label: str = ""
    columns: dict[str, ItemResult] = field(default_factory=dict)   # 열 글자 → 역할
    header_text: dict[str, str] = field(default_factory=dict)
    rows: dict[int, ItemResult] = field(default_factory=dict)      # 행 번호 → 분류
    items: list[dict] = field(default_factory=list)                # 문서 값 후보
    items_blocked: list[str] = field(default_factory=list)         # 품목을 내보내지 않은 사유 (3-2)
    note: str = ""


@dataclass
class L2Result:
    file: str
    sheets: list[SheetResult]
    calls: list[dict] = field(default_factory=list)   # 호출 기록 (작업 키, 모델, 성공 여부)


def _run(task: dict, call: Caller, primary: str, verifier: str | None, log: list) -> dict[str, dict]:
    """모델별로 호출하고 G1 + 작업별 검사를 거친 항목 결과를 돌려준다. {모델: {항목키: {"value","hold"}}}"""
    kind = task["payload"]["kind"]
    out = {}
    for model in [m for m in (primary, verifier) if m]:
        parsed = call(task, model)
        g1 = gates.g1_schema(kind, parsed)
        log.append({"target_key": task["target_key"], "model": model, "ok": g1 is None})
        if g1:
            out[model] = None
        else:
            out[model] = gates.CHECKERS[kind](task, parsed)
    return out


def _merge(per_model: dict[str, dict | None], key, primary: str, verifier: str | None) -> ItemResult:
    def get(m):
        r = per_model.get(m)
        return None if r is None else r.get(key)
    a = get(primary)
    cands = {m: (get(m) or {}).get("value") for m in per_model}
    if a is None or a["hold"]:
        return ItemResult(None, "HELD", (a or {}).get("hold") or "AI_NO_RESPONSE", cands)
    if verifier:
        b = get(verifier)
        if b is None or b["hold"]:
            return ItemResult(None, "HELD", "AI_NO_RESPONSE", cands)
        if a["value"] != b["value"]:
            return ItemResult(None, "HELD", "AI_DISAGREE", cands)
    return ItemResult(a["value"], "PENDING", None, cands)


def run_l2(path: str | Path, call: Caller, primary: str, verifier: str | None = None) -> L2Result:
    wb: Workbook = read_workbook(path)
    log: list = []
    res = L2Result(wb.path.name, [], log)

    st = sheets_task(wb)
    per = _run(st, call, primary, verifier, log)
    for sheet in wb.sheets:
        sr = SheetResult(sheet.name, _merge(per, sheet.name, primary, verifier))
        res.sheets.append(sr)
        if sr.kind.status == "PENDING":
            hits = gates.rule_qty_sheet(sheet.name, sr.kind.value)
            if hits:   # 수량 시트 안전장치: 모델 답은 후보 칸(candidates)에 그대로 남는다
                v = sr.kind.value
                sr.kind = ItemResult(None, "HELD", "AI_OUT_OF_DOMAIN", sr.kind.candidates, [h[0] for h in hits])
                _add_note(sr, "수량 시트 규칙 보류: " + "; ".join(f"{n} {why}" for n, why in hits)
                          + f" (모델 답 {v['sheet_kind']}/{v['is_qty_sheet']}는 모델별 후보에 보존)")
        if sr.kind.status != "PENDING" or sr.kind.value["is_qty_sheet"] != "Y":
            continue
        header = header_for(sheet)
        if header is None:
            _add_note(sr, header_diagnosis(sheet))
            continue
        sr.header_label = header.label
        ct = columns_task(wb, sheet, header)
        sr.header_text = ct["payload"]["meta"]["header_text"]
        perc = _run(ct, call, primary, verifier, log)
        for c in ct["payload"]["meta"]["cols"]:
            sr.columns[c] = _merge(perc, c, primary, verifier)
        for c in ct["payload"]["meta"]["auto_cols"]:   # 머리글 없는 열: 모델에 보내지 않고 코드가 '기타'
            sr.columns[c] = ItemResult("기타", "PENDING", None, {AUTO: "기타"})
        roles = {c: r.value for c, r in sr.columns.items() if r.status == "PENDING"}
        for rt in rows_tasks(wb, sheet, header, roles):
            perr = _run(rt, call, primary, verifier, log)
            for r in rt["payload"]["meta"]["rows"]:
                sr.rows[r] = _merge(perr, r, primary, verifier)
        missing = _missing_item_cols(sr)
        if missing:   # 수량 없는 품목이 나가지 않게: 품명·단위·수량 열 중 하나라도 확정 후보(PENDING)가 아니면 품목을 내보내지 않는다
            sr.items_blocked = missing
            _add_note(sr, "품목 내보내지 않음: " + "; ".join(missing) + " (행 분류 결과는 남김)")
            continue
        sr.items = extract_items(sheet, roles, {r: x.value for r, x in sr.rows.items() if x.status == "PENDING"})
    return res


def _add_note(sr: SheetResult, text: str) -> None:
    sr.note = f"{sr.note} / {text}" if sr.note else text


def _missing_item_cols(sr: SheetResult) -> list[str]:
    """품명·단위·수량 중 PENDING 열이 없는 역할마다 사유. 예: "수량 열 보류 D(AI_DISAGREE, 후보 gt=수량·m2=기타)"."""
    out = []
    for role in ITEM_COLS:
        if any(it.status == "PENDING" and it.value == role for it in sr.columns.values()):
            continue
        held = [(c, it) for c, it in sr.columns.items() if it.status == "HELD" and role in it.candidates.values()]
        if held:
            out.append(f"{role} 열 보류 " + ", ".join(
                f"{c}({it.hold_code}, 후보 " + "·".join(f"{m}={'검사 탈락' if v is None else v}"
                                                         for m, v in it.candidates.items()) + ")"
                for c, it in held))
        else:
            out.append(f"{role} 열 없음 (어느 모델도 {role} 역할로 지정하지 않음)")
    return out
