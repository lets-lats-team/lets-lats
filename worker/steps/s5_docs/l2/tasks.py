"""L2 작업(모델에 보낼 묶음) 만들기. AI 설계 10장: 머리글 + 50행 묶음, 셀 주소 함께 전송.

작업 3종
- BOQ_SHEETS : 파일 하나의 시트 목록 + 시트별 앞부분 (시트 종류·수량 시트 여부)
- BOQ_COLUMNS: 수량 시트 하나의 머리글 + 앞부분 행 (열 역할)
- BOQ_ROWS   : 수량 시트의 머리글 아래 행 50개씩 (행 분류)

작업은 멀티에이전트 계약의 AITask 모양 dict로 만든다:
  {"role": "L2", "target_key", "payload": {"kind", "prompt", "schema_name", "meta"}, "affects_output": True}
숨김 열: 열 역할 작업에는 "(숨김)" 표시를 붙여 함께 보낸다 (정답셋이 숨김 열에도 역할을 단다).
행 묶음에는 보이는 열만 보낸다 (숨김 열은 계산용 숫자가 많아 행 판단을 흐린다).
숨김 열 예시 값: 앞부분 행에는 숨김 열 값이 없으므로, 열 작업 머리글 줄에 숨김 열의 서로 다른 값 3개를 붙인다 (L2.v4).
머리글이 없는 열: 열 역할 작업에 보내지 않고 코드가 '기타'로 정한다 (meta["auto_cols"]).
  머리글 인용(G2)으로 근거를 대조할 수 없어 모델이 추측만 하게 되기 때문이다. 정답셋도 이런 열에는 역할을 달지 않는다.
"""
from __future__ import annotations

from ..boq_header import Header, detect_header
from ..reader_xlsx import Sheet, Workbook, col_letter
from . import prompt as P

ROW_BUNDLE = 50
PREVIEW_ROWS = 12
SAMPLE_ROWS = 8
HIDDEN_EXAMPLES = 3
CELL_MAX = 40
MAX_COLS = 60


def _all_cols(sheet: Sheet) -> list[int]:
    return list(range(1, min(sheet.max_col, MAX_COLS) + 1))


def _visible_cols(sheet: Sheet) -> list[int]:
    return [c for c in _all_cols(sheet) if c not in sheet.hidden_cols]


def row_line(sheet: Sheet, r: int, cols: list[int]) -> str:
    parts = [f"{col_letter(c)}:{sheet.text(r, c)[:CELL_MAX]}" for c in cols if sheet.text(r, c)]
    return f"{r} | " + "  ".join(parts)


def _task(kind: str, target_key: str, prompt: str, meta: dict) -> dict:
    return {"role": "L2", "target_key": target_key,
            "payload": {"kind": kind, "prompt": prompt, "schema_name": kind, "prompt_version": P.PROMPT_VERSION,
                        "system": P.SYSTEM, "meta": meta},
            "affects_output": True}


def sheets_task(wb: Workbook) -> dict:
    blocks = []
    for s in wb.sheets:
        cols = _visible_cols(s)
        lines, shown = [], 0
        for r in range(1, s.max_row + 1):
            if shown >= PREVIEW_ROWS:
                break
            if s.is_empty_row(r):
                continue
            lines.append(row_line(s, r, cols))
            shown += 1
        blocks.append(f"### 시트: {s.name} (행 {s.max_row}, 열 {s.max_col})\n" + ("\n".join(lines) or "(빈 시트)"))
    return _task("BOQ_SHEETS", f"{wb.path.name}#sheets",
                 P.SHEETS_PROMPT.format(sheets="\n\n".join(blocks)),
                 {"file": wb.path.name, "sheets": [s.name for s in wb.sheets]})


def _examples(sheet: Sheet, header: Header, c: int) -> str:
    """숨김 열의 서로 다른 값 앞 몇 개 (L2.v4). 값이 없으면 '값 없음'."""
    seen: list[str] = []
    for r in range(header.last + 1, sheet.max_row + 1):
        v = sheet.text(r, c)[:CELL_MAX]
        if v and v not in seen:
            seen.append(v)
            if len(seen) >= HIDDEN_EXAMPLES:
                break
    return (", 예: " + " | ".join(seen)) if seen else ", 값 없음"


def columns_task(wb: Workbook, sheet: Sheet, header: Header) -> dict:
    cols = [c for c in _all_cols(sheet) if header.col_text.get(c, "").strip()]
    auto = [c for c in _all_cols(sheet) if not header.col_text.get(c, "").strip()]
    vis = _visible_cols(sheet)
    hdr = "\n".join(f"{col_letter(c)}: {header.col_text.get(c, '')}"
                    + (f"  (숨김{_examples(sheet, header, c)})" if c in sheet.hidden_cols else "")
                    for c in cols)
    rows, shown = [], 0
    for r in range(header.last + 1, sheet.max_row + 1):
        if shown >= SAMPLE_ROWS:
            break
        if sheet.is_empty_row(r):
            continue
        rows.append(row_line(sheet, r, vis))
        shown += 1
    return _task("BOQ_COLUMNS", f"{wb.path.name}#{sheet.name}#columns",
                 P.COLUMNS_PROMPT.format(sheet=sheet.name, header=hdr, rows="\n".join(rows)),
                 {"file": wb.path.name, "sheet": sheet.name, "header_rows": list(header.rows),
                  "cols": [col_letter(c) for c in cols],
                  "auto_cols": [col_letter(c) for c in auto],
                  "header_text": {col_letter(c): header.col_text.get(c, "") for c in cols + auto}})


def rows_tasks(wb: Workbook, sheet: Sheet, header: Header, col_roles: dict[str, str]) -> list[dict]:
    cols = _visible_cols(sheet)
    data_rows = [r for r in range(header.last + 1, sheet.max_row + 1) if not sheet.is_empty_row(r)]
    roles_txt = ", ".join(f"{k}={v}" for k, v in col_roles.items() if v not in ("기타",)) or "(열 역할 미정)"
    tasks = []
    for i in range(0, len(data_rows), ROW_BUNDLE):
        chunk = data_rows[i:i + ROW_BUNDLE]
        body = "\n".join(row_line(sheet, r, cols) for r in chunk)
        tasks.append(_task("BOQ_ROWS", f"{wb.path.name}#{sheet.name}#rows{chunk[0]}-{chunk[-1]}",
                           P.ROWS_PROMPT.format(sheet=sheet.name, col_roles=roles_txt, rows=body),
                           {"file": wb.path.name, "sheet": sheet.name, "rows": chunk}))
    return tasks


def header_for(sheet: Sheet) -> Header | None:
    return detect_header(sheet)
