"""L3 모듈 3~6단계 (prepare, 검사, postprocess, pair_key) 단위 시험. 모델·네트워크 없음."""
import re
import os
import sys
from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest

APP = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(APP))

from worker.roles import conformance as C  # noqa: E402
from worker.roles.contract import AITask, DocumentRef, Evidence, Part, RoleInputError, RoleLimits  # noqa: E402
from worker.roles.l3_spec import checks  # noqa: E402
from worker.roles.l3_spec.module import MODULE  # noqa: E402
from worker.roles.testing import FakeContext, run_task  # noqa: E402

DOC = uuid4()
COLLECT = Path(os.environ.get("LETS_DATA_ROOT") or APP.parent) / "03_수집_3년"   # 원본이 없으면 그 시험만 건너뜀

SRC = {
    "□2 3. 아.": "아. 냉매배관 파이프는 부분적으로 하중을 받지 않도록 1.5～2m 간격으로\n지지(지탱)해 주어야 한다.",
    "□2 5. 나.": "나. 배수관(드레인관)은 1/50～1/100의 기울기를 주어 응축수 배출을 용이하게 설치한다.",
    "□2 7. 라. (3)": "(3) 통신케이블은 전원용 케이블과 충분히 이격하여 설치한다.(최소 50 ㎜ 이격)",
    "1.2.8 2) ②": "② 보온두께 및 재질은 다음 표에 따른다.\n| 결로방지용 급  수  관 | 아티론보온재 | 25T | 40T |  |",
    "2.2": "2.2 기존 냉매 배관 세관 후 재사용※ 철거 전 현장 철거 요구사항 사전 협의",
}


def task(kind="HWP"):
    loc = {"clause_no": "□2 3. 아.", "chunk": 0} | ({"page": 52} if kind == "PDF" else {})
    return AITask(role="L3", target_key=f"spec:{DOC}:0", parts=[Part(kind="text", text="…")],
                  source=Evidence(kind=kind, document_id=DOC, location=loc), affects_output=True,
                  private={"kind": kind, "document_id": str(DOC), "chunk": 0, "clauses": SRC,
                           "pages": {k: [52] for k in SRC}, "owned": list(SRC), "image_pages": []})


def rule(no="□2 3. 아.", item="냉매배관 파이프", attr="지지 간격", op=">=", value="1.5", unit="m",
         quote="1.5～2m 간격으로 지지(지탱)해 주어야 한다"):
    return {"clause_no": no, "item": item, "attribute": attr, "operator": op, "value": value, "unit": unit, "quote": quote}


def one(**kw):
    out = MODULE.postprocess(task(), {"task": "SPEC_RULES", "rules": [rule(**kw)]})
    assert len(out) == 1
    return out[0]


# ---- 검사 (checks) ----

def test_g2_norm_and_numbers():
    assert checks.g2_norm("1.5～2m\n간격으로") == checks.g2_norm("1.5 ~ 2 m 간격으로") == "1.5~2m간격으로"
    assert checks.g2_norm("50 ㎜") == "50mm" and checks.g2_norm("| 25T | 40T |") == "25T40T"
    assert checks.numbers("최소 1,500 ㎜, 1/50～1/100") == ["1500", "1", "50", "1", "100"]
    assert checks.is_numeric_value("1.5 ~ 2") and checks.is_numeric_value("1/50~1/100")
    assert not checks.is_numeric_value("동관") and not checks.is_numeric_value("R410A")
    assert checks.normalize_value("1.5 ～ 2") == "1.5~2" and checks.normalize_value(" 난연  보온재 ") == "난연 보온재"


def test_check_unit():
    assert checks.check_unit("25", "㎜") is None and checks.check_unit("10", "㎏/㎠") is None
    assert checks.check_unit("3", "선") is None and checks.check_unit("25", "T") is None
    assert checks.check_unit("1/50~1/100", "") is None                     # 기울기 비율은 단위 없어도 됨
    assert checks.check_unit("25", "") == "숫자 값인데 단위 없음"
    assert "단위 목록에 없음" in checks.check_unit("25", "평")
    assert checks.check_unit("동관", "") is None                           # 글자 값은 단위 검사 안 함


# ---- postprocess ----

