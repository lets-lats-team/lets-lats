"""L2 단위 시험 (네트워크·실제 정답 파일 없이). 작은 가짜 내역서를 만들어 쓴다."""
import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from worker.steps.s5_docs.boq_header import detect_header, header_diagnosis  # noqa: E402
from worker.steps.s5_docs.l2 import gates  # noqa: E402
from worker.steps.s5_docs.l2.extract import extract_items, to_number  # noqa: E402
from worker.steps.s5_docs.l2.pipeline import run_l2  # noqa: E402
from worker.steps.s5_docs.l2.prompt import SCHEMAS  # noqa: E402
from worker.steps.s5_docs.l2.tasks import columns_task, rows_tasks, sheets_task  # noqa: E402
from worker.steps.s5_docs.reader_xlsx import number_text, read_workbook  # noqa: E402


@pytest.fixture
def boq(tmp_path):
    """원가계산서 + 내역서(두 줄 머리글, 병합, 숨김 열, 소수점 찌꺼기) + 일위대가."""
    wb = openpyxl.Workbook()
    ws0 = wb.active
    ws0.title = "원가계산서"
    ws0["A1"] = "공 사 원 가 계 산 서"
    ws0["A3"], ws0["B3"] = "재료비", 0
    ws = wb.create_sheet("내역서")
    ws["A1"] = "공사명 : 시험"
    ws.append(["품       명", "규  격", "단위", "수 량", "재  료  비", None, "비 고", "코드"])  # 2행
    ws.append([None, None, None, None, "단   가", "금    액", None, None])                    # 3행
    ws.merge_cells("E2:F2")
    ws.append(["1. 배관", None, None, None])                                                   # 4
    ws.append(["냉매배관자재(경질직관)", "D41.28*1.52T", "M", 34.760000000000005, 0, 0, None, "X1"])  # 5
    ws.append(["보온재", "25T", "M", "1,200", 0, 0, None, "X2"])                              # 6
    ws.append(["계", None, None, None, None, 0])                                               # 7
    ws["I5"] = 1                                                                                # 머리글 없는 계산용 열
    ws.column_dimensions["H"].hidden = True
    ws2 = wb.create_sheet("일위대가")
    ws2.append(["품 명", "규 격", "단위", "수량"])
    ws2.append(["동관", "15.88", "M", 1])
    p = tmp_path / "boq.xlsx"
    wb.save(p)
    return p


def test_number_text_cleans_float_noise():
    assert number_text(34.760000000000005) == "34.76"
    assert number_text(1.0) == "1"
    assert number_text(0.1 + 0.2) == "0.3"
    assert number_text(12.5) == "12.5"


def test_reader_and_header(boq):
    wb = read_workbook(boq)
    sh = wb.sheet("내역서")
    assert 8 in sh.hidden_cols
    h = detect_header(sh)
    assert h.rows == (2, 3) and h.label == "2~3"
    assert h.col_text[5] == "재  료  비 / 단   가"   # 병합된 윗줄 + 아랫줄
    assert h.col_text[6] == "재  료  비 / 금    액"
    assert h.col_text[1] == "품       명"
    assert detect_header(wb.sheet("원가계산서")) is None


def test_tasks_shape(boq):
    wb = read_workbook(boq)
    st = sheets_task(wb)
    assert st["payload"]["meta"]["sheets"] == ["원가계산서", "내역서", "일위대가"]
    sh = wb.sheet("내역서")
    ct = columns_task(wb, sh, detect_header(sh))
    assert ct["payload"]["meta"]["cols"][-1] == "H"          # 숨김 열도 열 작업에는 들어감
    assert ct["payload"]["meta"]["auto_cols"] == ["I"]       # 머리글 없는 열은 보내지 않음
    assert "\nI:" not in ct["payload"]["prompt"]                # 머리글 목록에 I열 없음
    assert "(숨김)" in ct["payload"]["prompt"]
    rts = rows_tasks(wb, sh, detect_header(sh), {})
    assert rts[0]["payload"]["meta"]["rows"] == [4, 5, 6, 7]
    assert "X1" not in rts[0]["payload"]["prompt"]           # 행 묶음에는 숨김 열 값 없음


