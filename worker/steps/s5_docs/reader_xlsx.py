"""내역서 엑셀 읽기 (S5-R, L2 입력 준비).

- .xlsx는 openpyxl, 옛 형식 .xls는 xlrd로 읽어 같은 모양(Sheet)으로 돌려준다.
- 셀 값은 저장된 계산값(data_only)으로 읽는다. 수식 자체는 다루지 않는다.
- 숫자는 원래 값(raw)과 사람이 보는 글자(text)를 함께 둔다.
  엑셀 저장값의 소수점 찌꺼기(34.760000000000005)는 text에서만 정리하고 raw는 그대로 둔다.
- 병합 셀은 왼쪽 위 칸에만 값이 있다. 병합 범위는 따로 기록한다 (머리글 해석에 씀).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass
class Cell:
    raw: Any          # 원래 값 (int/float/str/date/None)
    text: str         # 표시용 글자 (공백 정리 안 함, 앞뒤 공백만 제거)


@dataclass
class Sheet:
    name: str
    max_row: int
    max_col: int
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)   # (행, 열) 1부터
    merged: list[tuple[int, int, int, int]] = field(default_factory=list)  # (r1, c1, r2, c2)
    hidden_cols: set[int] = field(default_factory=set)

    def text(self, r: int, c: int) -> str:
        cell = self.cells.get((r, c))
        return cell.text if cell else ""

    def raw(self, r: int, c: int) -> Any:
        cell = self.cells.get((r, c))
        return cell.raw if cell else None

    def row_texts(self, r: int) -> dict[int, str]:
        return {c: self.cells[(r, c)].text for c in range(1, self.max_col + 1)
                if (r, c) in self.cells and self.cells[(r, c)].text}

    def is_empty_row(self, r: int) -> bool:
        return not self.row_texts(r)

    def merged_anchor(self, r: int, c: int) -> tuple[int, int]:
        """병합 범위 안의 칸이면 그 범위의 왼쪽 위 칸을 돌려준다."""
        for r1, c1, r2, c2 in self.merged:
            if r1 <= r <= r2 and c1 <= c <= c2:
                return r1, c1
        return r, c


@dataclass
class Workbook:
    path: Path
    sheets: list[Sheet]

    def sheet(self, name: str) -> Sheet:
        for s in self.sheets:
            if s.name == name:
                return s
        raise KeyError(name)


def col_letter(c: int) -> str:
    s = ""
    while c:
        c, rem = divmod(c - 1, 26)
        s = chr(65 + rem) + s
    return s


def col_index(letter: str) -> int:
    n = 0
    for ch in letter.strip().upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def number_text(v: float | int) -> str:
    """엑셀 숫자를 사람이 보는 글자로. 부동소수 찌꺼기를 없앤다 (유효숫자 12자리)."""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if v != v:  # NaN
        return ""
    if float(v).is_integer():
        return str(int(v))
    d = Decimal(repr(v))
    q = Decimal(f"{float(v):.12g}")
    s = format(q if abs(q - d) < Decimal("1e-9") else d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _to_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return number_text(v)
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    return str(v).strip()


def _read_xlsx(path: Path) -> list[Sheet]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)  # read_only이면 병합·숨김 정보를 못 얻음
    out = []
    for ws in wb.worksheets:
        sh = Sheet(ws.title, ws.max_row or 0, ws.max_column or 0)
        for row in ws.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                sh.cells[(c.row, c.column)] = Cell(c.value, _to_text(c.value))
        for rng in ws.merged_cells.ranges:
            sh.merged.append((rng.min_row, rng.min_col, rng.max_row, rng.max_col))
        for key, dim in ws.column_dimensions.items():
            if dim.hidden:
                lo = dim.min or col_index(key)
                hi = dim.max or lo
                sh.hidden_cols.update(range(lo, hi + 1))
        _trim(sh)
        out.append(sh)
    wb.close()
    return out


def _read_xls(path: Path) -> list[Sheet]:
    import xlrd
    wb = xlrd.open_workbook(str(path), formatting_info=True)
    out = []
    for ws in wb.sheets():
        sh = Sheet(ws.name, ws.nrows, ws.ncols)
        for r in range(ws.nrows):
            for c in range(ws.ncols):
                cell = ws.cell(r, c)
                if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    continue
                v = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        v = xlrd.xldate.xldate_as_datetime(v, wb.datemode)
                    except Exception:  # noqa: BLE001 - 날짜 변환 실패는 숫자로 둔다
                        pass
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    v = bool(v)
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    v = None
                if v is None or v == "":
                    continue
                sh.cells[(r + 1, c + 1)] = Cell(v, _to_text(v))
        for r1, r2, c1, c2 in ws.merged_cells:  # xlrd: 끝은 미포함
            sh.merged.append((r1 + 1, c1 + 1, r2, c2))
        for c, info in ws.colinfo_map.items():
            if info.hidden:
                sh.hidden_cols.add(c + 1)
        _trim(sh)
        out.append(sh)
    return out


def _trim(sh: Sheet) -> None:
    """빈 칸만 있는 끝쪽 행·열을 잘라 실제 범위로 맞춘다."""
    nonempty = [k for k, v in sh.cells.items() if v.text]
    sh.max_row = max((r for r, _ in nonempty), default=0)
    sh.max_col = max((c for _, c in nonempty), default=0)


def read_workbook(path: str | Path) -> Workbook:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".xlsx":
        sheets = _read_xlsx(p)
    elif ext == ".xls":
        sheets = _read_xls(p)
    else:
        raise ValueError(f"지원하지 않는 내역서 형식: {ext} (xlsx·xls만)")
    return Workbook(p, sheets)