def test_valid_rule_passes_with_normalized_value():
    c = one()
    assert c.hold_code is None and c.value == {"item": "냉매배관파이프", "attribute": "지지간격", "operator": ">=",
                                               "value": "1.5", "unit": "m"}
    assert one(op="<=", value="2").hold_code is None                              # 범위의 다른 끝은 별도 규칙
    assert c.evidence[0].kind == "HWP" and c.evidence[0].location == {"clause_no": "□2 3. 아.", "chunk": 0}
    assert c.evidence[0].quote == "1.5～2m 간격으로 지지(지탱)해 주어야 한다" and c.raw["item"] == "냉매배관 파이프"


def test_quote_differences_that_pass():
    assert one(quote="1.5~2m 간격으로 지지 (지탱)해").hold_code is None          # 물결·공백·줄바꿈 차이
    assert one(no="□2 7. 라. (3)", item="통신케이블", attr="이격 거리", op=">=", value="50", unit="mm",
               quote="(최소 50 mm 이격)").hold_code is None                         # ㎜ vs mm
    assert one(no="1.2.8 2) ②", item="급수관 보온재", attr="두께", op=">=", value="25", unit="T",
               quote="결로방지용 급수관 아티론보온재 25T").hold_code is None        # 표 칸 구분 없이
    assert one(no=" □2  3.  아. (이어짐)").hold_code is None                       # clause_no 공백·이어짐 표시


def test_quote_failures_are_no_evidence():
    c = one(quote="2.5m 간격으로 지지(지탱)해 주어야 한다")
    assert c.hold_code == "AI_NO_EVIDENCE" and c.note == "인용문이 조항 원문에 없음"
    c = one(value="1.2")                                                         # 인용문은 맞는데 값 숫자가 없음
    assert c.hold_code == "AI_NO_EVIDENCE" and "1.2" in c.note
    assert one(quote="").note == "인용문 없음"
    c = one(no="□9 1.")
    assert c.hold_code == "AI_NO_EVIDENCE" and "이 묶음에 없음" in c.note
    c = one(quote="냉매배관 파이프는", value="동관", op="=", unit="")             # 글자 값이 인용문에 없음
    assert c.hold_code == "AI_NO_EVIDENCE" and "글자 값" in c.note
    assert one(quote="냉매배관 파이프는", value="냉매배관 파이프", op="=", unit="").hold_code is None


def test_text_value_and_glued_value():                                       # 2026-11-26
    assert one(quote="냉매배관 파이프는", value="냉매배관  파이프", op="=", unit="").hold_code is None   # 공백 차이 무시
    for kw in (dict(value="2m"), dict(no="□2 7. 라. (3)", value="50 ㎜", quote="(최소 50 ㎜ 이격)")):
        c = one(unit="", **kw)                                                    # 인용문에 있는 글자라 G2는 통과
        assert c.hold_code == "AI_OUT_OF_DOMAIN" and "붙여" in c.note, (kw, c.note)
    assert one(value="1.5m", unit="").hold_code == "AI_NO_EVIDENCE"              # 인용문에 없는 글자면 G2가 먼저
    assert checks.check_glued("Φ6.35") and checks.check_glued("30A") and checks.check_glued("25T")
    assert checks.check_glued("R410A") is None and checks.check_glued("KSC9306") is None
    assert checks.check_glued("-10") is None and checks.check_glued("동관") is None


def test_unit_failure_is_out_of_domain_after_g2():
    c = one(unit="평")
    assert c.hold_code == "AI_OUT_OF_DOMAIN" and "단위" in c.note
    assert checks.check_unit("60", "Hz") is None


def test_range_value_is_out_of_domain():                                     # 연산자 6개: 범위는 두 규칙으로
    c = one(value="1.5~2")
    assert c.hold_code == "AI_OUT_OF_DOMAIN" and "두 규칙" in c.note
    assert checks.check_range("1/50 ～ 1/100") and checks.check_range("1/50") is None
    assert checks.check_range("동관~황동관") is None                                # 숫자 범위가 아님
    for v in ("1.5-2", "1.5 내지 2", "1/50-1/100"):                                # 범위 표기
        assert checks.check_range(v), v
    assert checks.check_range("-10") is None                                      # 음수
    c = one(value="1.5 내지 2", quote="1.5 내지 2 m 간격")
    assert c.hold_code in ("AI_NO_EVIDENCE", "AI_OUT_OF_DOMAIN")
    assert checks.OPERATORS == ["=", "!=", ">=", "<=", ">", "<"]
    assert one(unit="평", quote="없는 문장").hold_code == "AI_NO_EVIDENCE"        # G2가 먼저


