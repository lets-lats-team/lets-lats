"""내역서 머리글 찾기와 열 머리글 글자 만들기 (코드가 하는 일, 모델 아님).

- 머리글 행: '품명'(또는 명칭·공종·품목·품목명 등 NAME_KEYS)과 '단위'가 같은 행에 있는 첫 행. 공백은 무시한다 ("품       명").
  '품목'·'품목명'은 2026-11-25 추가 (이 머리글을 쓰는 .xls 내역서를 못 읽던 것).
- 못 찾으면 header_diagnosis()가 메모용 사유를 만든다 (어느 행에 무엇만 있었는지).
  단위 열 없이 수량 칸에 "14대"처럼 적는 간이 양식은 지원하지 않는다 (2026-11-25 결정 나: 같은 공고에 표준 양식
  세부내역서가 따로 있어 지원하면 물량이 중복된다). 진단 메모에 그 가능성을 표시만 한다.
- 두 줄 머리글: 바로 아래 행에 '단가'·'금액'이 있으면 두 줄로 본다.
- 열 머리글 글자: 윗줄(병합이면 병합 범위의 값) + " / " + 아랫줄. 예: "재 료 비 / 단가".
  L2_열대응 정답의 '머리글 원문'과 같은 규칙이다. G2(근거)는 이 글자와 모델의 header_quote를 대조한다.

머리글 행 추정은 모델에 보낼 묶음을 만드는 데만 쓴다. 시트 종류·수량 시트 여부는 모델(L2)이 판단한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .reader_xlsx import Sheet, col_letter

WS = re.compile(r"\s+")
NAME_KEYS = {"품명", "명칭", "공종", "품명및규격", "공종명", "품목", "품목명"}
UNIT_KEYS = {"단위"}
QTY_KEYS = {"수량"}   # 진단 메모용 (머리글 판정에는 쓰지 않음)
DIAG_SHOW = 3         # 진단 메모에 보일 행 수
SUB_KEYS = {"단가", "금액"}
SCAN_ROWS = 40


def squash(s: str) -> str:
    return WS.sub("", s or "")


@dataclass
class Header:
    rows: tuple[int, ...]                    # (5,) 또는 (5, 6)
    col_text: dict[int, str] = field(default_factory=dict)  # 열 → 머리글 글자

    @property
    def first(self) -> int:
        return self.rows[0]

    @property
    def last(self) -> int:
        return self.rows[-1]

    @property
    def label(self) -> str:
        """정답 엑셀의 '머리글 행' 칸 형식: '5' 또는 '5~6'."""
        return str(self.first) if len(self.rows) == 1 else f"{self.first}~{self.last}"


def find_header_row(sheet: Sheet) -> int | None:
    for r in range(1, min(sheet.max_row, SCAN_ROWS) + 1):
        cells = {squash(t) for t in sheet.row_texts(r).values()}
        if cells & NAME_KEYS and cells & UNIT_KEYS:
            return r
    return None


def header_diagnosis(sheet: Sheet) -> str:
    """머리글을 못 찾은 이유를 구체적으로 (전에는 한 줄뿐이라 원인을 알 수 없었다). 예:
    '머리글 행을 찾지 못함: 1~40행에 품명 계열(…)과 '단위'가 같은 행에 없음. 품명 계열만: 6행(B6=품목명) · 단위만: 없음 · …'"""
    last = min(sheet.max_row, SCAN_ROWS)
    name_rows, unit_rows, compact_rows = [], [], []
    for r in range(1, last + 1):
        texts = sheet.row_texts(r)
        hit_name = [(c, t) for c, t in texts.items() if squash(t) in NAME_KEYS]
        hit_unit = [(c, t) for c, t in texts.items() if squash(t) in UNIT_KEYS]
        hit_qty = [(c, t) for c, t in texts.items() if squash(t) in QTY_KEYS]
        if hit_name:
            name_rows.append((r, hit_name))
        elif hit_unit:
            unit_rows.append((r, hit_unit))
        if hit_qty and not hit_unit:
            compact_rows.append((r, hit_name + hit_qty))

    def show(rows):
        if not rows:
            return "없음"
        parts = [f"{r}행(" + ", ".join(f"{col_letter(c)}{r}={t.strip()}" for c, t in hits) + ")"
                 for r, hits in rows[:DIAG_SHOW]]
        return " · ".join(parts) + (f" 외 {len(rows) - DIAG_SHOW}행" if len(rows) > DIAG_SHOW else "")

    keys = "·".join(sorted(NAME_KEYS))
    msg = (f"머리글 행을 찾지 못함: 1~{last}행에 품명 계열({keys})과 '단위'가 같은 행에 없음. "
           f"품명 계열만 있는 행: {show(name_rows)} / 단위만 있는 행: {show(unit_rows)}")
    if compact_rows:
        msg += (f" / 수량은 있고 단위 열이 없는 행: {show(compact_rows)} — 수량 칸에 단위가 붙는 간이 양식일 수 있음"
                " (지원하지 않음, 2026-11-25 결정: 같은 공고의 표준 양식 내역서를 쓴다)")
    return msg


def _top_text(sheet: Sheet, r: int, c: int) -> str:
    ar, ac = sheet.merged_anchor(r, c)
    return sheet.text(ar, ac) if ar == r else (sheet.text(r, c) or sheet.text(ar, ac))


def detect_header(sheet: Sheet) -> Header | None:
    r = find_header_row(sheet)
    if r is None:
        return None
    nxt = {squash(t) for t in sheet.row_texts(r + 1).values()} if r + 1 <= sheet.max_row else set()
    two = bool(nxt & SUB_KEYS)
    rows = (r, r + 1) if two else (r,)
    h = Header(rows)
    for c in range(1, sheet.max_col + 1):
        top = _top_text(sheet, r, c)
        sub = sheet.text(r + 1, c) if two else ""
        if top and sub:
            h.col_text[c] = f"{top} / {sub}"
        else:
            h.col_text[c] = top or sub
    return h
