"""L3 평가 실행기 시험. 정답 엑셀 대신 가짜 정답 줄을 쓰고, 시방서는 실제 원본(없으면 건너뜀)."""
import sys
from argparse import Namespace
from pathlib import Path
from uuid import uuid4

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from l3_eval import answers as A  # noqa: E402
from l3_eval.callers import gt_caller  # noqa: E402
from l3_eval.score import score_set  # noqa: E402
import run_l3_eval  # noqa: E402
from worker.roles.contract import DocumentRef, RoleLimits  # noqa: E402
from worker.roles.l3_spec.module import MODULE  # noqa: E402
from worker.roles.testing import FakeContext, run_document  # noqa: E402

HEAD = ("세트", "파일", "쪽 또는 조항 위치", "clause_no", "item", "attribute", "operator", "value", "unit", "출처",
        "quote", "확인자", "확인일", "메모")
L3 = "글자층(L3)"
S24_NOTICE = "20240120529-00_1705896443713_붙임1. 입찰공고(안).hwp"
ROWS = [HEAD,
        ("S24", "", "", "□2 3. 아.", "냉매배관 파이프", "지지 간격", ">=", "1.5", "m", L3,
         "1.5～2m 간격으로 지지(지탱)해 주어야 한다", "시험", "", ""),
        ("S24", "", "", "□2  3.아.", "냉매배관 파이프", "재질", "=", "파이프", "", L3,    # clause_no 띄어쓰기 다름
         "냉매배관 파이프는", "시험", "", ""),
        ("S24", "", "", "□2 5. 나.", "배수관", "기울기", "<=", "1/50", "", L3, "1/50～1/100의 기울기를 주어", "시험", "", ""),
        ("S24", "", "", "□2 7. 라. (3)", "통신케이블", "이격 거리", ">=", 50, "㎜", L3, "(최소 50 ㎜ 이격)", "시험", "", ""),
        ("S24", "", "", "□9 9.", "없는 조항", "두께", "=", "1", "mm", L3, "x", "시험", "", ""),      # 조항 목록에 없음
        ("S24", "", "", "", "빈 칸", "", "", "", "", L3, "", "시험", "", ""),                           # 필수 칸 빔
        ("S26", "", "53", "제2장 6. 8)", "실외기", "이격 거리", ">=", "500", "㎜", "이미지 표(V4)", "그림", "시험", "", ""),
        ("S26", "", "52", "제2장 5. 4)", "드레인 배관 주관", "관경", ">=", "30", "A", L3,
         "주관은 30A이상의 파이프를 사용한다", "시험", "", ""),
        ("S24", S24_NOTICE, "", "1. 다.", "공사", "시간", "<=", "45", "일", L3,              # 공고문 행 (파일 칸으로 나뉨)
         "계약체결일로부터 45일 이내", "시험", "", ""),
        ("S24", "없는 파일.hwp", "", "□2 3. 아.", "x", "두께", "=", "1", "mm", L3, "x", "시험", "", ""),   # 파일 이름 틀림
        ("S24", "", "", "□2 5. 나.", "배수관", "기울기", "범위", "1/50~1/100", "", L3, "1/50～1/100의 기울기", "시험", "", "")]  # 6개 밖


@pytest.fixture(scope="module")
def ans():
    a = A.load(rows=ROWS)
    if "S24" not in a or "S26" not in a:
        pytest.skip("공고 원본 없음")
    return a


def test_load_answers(ans):
    s24 = ans["S24"]
    assert len(s24.rules) == 5 and s24.incomplete == [7]
    assert s24.rules[3].value == "50" and ans["S26"].v4_rows == 1 and len(ans["S26"].rules) == 1
    assert s24.bad_file == [11] and s24.role == "SPEC" and s24.bad_operator == [12]
    n = ans["S24-공고"]
    assert n.role == "NOTICE" and n.spec.name == S24_NOTICE and [r.row for r in n.rules] == [10]
    assert {"S25-공고", "S26-공고"} <= set(ans) and ans["S26-공고"].spec.suffix == ".hwp"


def _doc(ans, sid):
    return DocumentRef(id=uuid4(), role=ans[sid].role, file_name=ans[sid].spec.name,
                       extension=ans[sid].spec.suffix.lstrip("."))