def test_schemas_are_strict():
    def walk(s):
        if s.get("type") == "object":
            assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
            for v in s["properties"].values():
                walk(v)
        if s.get("type") == "array":
            walk(s["items"])
    for s in SCHEMAS.values():
        walk(s)


def test_gates_columns(boq):
    wb = read_workbook(boq)
    sh = wb.sheet("내역서")
    ct = columns_task(wb, sh, detect_header(sh))
    parsed = {"task": "BOQ_COLUMNS", "columns": [
        {"col": "A", "role": "품명", "header_quote": "품 명"},          # 공백 차이는 통과
        {"col": "B", "role": "규격", "header_quote": "규격(지어냄)"},     # 원문에 없음 → 근거 없음
        {"col": "C", "role": "수량", "header_quote": "단위"},
        {"col": "D", "role": "수량", "header_quote": "수 량"},          # 수량 두 개 → 값 범위
        {"col": "E", "role": "단가", "header_quote": "재 료 비 / 단 가"},
        {"col": "E", "role": "금액", "header_quote": "재 료 비 / 단 가"},  # 같은 열 두 번 → 값 범위
    ]}
    r = gates.check_columns(ct, parsed)
    assert r["A"]["value"] == "품명"
    assert r["B"]["hold"] == "AI_NO_EVIDENCE"
    assert r["C"]["hold"] == r["D"]["hold"] == "AI_OUT_OF_DOMAIN"
    assert r["E"]["hold"] == "AI_OUT_OF_DOMAIN"
    assert r["F"]["hold"] == "AI_NO_RESPONSE"                    # 답하지 않은 열


def test_gates_g1():
    assert gates.g1_schema("BOQ_ROWS", None) == "AI_NO_RESPONSE"
    assert gates.g1_schema("BOQ_ROWS", {"task": "BOQ_ROWS", "rows": [{"row": 1, "class": "아무거나"}]}) == "AI_NO_RESPONSE"
    assert gates.g1_schema("BOQ_ROWS", {"task": "BOQ_ROWS", "rows": [{"row": 1, "class": "품목"}]}) is None


def test_extract_takes_numbers_from_cells_not_model(boq):
    wb = read_workbook(boq)
    sh = wb.sheet("내역서")
    items = extract_items(sh, {"A": "품명", "B": "규격", "C": "단위", "D": "수량"}, {5: "품목", 6: "품목", 7: "소계"})
    assert [i["row"] for i in items] == [5, 6]
    assert items[0]["qty"] == 34.76 and items[0]["qty_raw"] == "34.76"
    assert items[1]["qty"] == 1200.0 and items[1]["source"]["cells"]["수량"] == "D6"
    assert to_number("약 3") is None


def _answering_caller(sheet_answers, col_answers, row_answers, wrong_model=None):
    def call(task, model):
        k = task["payload"]["kind"]
        m = task["payload"]["meta"]
        flip = model == wrong_model
        if k == "BOQ_SHEETS":
            return {"task": k, "sheets": [{"sheet": n, "sheet_kind": sheet_answers[n][0], "is_qty_sheet": sheet_answers[n][1]}
                                          for n in m["sheets"]]}
        if k == "BOQ_COLUMNS":
            return {"task": k, "columns": [{"col": c, "role": col_answers.get(c, "기타"),
                                            "header_quote": m["header_text"][c]} for c in m["cols"]]}
        if k == "BOQ_ROWS":
            return {"task": k, "rows": [{"row": r, "class": ("기타" if flip and r == 5 else row_answers[r])}
                                        for r in m["rows"]]}
    return call