def test_pdf_evidence_has_page():
    c = MODULE.postprocess(task("PDF"), {"task": "SPEC_RULES", "rules": [rule()]})[0]
    assert c.evidence[0].kind == "PDF" and c.evidence[0].location["page"] == 52


# ---- 공사 방식 (G3, 2026-11-25 결정: 설계서 형식 — value에 R01 4종 코드) ----

def method(**kw):
    base = dict(no="2.2", item="냉매 배관", attr="공사 방식", op="=", value="REUSE_PIPE", unit="",
                quote="기존 냉매 배관 세관 후 재사용")
    return one(**(base | kw))


def test_method_row_passes_and_normalizes():
    c = method()
    assert c.hold_code is None and c.value == {"item": "냉매배관", "attribute": "공사방식", "operator": "=",
                                               "value": "REUSE_PIPE", "unit": ""}
    assert method(value=" reuse pipe ").value["value"] == "REUSE_PIPE" and method(value="reuse-pipe").hold_code is None
    assert method(attr="공사방식").hold_code is None
    assert MODULE.pair_key(method()) == "2.2|냉매배관|공사방식|="
    for code in checks.PIPING_MODES:
        assert checks.check_method("공사 방식", "=", code, "") is None


def test_method_row_format_failures_are_out_of_domain():
    for kw, part in ((dict(value="기존 배관 재사용"), "4종 코드"), (dict(op="!="), "operator"),
                     (dict(unit="m"), "단위"), (dict(item="드레인 배관"), "item")):
        c = method(**kw)
        assert c.hold_code == "AI_OUT_OF_DOMAIN" and part in c.note, (kw, c.note)
    c = method(attr="재질")                                                       # 코드 글자는 인용문에 없으니 G2가 먼저
    assert c.hold_code == "AI_NO_EVIDENCE"
    assert checks.check_method("재질", "=", "REUSE_PIPE", "") and method(item="냉매배관").hold_code is None
    c = method(quote="철거 전 현장 철거 요구사항 사전 협의")                         # 철거 문장에 REUSE_PIPE (회귀 R-04)
    assert c.hold_code == "AI_NO_EVIDENCE" and "REUSE_PIPE" in c.note
    assert method(value="REPLACE_AFTER_DEMO", quote="철거 전 현장 철거 요구사항 사전 협의").hold_code is None
    c = one(no="□2 3. 아.", item="냉매 배관", attr="공사 방식", op="=", value="REUSE_PIPE", unit="",
            quote="1.5～2m 간격으로 지지(지탱)해 주어야 한다")                     # 배관 지지 문장
    assert c.hold_code == "AI_NO_EVIDENCE" and "근거 말" in c.note
    assert checks.check_quote("기존 냉매배관을 사용을하고", "기존 냉매배관을 사용을하고", "REUSE_PIPE", "공사 방식") is None  # R-05
    assert method(quote="기존 배관 철거 후 신설").hold_code == "AI_NO_EVIDENCE"      # G2가 먼저
    assert checks.check_method("재질", "=", "동관", "") is None                       # 공사 방식이 아닌 행은 건드리지 않음


def test_prompt_and_schema_v3():
    assert MODULE.prompt_version == "l3-v3"
    assert all(code in MODULE.system_prompt for code in checks.PIPING_MODES)
    assert checks.METHOD_ITEM in MODULE.system_prompt and checks.METHOD_ATTRIBUTE in MODULE.system_prompt
    ops = MODULE.schema["properties"]["rules"]["items"]["properties"]["operator"]["enum"]
    assert ops == checks.OPERATORS