def test_gt_self_check(ans):
    for sid, n_ok in (("S24", 4), ("S26", 1), ("S24-공고", 1)):
        d = _doc(ans, sid)
        call = gt_caller(ans, {str(d.id): sid})
        tasks, results = run_document(MODULE, FakeContext(paths={d.id: ans[sid].spec},
                                                          role_limits=RoleLimits(chunk_tokens=20_000)), d, call, "gt")
        sc = score_set(ans[sid], tasks, results, "gt")
        assert sc["counter"]["맞음"] == n_ok and sc["counter"]["틀린 PENDING"] == 0
        if sid == "S24":
            assert sc["bad_clause_rows"] == [6] and sc["counter"]["놓침"] == 1    # 없는 조항 정답은 놓침


def test_wrong_value_quote_drop_and_extra(ans):
    sid = "S24"
    d = _doc(ans, sid)
    base = gt_caller(ans, {str(d.id): sid})

    def bad(task, model):
        r = base(task, model)
        for x in r["rules"]:
            if x["attribute"] == "지지 간격":
                x["value"] = "1.2" if model == "m1" else x["value"]                # 값 틀림 (인용문에는 1.2 없음 → G2)
            if x["attribute"] == "기울기":
                x["value"] = "1/200" if model == "m1" else x["value"]
                x["quote"] = "1/50～1/200의 기울기"                                  # 지어낸 인용문
        r["rules"] = [x for x in r["rules"] if x["attribute"] != "이격 거리"]         # 빠뜨림
        r["rules"].append({"clause_no": "□2 3. 자.", "item": "냉매 배관", "attribute": "기타", "operator": "=",
                           "value": "방수처리", "unit": "", "quote": "반드시 방수처리를 해야 한다"})   # 정답에 없는 조건
        return r
    tasks, results = run_document(MODULE, FakeContext(paths={d.id: ans[sid].spec}), d, bad, "m1")
    c = score_set(ans[sid], tasks, results, "m1")["counter"]
    assert c["보류:AI_NO_EVIDENCE"] == 2 and c["놓침"] == 2 and c["정답에 없는 PENDING"] == 1 and c["맞음"] == 1

    def wrong_but_quoted(task, model):        # 인용문엔 있는 숫자로 틀린 값 → 교차 확인만 잡을 수 있음
        r = base(task, model)
        for x in r["rules"]:
            if x["attribute"] == "지지 간격" and model == "m1":
                x["operator"], x["value"] = ">=", "2"
        return r
    tasks, results = run_document(MODULE, FakeContext(paths={d.id: ans[sid].spec}), d, wrong_but_quoted, "m1")
    assert score_set(ans[sid], tasks, results, "m1")["counter"]["틀린 PENDING"] == 1
    tasks, results = run_document(MODULE, FakeContext(paths={d.id: ans[sid].spec}), d, wrong_but_quoted, "m1", "gt")
    c = score_set(ans[sid], tasks, results, "m1")["counter"]
    assert c["틀린 PENDING"] == 0 and c["보류:AI_DISAGREE"] == 1                    # 교차 확인이 막음


def test_runner_end_to_end(ans, tmp_path):
    args = Namespace(primary="gt", verifier="fake-wrong", sets="S24,S25,S26", answers=Path("가짜.xlsx"),
                     chunk_tokens=20_000, out=tmp_path)
    run_dir = run_l3_eval.run(args, answers=ans)
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "| S24 | 5 |" in report and "조항 목록에 없는 정답 행 [6]" in report and "이미지 표(V4)' 정답 1줄" in report
    assert "| S24-공고 | 1 | 1 | 0 |" in report and "| S25-공고 | 0 |" in report and "아닌 정답 행 [11]" in report and "밖이라 채점에서 뺀 정답 행 [12]" in report
    assert (run_dir / "S24_L3_조건.csv").exists() and (run_dir / "S24-공고_L3_조건.csv").exists()


# ---- 2026-11-26 Codex 4-1·5-1: 같은 키 결과 중복, 같은 키 정답 중복 ----

def _res(key, status, value, unit="m", hold=None, tk="t0"):
    from types import SimpleNamespace as N
    cand = N(value={"value": value, "unit": unit}, evidence=[N(quote="q")], hold_code=hold, note="")
    return N(target_key=tk, pair_key=key, status=status, hold_code=hold, agreed=True, candidates={"m": cand})


