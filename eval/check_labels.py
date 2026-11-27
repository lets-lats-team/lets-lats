"""L2·L3 정답 파일 검사 (data/text_v0.1/labels).

- 코드 값이 허용 목록에 있는지
- BOQ_DETAIL 시트의 열·행이 다 채워졌는지
- L3: 필수 칸, operator, quote가 시방서 원문에 그대로 있는지 (공백·줄바꿈 무시)

  python check_labels.py [--set R26BK01755909]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "data" / "text_v0.1"

SHEET_ROLES = {"COST_SUMMARY", "AGGREGATE", "BOQ_DETAIL", "UNIT_PRICE", "OTHER"}
COL_ROLES = {"ITEM_NAME", "SPEC", "UNIT", "QTY", "OTHER"}
ROW_ROLES = {"SECTION_TITLE", "ITEM", "SUBTOTAL", "OTHER"}
OPERATORS = {"=", ">=", "<=", "IN"}
WS = re.compile(r"\s+")


def load(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def squash(s: str) -> str:
    return WS.sub("", s or "")


def check_set(set_id: str) -> tuple[list[str], dict]:
    errs: list[str] = []
    lab = ROOT / "labels" / set_id
    sheets = load(lab / "l2_sheets.csv")
    cols = load(lab / "l2_columns.csv")
    rows = load(lab / "l2_rows.csv")
    rules = load(lab / "l3_rules.csv")

    detail = set()
    for s in sheets:
        role = (s.get("sheet_role") or "").strip()
        if role and role not in SHEET_ROLES:
            errs.append(f"l2_sheets: '{s['sheet']}' sheet_role 오타 '{role}'")
        if role == "BOQ_DETAIL":
            detail.add((s["workbook"], s["sheet"]))
    sheets_done = sum(1 for s in sheets if (s.get("sheet_role") or "").strip())

    col_need = [c for c in cols if (c["workbook"], c["sheet"]) in detail]
    col_done = 0
    for c in col_need:
        role = (c.get("col_role") or "").strip()
        if not role:
            continue
        col_done += 1
        if role not in COL_ROLES:
            errs.append(f"l2_columns: {c['sheet']}!{c['col']} col_role 오타 '{role}'")
    for ws in detail:
        roles = [(c.get("col_role") or "").strip() for c in cols if (c["workbook"], c["sheet"]) == ws]
        for need in ("ITEM_NAME", "UNIT", "QTY"):
            if roles and all(roles) and need not in roles:
                errs.append(f"l2_columns: '{ws[1]}'에 {need} 열이 없음 (정말 없는지 확인)")

    row_need = [r for r in rows if (r["workbook"], r["sheet"]) in detail]
    row_done = 0
    for r in row_need:
        role = (r.get("row_role") or "").strip()
        if not role:
            continue
        row_done += 1
        if role not in ROW_ROLES:
            errs.append(f"l2_rows: {r['sheet']}!{r['row']} row_role 오타 '{role}'")

    spec_text = {}
    for t in (ROOT / "sets" / set_id / "spec_text").glob("*.txt"):
        spec_text[t.name[:-4]] = squash(t.read_text(encoding="utf-8"))
    rule_ok = 0
    for i, r in enumerate(rules, start=2):
        f = (r.get("spec_file") or "").strip()
        if f not in spec_text:
            errs.append(f"l3_rules {i}행: spec_file '{f}'이 세트에 없음")
            continue
        if not (r.get("quote") or "").strip():
            if "조건 없음" not in (r.get("note") or ""):
                errs.append(f"l3_rules {i}행: quote가 비었음")
            continue
        for k in ("item", "attribute", "operator", "value"):
            if not (r.get(k) or "").strip():
                errs.append(f"l3_rules {i}행: {k}가 비었음")
        if (r.get("operator") or "").strip() not in OPERATORS:
            errs.append(f"l3_rules {i}행: operator '{r.get('operator')}'는 = >= <= IN 중 하나여야 함")
        if squash(r["quote"]) not in spec_text[f]:
            errs.append(f"l3_rules {i}행: quote가 시방서 원문에 그대로 없음 → '{r['quote'][:40]}'")
        else:
            rule_ok += 1

    stat = {
        "sheets": f"{sheets_done}/{len(sheets)}",
        "detail_sheets": len(detail),
        "columns": f"{col_done}/{len(col_need)}",
        "rows": f"{row_done}/{len(row_need)}",
        "l3_rules_ok": rule_ok,
        "l3_rows": len(rules),
    }
    return errs, stat


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default=None)
    args = ap.parse_args()
    ids = [args.set] if args.set else sorted(p.name for p in (ROOT / "labels").iterdir() if p.is_dir())
    total_err = 0
    for sid in ids:
        errs, st = check_set(sid)
        total_err += len(errs)
        print(f"[{sid}] 시트 {st['sheets']} · 내역 시트 {st['detail_sheets']} · 열 {st['columns']} · 행 {st['rows']} · "
              f"L3 조건 {st['l3_rules_ok']}/{st['l3_rows']}")
        for e in errs:
            print("   -", e)
    print("오류 없음" if total_err == 0 else f"오류 {total_err}건")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