def test_prompt_example_passes_checks():
    """프롬프트 예 출력이 G2·G3를 모두 통과해야 한다 (보류될 답을 가르치지 않게)."""
    import json as _json
    blocks = re.findall(r"```(?:json)?\n(.*?)```", MODULE.system_prompt, re.S)
    source, out = blocks[0], _json.loads(blocks[1])
    assert len(out["rules"]) >= 10
    for r in out["rules"]:
        assert r["operator"] in checks.OPERATORS
        assert checks.check_quote(r["quote"], source, r["value"], r["attribute"]) is None, r
        for f in (lambda: checks.check_method(r["attribute"], r["operator"], r["value"], r["unit"], r["item"]),
                  lambda: checks.check_empty(r["value"]), lambda: checks.check_range(r["value"]),
                  lambda: checks.check_glued(r["value"]), lambda: checks.check_unit(r["value"], r["unit"])):
            assert f() is None, r


# ---- clause_no 맞추기 (2026-11-26 결정) ----

def tree_task():
    clauses = {"3.": "3. 배관\n아. 1.5～2m 간격으로 지지한다.\n자. 방수처리를 한다.",
               "3. 아.": "아. 1.5～2m 간격으로 지지한다.", "3. 자.": "자. 방수처리를 한다.",
               "□2 ①": "① 첫째 항목", "□2 ①#2": "① 재입찰을 실시할 수 있다 1회"}
    tree = {"3.": {"own": "3. 배관", "children": ["3. 아.", "3. 자."], "pages": [52]},
            "3. 아.": {"own": clauses["3. 아."], "children": [], "pages": [52]},
            "3. 자.": {"own": clauses["3. 자."], "children": [], "pages": [53]},
            "□2 ①": {"own": clauses["□2 ①"], "children": [], "pages": []},
            "□2 ①#2": {"own": clauses["□2 ①#2"], "children": [], "pages": []}}
    t = task()
    t.private.update({"clauses": clauses, "tree": tree})
    return t


def test_clause_descends_to_lowest_and_fixes_dup_suffix():
    t = tree_task()
    c = MODULE.postprocess(t, reply(rule(no="3.", value="1.5", quote="1.5～2m 간격으로 지지한다")))[0]
    assert c.hold_code is None and c.evidence[0].location["clause_no"] == "3. 아." and "조정" in c.note
    c = MODULE.postprocess(t, reply(rule(no="3.", value="", op="=", unit="", item="배관", attr="재질",
                                         quote="3. 배관")))[0]
    assert c.evidence[0].location["clause_no"] == "3."                          # 자기 본문에 있으면 그대로
    c = MODULE.postprocess(t, reply(rule(no="□2 ①", item="재입찰", attr="수량", op="<=", value="1", unit="회",
                                         quote="재입찰을 실시할 수 있다 1회")))[0]
    assert c.hold_code is None and c.evidence[0].location["clause_no"] == "□2 ①#2"
    c = MODULE.postprocess(t, reply(rule(no="3. 자.", value="1.5", quote="1.5～2m 간격으로 지지한다")))[0]
    assert c.hold_code == "AI_NO_EVIDENCE"                                       # 형제 조항으로는 옮기지 않음


def test_clause_descends_into_child_outside_chunk():                       # 회귀 R-07
    t = tree_task()
    t.private["clauses"] = {"3.": t.private["clauses"]["3."]}                  # 하위는 다른 묶음
    c = MODULE.postprocess(t, reply(rule(no="3.", value="1.5", quote="1.5～2m 간격으로 지지한다")))[0]
    assert c.hold_code is None and c.evidence[0].location["clause_no"] == "3. 아."


# ---- 회귀 R-01·R-02·R-03·R-06·R-10 ----

def test_regress_value_checks():
    assert not checks._in_quote("KSC930", checks.g2_norm("KSC 9306에 의한"))          # R-01 부분 문자열
    assert checks._in_quote("KSC9306", checks.g2_norm("KSC 9306에 의한"))
    assert checks._in_quote("동관", checks.g2_norm("인탈산 재질의 동관을"))             # 한글은 경계 검사 안 함
    for v in ("30A이상", "500㎜이상", "-10℃", "30inch", "3대"):                       # R-02
        assert checks.check_glued(v), v
    for v in ("2인 1조", "1식", "R410A", "300*150*1500", "KSC9306"):
        assert checks.check_glued(v) is None, v
    for v in ("1.5—2", "1.5−2", "1.5~2m"):                                         # R-03
        assert checks.check_range(v), v
    assert checks.check_range("KS D 5301-2") is None
    assert checks.check_quote("3.8 MPa", "3.8 MPa의 내압", "3.80") is None            # R-06
    c = one(value="", op="=", unit="", quote="냉매배관 파이프는")                       # R-10
    assert c.hold_code == "AI_OUT_OF_DOMAIN" and "비어" in c.note