def test_duplicate_results_counted_once():
    sa = A.load(rows=ROWS, require_source=False)["S24"]
    key = A.answer_key("□2 3. 아.", "냉매배관 파이프", "지지 간격", ">=")
    task = type("T", (), {"private": {"pages": {}, "clauses": {"□2 3. 아.": ""}}})()
    sc = score_set(sa, [task], [_res(key, "PENDING", "1.5", tk="t0"), _res(key, "PENDING", "1.5", tk="t1"),
                                _res(key, "PENDING", "1.5", tk="t2")], "m")
    assert sc["counter"]["맞음"] == 1 and sc["counter"]["중복 결과"] == 2
    sc = score_set(sa, [task], [_res(key, "PENDING", "1.5", tk="t0"), _res(key, "PENDING", "9", tk="t1")], "m")
    assert sc["counter"]["틀린 PENDING"] == 1 and sc["counter"]["맞음"] == 0     # 하나라도 틀리면 틀린 PENDING


def test_duplicate_answer_rows_not_overwritten():
    rows = ROWS + [("S24", "", "", "□2 3. 아.", "냉매배관 파이프", "지지 간격", ">=", "9", "m", L3,
                    "1.5～2m 간격으로 지지(지탱)해 주어야 한다", "시험", "", "")]
    sa = A.load(rows=rows, require_source=False)["S24"]
    key = A.answer_key("□2 3. 아.", "냉매배관 파이프", "지지 간격", ">=")
    task = type("T", (), {"private": {"pages": {}, "clauses": {"□2 3. 아.": ""}}})()
    sc = score_set(sa, [task], [_res(key, "PENDING", "1.5")], "m")
    assert sc["counter"]["맞음"] == 1 and sc["counter"]["틀린 PENDING"] == 0 and sc["dup_rows"] == [len(rows)]


def test_duplicate_representative_row_matches_judgment():                  # 회귀 R-08·R-09
    sa = A.load(rows=ROWS, require_source=False)["S24"]
    key = A.answer_key("□2 3. 아.", "냉매배관 파이프", "지지 간격", ">=")
    task = type("T", (), {"private": {"pages": {}, "clauses": {"□2 3. 아.": ""}}})()
    sc = score_set(sa, [task], [_res(key, "PENDING", "1.5", tk="t0"), _res(key, "PENDING", "9", tk="t1")], "m")
    by_tk = {r["target_key"]: r["판정"] for r in sc["rows"]}
    assert by_tk == {"t1": "틀린 PENDING", "t0": "중복 결과(맞음)"} and "9 m" in sc["wrong"][0]
    sc = score_set(sa, [task], [_res(key, "HELD", "1.5", hold="AI_DISAGREE", tk="t0"),
                                _res(key, "PENDING", "1.5", tk="t1")], "m")
    by_tk = {r["target_key"]: r["판정"] for r in sc["rows"]}
    assert by_tk == {"t1": "맞음", "t0": "중복 결과(보류:AI_DISAGREE)"}
    other = A.answer_key("□2 3. 아.", "x", "y", "=")                               # 정답 없는 키
    for order in (("HELD", "PENDING"), ("PENDING", "HELD")):
        res = [_res(other, st, "1", hold="AI_DISAGREE" if st == "HELD" else None, tk=f"t{k}") for k, st in enumerate(order)]
        assert score_set(sa, [task], res, "m")["counter"]["정답에 없는 PENDING"] == 1, order


def test_anthropic_caller_thinking_off_and_failed_raw():
    """Haiku 호출은 thinking을 끄고, max_tokens 끊김이면 원래 응답을 FAILED_RAW에 남긴다 (2026-11-26 트러블슈팅)."""
    from types import SimpleNamespace as NS
    from l3_eval import callers as C
    from worker.roles.contract import AITask, Evidence, Part

    seen = {}

    class Msgs:
        def create(self, **kw):
            seen.update(kw)
            return NS(stop_reason="max_tokens", usage=NS(input_tokens=10, output_tokens=4096),
                      content=[NS(type="thinking"), NS(type="text", text='{"task":"SPEC_RULES","rules":[{"clau')])

    task = AITask(role="L3", target_key="spec:x:0", parts=[Part(kind="text", text="본문")],
                  source=Evidence(kind="HWP", document_id=uuid4(), location={"clause_no": "1."}), affects_output=True, private={})
    n = len(C.FAILED_RAW)
    assert C.anthropic_caller(client=NS(messages=Msgs()))(task, "claude-haiku-5-5") is None
    assert seen["thinking"] == {"type": "disabled"} and seen["max_tokens"] == C.L3_MAX_TOKENS
    raw = C.FAILED_RAW[n]
    assert raw["error"] == "stop_reason=max_tokens" and raw["raw"].startswith("[블록 thinking,text]")
    del C.FAILED_RAW[n:], C.CALL_LOG[-1:]
