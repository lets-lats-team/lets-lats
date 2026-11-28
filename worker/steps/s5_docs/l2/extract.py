"""품목 행의 값을 원본 셀에서 가져온다 (AI 설계 6.2: 숫자는 모델 출력이 아니라 원본 셀에서).

결과 한 건 = D06 document_value 후보:
  {"sheet", "row", "name", "spec", "unit", "qty_raw", "qty", "source": {"sheet", "cells": {역할: "C12"}}}
- qty: 원본 셀 값을 숫자로 (쉼표 제거). 숫자로 못 읽으면 None, qty_raw에 원문.
- 소수점 찌꺼기는 12자리 유효숫자로 정리한다 (34.760000000000005 → 34.76).
- 이 단계는 열·행 분류가 PENDING인 것만 쓴다. 확정은 담당자(A05)가 한다.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ..reader_xlsx import Sheet, col_index, number_text

FIELDS = {"품명": "name", "규격": "spec", "단위": "unit", "수량": "qty_raw"}
NUM = re.compile(r"^[+-]?\d[\d,]*(\.\d+)?$")


def to_number(raw) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(number_text(raw))
    s = str(raw).strip().replace(" ", "")
    if not NUM.match(s):
        return None
    try:
        return float(Decimal(s.replace(",", "")))
    except InvalidOperation:
        return None


def extract_items(sheet: Sheet, col_roles: dict[str, str], row_classes: dict[int, str]) -> list[dict]:
    cols = {}
    for letter, role in col_roles.items():
        if role in FIELDS and role not in cols:
            cols[role] = letter
    if "품명" not in cols:
        return []
    items = []
    for r, cls in sorted(row_classes.items()):
        if cls != "품목":
            continue
        rec = {"sheet": sheet.name, "row": r, "name": "", "spec": "", "unit": "", "qty_raw": "", "qty": None,
               "source": {"sheet": sheet.name, "cells": {}}}
        for role, letter in cols.items():
            c = col_index(letter)
            rec[FIELDS[role]] = sheet.text(r, c)
            rec["source"]["cells"][role] = f"{letter}{r}"
        if "수량" in cols:
            rec["qty"] = to_number(sheet.raw(r, col_index(cols["수량"])))
        items.append(rec)
    return items
