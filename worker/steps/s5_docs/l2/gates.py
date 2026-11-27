"""L2 응답 검사 (AI 설계 8장 G1~G3 중 L2에 해당하는 것). 판정은 코드가 한다.

- G1 형식: 스키마 통과
- G2 근거: 열 역할의 header_quote가 그 열의 머리글 글자와 같은가 (공백 무시),
          시트 이름·행 번호가 실제로 보낸 것인가
- G3 값 범위: 값 목록 (스키마 enum), 모든 대상에 정확히 한 번 답했는가, 품명·단위·수량 열이 하나씩인가

- 수량 시트 안전장치 (rule_qty_sheet): 단가 산정·요약 시트를 Y로 답하면 AI_OUT_OF_DOMAIN (2026-11-25 결정 가)

결과는 항목(시트·열·행)마다 ok 또는 hold_code(AI_NO_RESPONSE · AI_NO_EVIDENCE · AI_OUT_OF_DOMAIN)를 붙인다.
"""
from __future__ import annotations

from collections import Counter

import jsonschema

from ..boq_header import squash
from .prompt import SCHEMAS
from .vocab import NON_QTY_KINDS, NON_QTY_NAME_WORDS, SINGLE_COLS


def g1_schema(kind: str, parsed: dict | None) -> str | None:
    if parsed is None:
        return "AI_NO_RESPONSE"
    try:
        jsonschema.validate(parsed, SCHEMAS[kind])
    except jsonschema.ValidationError:
        return "AI_NO_RESPONSE"  # 설계 G1: 1회 재요청 후에도 실패면 AI_NO_RESPONSE (재요청은 gateway 몫)
    return None


def check_sheets(task: dict, parsed: dict) -> dict[str, dict]:
    """시트 이름 → {"value": {"sheet_kind", "is_qty_sheet"} | None, "hold": code | None}"""
    names = task["payload"]["meta"]["sheets"]
    out = {n: {"value": None, "hold": "AI_NO_RESPONSE"} for n in names}
    seen = Counter(x["sheet"] for x in parsed["sheets"])
    for x in parsed["sheets"]:
        n = x["sheet"]
        if n not in out:
            continue  # 보낸 적 없는 시트 이름: 무시 (해당 시트는 응답 없음으로 남음)
        if seen[n] > 1:
            out[n] = {"value": None, "hold": "AI_OUT_OF_DOMAIN"}
            continue
        out[n] = {"value": {"sheet_kind": x["sheet_kind"], "is_qty_sheet": x["is_qty_sheet"]}, "hold": None}
    return out


def check_columns(task: dict, parsed: dict) -> dict[str, dict]:
    """열 글자 → {"value": 역할 | None, "hold": code | None, "quote": str}"""
    meta = task["payload"]["meta"]
    out = {c: {"value": None, "hold": "AI_NO_RESPONSE", "quote": ""} for c in meta["cols"]}
    seen = Counter(x["col"].strip().upper() for x in parsed["columns"])
    for x in parsed["columns"]:
        c = x["col"].strip().upper()
        if c not in out:
            continue
        if seen[c] > 1:
            out[c] = {"value": None, "hold": "AI_OUT_OF_DOMAIN", "quote": x["header_quote"]}
            continue
        if squash(x["header_quote"]) != squash(meta["header_text"].get(c, "")):
            out[c] = {"value": None, "hold": "AI_NO_EVIDENCE", "quote": x["header_quote"]}
            continue
        out[c] = {"value": x["role"], "hold": None, "quote": x["header_quote"]}
    # 구조 검사: 품명·단위·수량이 둘 이상이면 해당 열들을 보류
    roles = Counter(v["value"] for v in out.values() if v["value"])
    for role in SINGLE_COLS:
        if roles[role] > 1:
            for c, v in out.items():
                if v["value"] == role:
                    out[c] = {**v, "value": None, "hold": "AI_OUT_OF_DOMAIN"}
    return out


def check_rows(task: dict, parsed: dict) -> dict[int, dict]:
    """행 번호 → {"value": 분류 | None, "hold": code | None}"""
    rows = task["payload"]["meta"]["rows"]
    out = {r: {"value": None, "hold": "AI_NO_RESPONSE"} for r in rows}
    seen = Counter(int(x["row"]) for x in parsed["rows"])
    for x in parsed["rows"]:
        r = int(x["row"])
        if r not in out:
            continue  # 보낸 적 없는 행 번호
        if seen[r] > 1:
            out[r] = {"value": None, "hold": "AI_OUT_OF_DOMAIN"}
            continue
        out[r] = {"value": x["class"], "hold": None}
    return out


def rule_qty_sheet(sheet_name: str, value: dict) -> list[tuple[str, str]]:
    """수량 시트 안전장치 (2026-11-25 결정 가). 모델이 Y라고 한 시트에 규칙을 대 본다.
    걸린 규칙마다 (규칙 이름, 구체적 사유)를 돌려준다. 빈 목록이면 통과.
    오보류를 나중에 보고 규칙을 좁힐 수 있게 사유를 구체적으로 남긴다 (근거 없이 풀지 않음)."""
    if value.get("is_qty_sheet") != "Y":
        return []
    out = []
    if value.get("sheet_kind") in NON_QTY_KINDS:
        out.append(("규칙①", f"시트 종류 '{value['sheet_kind']}'인데 수량 시트 Y"))
    words = [w for w in NON_QTY_NAME_WORDS if w in squash(sheet_name)]
    if words:
        out.append(("규칙②", f"시트 이름 '{sheet_name}'에 '{'·'.join(words)}' 있는데 수량 시트 Y"))
    return out


CHECKERS = {"BOQ_SHEETS": check_sheets, "BOQ_COLUMNS": check_columns, "BOQ_ROWS": check_rows}