SHEETS = {"원가계산서": ("원가계산서", "N"), "내역서": ("내역서", "Y"), "일위대가": ("일위대가", "N")}
COLS = {"A": "품명", "B": "규격", "C": "단위", "D": "수량", "E": "단가", "F": "금액", "G": "비고", "H": "코드"}
ROWS = {4: "공종 제목", 5: "품목", 6: "품목", 7: "소계"}


def test_pipeline_single_model(boq):
    res = run_l2(boq, _answering_caller(SHEETS, COLS, ROWS), "m1")
    by = {s.name: s for s in res.sheets}
    assert by["일위대가"].kind.value == {"sheet_kind": "일위대가", "is_qty_sheet": "N"}
    assert not by["일위대가"].rows                                  # 수량 시트가 아니면 열·행 단계 없음
    d = by["내역서"]
    assert d.header_label == "2~3" and d.columns["D"].value == "수량"
    assert d.columns["I"].value == "기타" and d.columns["I"].candidates == {"코드 규칙": "기타"}
    assert {r: x.value for r, x in d.rows.items()} == ROWS
    assert [i["qty"] for i in d.items] == [34.76, 1200.0]


def test_pipeline_cross_check_disagree(boq):
    call = _answering_caller(SHEETS, COLS, ROWS, wrong_model="m2")
    res = run_l2(boq, call, "m1", "m2")
    d = {s.name: s for s in res.sheets}["내역서"]
    assert d.rows[5].status == "HELD" and d.rows[5].hold_code == "AI_DISAGREE"
    assert d.rows[5].candidates == {"m1": "품목", "m2": "기타"}
    assert d.rows[6].status == "PENDING"
    assert [i["row"] for i in d.items] == [6]                       # 보류된 행은 값으로 내보내지 않음


def test_rule_qty_sheet_holds_and_keeps_model_answer(boq):
    """결정 (가): 일위대가를 Y로 답해도 코드가 보류하고, 모델 답은 후보에 남는다."""
    sheets = {**SHEETS, "일위대가": ("일위대가", "Y")}
    res = run_l2(boq, _answering_caller(sheets, COLS, ROWS), "m1")
    u = {s.name: s for s in res.sheets}["일위대가"]
    assert u.kind.status == "HELD" and u.kind.hold_code == "AI_OUT_OF_DOMAIN"
    assert u.kind.rules == ["규칙①", "규칙②"]
    assert u.kind.candidates == {"m1": {"sheet_kind": "일위대가", "is_qty_sheet": "Y"}}
    assert "규칙① 시트 종류 '일위대가'" in u.note and "규칙② 시트 이름 '일위대가'" in u.note
    assert not u.rows and not u.items                                  # 열·행 단계로 가지 않음
    assert {s.name: s for s in res.sheets}["내역서"].items             # 내역서는 그대로


def test_rule_qty_sheet_each_rule():
    assert gates.rule_qty_sheet("단 가 대 비 표", {"sheet_kind": "내역서", "is_qty_sheet": "Y"})[0][0] == "규칙②"  # 공백 무시
    assert [n for n, _ in gates.rule_qty_sheet("Sheet1", {"sheet_kind": "표지", "is_qty_sheet": "Y"})] == ["규칙①"]
    assert gates.rule_qty_sheet("공종별집계표", {"sheet_kind": "집계표", "is_qty_sheet": "N"}) == []    # N이면 규칙 없음
    assert gates.rule_qty_sheet("내역서", {"sheet_kind": "내역서", "is_qty_sheet": "Y"}) == []


