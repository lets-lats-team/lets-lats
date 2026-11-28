"""L2 결과를 정답과 맞대 채점하고, 정답 엑셀과 같은 칸으로 내보낸다.

판정 (항목 = 시트·열·행 하나, 정답이 있는 것만)
- 맞음      : PENDING이고 정답과 같음
- 틀린 PENDING: PENDING인데 정답과 다름  ← 가장 중요한 지표 (AI 설계 14.2)
- 보류      : HELD (hold_code별로 셈)
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .answers import SetAnswers


def _judge(item, answer) -> str:
    if item is None:
        return "대상 아님"
    if item.status != "PENDING":
        return f"보류:{item.hold_code}"
    return "맞음" if item.value == answer else "틀린 PENDING"


def score_set(sa: SetAnswers, res) -> dict:
    by_sheet = {s.name: s for s in res.sheets}
    out = {"sheets_kind": Counter(), "sheets_yn": Counter(), "columns": Counter(), "rows": Counter(),
           "header_rows": Counter(), "values": Counter(), "wrong": []}
    for name, a in sa.sheets.items():
        s = by_sheet.get(name)
        kind_item = s.kind if s else None
        if a["kind"]:
            v = None if kind_item is None else kind_item
            j = _judge(v, a["kind"]) if v is None or v.status != "PENDING" else ("맞음" if v.value["sheet_kind"] == a["kind"] else "틀린 PENDING")
            out["sheets_kind"][j] += 1
            if j == "틀린 PENDING":
                out["wrong"].append(f"시트 종류 {name}: 모델 {v.value['sheet_kind']} / 정답 {a['kind']}")
        if a["yn"]:
            v = kind_item
            j = _judge(v, a["yn"]) if v is None or v.status != "PENDING" else ("맞음" if v.value["is_qty_sheet"] == a["yn"] else "틀린 PENDING")
            out["sheets_yn"][j] += 1
            if j == "틀린 PENDING":
                out["wrong"].append(f"수량 시트 {name}: 모델 {v.value['is_qty_sheet']} / 정답 {a['yn']}")
    for (sheet, col), a in sa.columns.items():
        if not a["role"]:
            continue
        s = by_sheet.get(sheet)
        item = s.columns.get(col) if s else None
        j = _judge(item, a["role"])
        out["columns"][j] += 1
        if j == "틀린 PENDING":
            out["wrong"].append(f"열 {sheet}!{col}: 모델 {item.value} / 정답 {a['role']}")
        if s and s.header_label and a["header_rows"]:
            out["header_rows"]["같음" if s.header_label == a["header_rows"] else "다름"] += 1
    for (sheet, row), a in sa.rows.items():
        if not a["cls"]:
            continue
        s = by_sheet.get(sheet)
        item = s.rows.get(row) if s else None
        j = _judge(item, a["cls"])
        out["rows"][j] += 1
        if j == "틀린 PENDING":
            out["wrong"].append(f"행 {sheet}!{row} '{a['name'][:20]}': 모델 {item.value} / 정답 {a['cls']}")
    # 원본 셀 값 대조: 정답 엑셀의 품명·규격·단위·수량 원문과 코드가 가져온 값 (공백·쉼표 무시)
    def same(a, b):
        f = lambda x: (x or "").replace(" ", "").replace(",", "")
        return f(a) == f(b)
    for s in res.sheets:
        for it in s.items:
            a = sa.rows.get((s.name, it["row"]))
            if not a:
                continue
            ok = all(same(it[k], a[ak]) for k, ak in (("name", "name"), ("spec", "spec"), ("unit", "unit"), ("qty_raw", "qty")))
            out["values"]["같음" if ok else "다름"] += 1
            if not ok:
                out["wrong"].append(f"셀 값 {s.name}!{it['row']}: 읽은 값 {it['name']}|{it['spec']}|{it['unit']}|{it['qty_raw']} "
                                    f"/ 정답 원문 {a['name']}|{a['spec']}|{a['unit']}|{a['qty']}")
    return out


def rate(c: Counter) -> str:
    n = sum(c.values())
    if not n:
        return "-"
    ok = c["맞음"]
    held = sum(v for k, v in c.items() if k.startswith("보류"))
    out = f"{ok}/{n} 맞음 · 틀린 PENDING {c['틀린 PENDING']} · 보류 {held}"
    if c["대상 아님"]:
        out += f" · 대상 아님 {c['대상 아님']}"  # 파이프라인이 다루지 않은 항목 (조용히 빠지지 않게 표시)
    return out


def export(set_id: str, res, out_dir: Path) -> None:
    """정답 엑셀(L2_시트구분·L2_열대응·L2_행분류)과 같은 칸 + 상태·보류 코드·모델별 후보."""
    out_dir.mkdir(parents=True, exist_ok=True)

    def w(name, header, rows):
        with open(out_dir / f"{set_id}_{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
            cw = csv.writer(f)
            cw.writerow(header)
            cw.writerows(rows)

    w("L2_시트구분", ["세트", "파일", "시트", "수량 시트 여부", "시트 종류", "상태", "hold_code", "모델별 후보", "메모", "규칙 보류"],
      [[set_id, res.file, s.name, (s.kind.value or {}).get("is_qty_sheet", ""), (s.kind.value or {}).get("sheet_kind", ""),
        s.kind.status, s.kind.hold_code or "", s.kind.candidates, s.note, "·".join(s.kind.rules)] for s in res.sheets])
    w("L2_열대응", ["세트", "파일", "시트", "머리글 행", "열", "머리글 원문", "역할", "상태", "hold_code", "모델별 후보"],
      [[set_id, res.file, s.name, s.header_label, c, s.header_text.get(c, ""), it.value or "", it.status,
        it.hold_code or "", it.candidates] for s in res.sheets for c, it in s.columns.items()])
    w("L2_행분류", ["세트", "파일", "시트", "행 번호", "분류", "상태", "hold_code", "모델별 후보"],
      [[set_id, res.file, s.name, r, it.value or "", it.status, it.hold_code or "", it.candidates]
       for s in res.sheets for r, it in sorted(s.rows.items())])
    w("L2_품목값", ["세트", "파일", "시트", "행 번호", "품명", "규격", "단위", "수량 원문", "수량", "원본 셀"],
      [[set_id, res.file, i["sheet"], i["row"], i["name"], i["spec"], i["unit"], i["qty_raw"], i["qty"],
        i["source"]["cells"]] for s in res.sheets for i in s.items])