def test_blocks_split_overlong_line_without_loss():                          # 회귀 R-11
    from worker.roles.l3_spec.clauses import split_clauses
    from worker.roles.l3_spec.reader import Line, SpecText
    cdoc = split_clauses(SpecText(kind="HWP", lines=[Line("1. Long"), Line("x" * 300)]))
    ctx = FakeContext(paths={})
    blocks = MODULE._blocks(cdoc, ctx, 80)
    assert len(blocks) > 1 and all(ctx.count_tokens(t) <= 80 for _, t, _ in blocks)
    assert "".join(t for _, t, _ in blocks).count("x") == 300                    # 잘려 나간 글자 없음
    assert [first for _, _, first in blocks].count(True) == 1


# ---- pair_key ----

def test_pair_key_ignores_spacing_only():
    a = one()
    b = MODULE.postprocess(task(), {"task": "SPEC_RULES", "rules": [rule(no="□2  3. 아. (이어짐)", item="냉매배관파이프",
                                                                         attr=" 지지간격")]})[0]
    assert MODULE.pair_key(a) == MODULE.pair_key(b) == "□2 3. 아.|냉매배관파이프|지지간격|>="
    assert MODULE.pair_key(one(op="<=", value="2")) != MODULE.pair_key(a)      # 범위의 두 끝은 다른 키


# ---- 시험용 엔진으로 끝까지 ----

def reply(*rules):
    return {"task": "SPEC_RULES", "rules": list(rules)}


def test_engine_cross_check():
    t = task()
    same = run_task(MODULE, t, lambda _t, m: reply(rule(item="냉매배관 파이프" if m == "h" else "냉매배관파이프")), "h", "l")
    assert len(same) == 1 and same[0].status == "PENDING" and same[0].agreed is True
    diff = run_task(MODULE, t, lambda _t, m: reply(rule(value="1.5" if m == "h" else "2", unit="m")), "h", "l")
    assert diff[0].hold_code == "AI_DISAGREE"
    fake = run_task(MODULE, t, lambda _t, m: reply(rule(quote="지어낸 문장" if m == "l" else rule()["quote"])), "h", "l")
    assert fake[0].hold_code == "AI_NO_EVIDENCE"                                 # 검사 코드가 불일치보다 앞
    bad_schema = run_task(MODULE, t, lambda _t, m: {"task": "SPEC_RULES", "rules": [rule(op="≥")]}, "h", "l")
    assert bad_schema[0].hold_code == "AI_NO_RESPONSE"                           # enum 밖 → G1 탈락
    old_op = run_task(MODULE, t, lambda _t, m: {"task": "SPEC_RULES", "rules": [rule(op="범위", value="1.5~2")]}, "h", "l")
    assert old_op[0].hold_code == "AI_NO_RESPONSE"                               # 11-26부터 6개 밖 연산자는 G1 탈락
    assert run_task(MODULE, t, lambda _t, m: reply(), "h", "l") == []           # 조건 없는 묶음 (allow_empty)


# ---- prepare ----

def _pdf(tmp_path, pages):
    d = pymupdf.open()
    for lines in pages:
        p = d.new_page()
        for i, s in enumerate(lines):
            p.insert_text((72, 72 + 14 * i), s)
    f = tmp_path / "spec.pdf"
    d.save(f)
    return f


def _ctx(path, role="SPEC", **lim):
    doc = DocumentRef(id=DOC, role=role, file_name=path.name, extension=path.suffix.lstrip("."))
    return FakeContext(paths={DOC: path}, role_limits=RoleLimits(**lim)), doc