def test_items_blocked_when_qty_column_held(boq):
    """수량 열이 AI_DISAGREE면 품목을 내보내지 않는다. 행 분류는 남긴다."""
    base = _answering_caller(SHEETS, COLS, ROWS)

    def call(task, model):
        r = base(task, model)
        if model == "m2" and r["task"] == "BOQ_COLUMNS":
            for x in r["columns"]:
                if x["role"] == "수량":
                    x["role"] = "기타"
        return r
    d = {s.name: s for s in run_l2(boq, call, "m1", "m2").sheets}["내역서"]
    assert d.columns["D"].hold_code == "AI_DISAGREE"
    assert d.items == [] and {r: x.value for r, x in d.rows.items()} == ROWS
    assert d.items_blocked == ["수량 열 보류 D(AI_DISAGREE, 후보 m1=수량·m2=기타)"]
    assert "품목 내보내지 않음: 수량 열 보류 D" in d.note


def test_items_blocked_when_unit_column_missing(boq):
    cols = {**COLS, "C": "기타"}      # 어느 모델도 단위 열을 지정하지 않음
    d = {s.name: s for s in run_l2(boq, _answering_caller(SHEETS, cols, ROWS), "m1").sheets}["내역서"]
    assert d.items == [] and d.items_blocked == ["단위 열 없음 (어느 모델도 단위 역할로 지정하지 않음)"]


def _sheet(tmp_path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "내역서"
    for row in rows:
        ws.append(row)
    p = tmp_path / "x.xlsx"
    wb.save(p)
    return read_workbook(p).sheet("내역서")


def test_header_accepts_pummok(tmp_path):
    """'품목'·'품목명'도 품명 머리글로 본다."""
    sh = _sheet(tmp_path, [["공사명"], [None, "품 목", "규격", "단위", "수량"], [None, "전기히트펌프", "", "대", 1]])
    assert detect_header(sh).label == "2"
    sh = _sheet(tmp_path, [[None, "품목명", "단위", "수량"]])
    assert detect_header(sh).label == "1"


def test_header_diagnosis_is_specific(tmp_path):
    """결정 (나): 무엇이 어디에 있었는지, 간이 양식이면 지원하지 않음을 메모에."""
    sh = _sheet(tmp_path, [["견적서"], [None, "품명", "수량", "금액"], [None, "냉난방기", "14대", 0], ["단위: 원"]])
    assert detect_header(sh) is None
    msg = header_diagnosis(sh)
    assert "1~4행" in msg and "품명 계열만 있는 행: 2행(B2=품명)" in msg
    assert "단위만 있는 행: 없음" in msg
    assert "수량은 있고 단위 열이 없는 행: 2행(B2=품명, C2=수량)" in msg and "지원하지 않음" in msg
    sh = _sheet(tmp_path, [["항  목", "적  요", "수량", "금  액"], ["냉난방기", "철거 및 설치", "11대", 0]])  # 대덕대 양식
    msg = header_diagnosis(sh)
    assert "품명 계열만 있는 행: 없음" in msg and "수량은 있고 단위 열이 없는 행: 1행(C1=수량)" in msg
    sh = _sheet(tmp_path, [["표지"], ["공사명"]])
    assert "품명 계열만 있는 행: 없음" in header_diagnosis(sh) and "간이 양식" not in header_diagnosis(sh)


def test_pipeline_header_missing_note(tmp_path):
    p = tmp_path / "y.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "내역서"
    wb.active.append(["품목명", "수량"])
    wb.active.append(["실내기", "7대"])
    wb.save(p)
    res = run_l2(p, lambda t, m: {"task": "BOQ_SHEETS", "sheets": [{"sheet": "내역서", "sheet_kind": "내역서", "is_qty_sheet": "Y"}]}, "m1")
    assert res.sheets[0].note.startswith("머리글 행을 찾지 못함: 1~2행") and len(res.calls) == 1


def test_pipeline_verifier_missing(boq):
    base = _answering_caller(SHEETS, COLS, ROWS)
    res = run_l2(boq, lambda t, m: None if m == "m2" else base(t, m), "m1", "m2")
    assert all(s.kind.hold_code == "AI_NO_RESPONSE" for s in res.sheets)  # 한쪽만 응답 → 보류 (7장)