def test_prepare_chunks_and_private(tmp_path):
    pages = [["cover"], ["1. Pipe"] + [f"1) support {i} m line" for i in range(1, 2)] + ["2) drain 1/50"],
             ["2. Wire", "1) cable 50 mm", "- 3 -"]]
    ctx, doc = _ctx(_pdf(tmp_path, pages), chunk_tokens=70)
    tasks = MODULE.prepare(ctx, doc)
    assert [t.target_key for t in tasks] == [f"spec:{DOC}:{i}" for i in range(len(tasks))] and len(tasks) >= 2
    first = tasks[0]
    assert first.parts[0].text.startswith("아래 조항에서 조건을 뽑는다. (묶음 1/")
    assert "[[1.]]" in first.parts[0].text and first.source.kind == "PDF" and first.source.location["page"] == 2
    assert "2) drain 1/50" in first.private["clauses"]["1."]                     # 상위 조항 원문에 하위 포함
    all_owned = [no for t in tasks for no in t.private["owned"]]
    assert sorted(all_owned) == sorted({"1.", "1. 1)", "1. 2)", "2.", "2. 1)"})  # 조항마다 한 묶음이 맡음
    assert C.check_tasks(tasks, ctx, MODULE) == [] and C.check_prepare_deterministic(MODULE, ctx, doc) == []


def test_prepare_splits_long_clause(tmp_path):
    ctx, doc = _ctx(_pdf(tmp_path, [["1. Long"] + [f"line {i:02d} xxxxxxxxxx" for i in range(30)]]), chunk_tokens=120)
    tasks = MODULE.prepare(ctx, doc)
    assert len(tasks) > 1 and "[[1.]] (이어짐)" in tasks[1].parts[0].text
    assert tasks[0].private["owned"] == ["1."] and tasks[1].private["owned"] == []
    assert all(ctx.count_tokens(t.parts[0].text) <= 120 for t in tasks)          # 머리말 포함 한도 안


def test_prepare_errors(tmp_path):
    ctx, doc = _ctx(_pdf(tmp_path, [["no clause numbers here", "just text"]]))
    with pytest.raises(RoleInputError) as e:
        MODULE.prepare(ctx, doc)
    assert e.value.code == "EMPTY"


def test_module_conformance(tmp_path):
    ctx, doc = _ctx(_pdf(tmp_path, [["1. Pipe", "1) support 1.5 m"]]))
    assert C.check_module(MODULE, APP / "worker" / "roles" / "l3_spec", ctx, [doc]) == []


def test_notice_document_same_path(tmp_path):
    """계약 1.1: L3는 공고문(NOTICE)도 받는다. 읽기·조항 나누기는 시방서와 같다."""
    assert MODULE.document_roles == ("SPEC", "NOTICE") and MODULE.contract_version == "1.1"
    f = _pdf(tmp_path, [["1. Pipe", "1) support 1.5 m"]])
    ctx, spec = _ctx(f)
    _, notice = _ctx(f, role="NOTICE")
    a, b = MODULE.prepare(ctx, spec), MODULE.prepare(ctx, notice)
    assert [t.model_dump() for t in a] == [t.model_dump() for t in b]
    assert C.check_module(MODULE, APP / "worker" / "roles" / "l3_spec", ctx, [notice]) == []
    drawing = DocumentRef(id=DOC, role="DRAWING", file_name="a.dwg", extension="dwg")
    assert C.check_module(MODULE, APP / "worker" / "roles" / "l3_spec", ctx, [drawing]) == []   # 대상 밖 문서는 건너뜀


def test_real_s24_prepare_if_present():
    found = list(COLLECT.glob("2024/20240120529_*/03_시방서_과업/20240120529-01_*공사시방서.hwp"))
    if not found:
        pytest.skip("공고 원본 없음")
    ctx, doc = _ctx(found[0], chunk_tokens=20_000)
    tasks = MODULE.prepare(ctx, doc)
    assert len(tasks) == 1 and "□2 3. 아." in tasks[0].private["clauses"]
    c = MODULE.postprocess(tasks[0], reply(rule()))[0]
    assert c.hold_code is None                                                    # 가이드 예시가 실제 원문으로 통과
    assert C.check_module(MODULE, APP / "worker" / "roles" / "l3_spec", ctx, [doc]) == []
