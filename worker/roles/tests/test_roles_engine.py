"""계약(contract)·시험용 엔진(testing)·적합성 검사(conformance) 단위 시험. 모델·네트워크 없음."""
import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from worker.roles import conformance as C  # noqa: E402
from worker.roles.contract import (AITask, Candidate, DocumentRef, Evidence, Part, RoleLimits, first_hold,  # noqa: E402
                                   normalize_text, normalize_unit)
from worker.roles.testing import FakeContext, run_task  # noqa: E402

DOC = uuid4()


class Dummy:
    """시험용 역할 모듈: 응답 items 하나가 후보 하나. quote가 비면 AI_NO_EVIDENCE, val이 'bad'면 AI_OUT_OF_DOMAIN."""
    role = "L3"
    contract_version = "1.1"
    prompt_version = "dummy-v1"
    system_prompt = "시험"
    document_roles = ("SPEC",)
    allow_empty = True
    schema = {"type": "object", "additionalProperties": False, "required": ["task", "items"],
              "properties": {"task": {"type": "string"},
                             "items": {"type": "array", "items": {
                                 "type": "object", "additionalProperties": False, "required": ["key", "val", "quote"],
                                 "properties": {"key": {"type": "string"}, "val": {"type": "string"},
                                                "quote": {"type": "string"}}}}}}

    def prepare(self, ctx, doc):
        src = Evidence(kind="HWP", document_id=doc.id, location={"clause_no": "1"})
        return [AITask(role="L3", target_key=f"spec:{doc.id}:0", parts=[Part(kind="text", text="본문")],
                       source=src, affects_output=True, private={"1": "본문"})]

    def postprocess(self, task, response):
        out = []
        for x in response["items"]:
            code = "AI_NO_EVIDENCE" if not x["quote"] else ("AI_OUT_OF_DOMAIN" if x["val"] == "bad" else None)
            out.append(Candidate(value={"key": x["key"], "val": x["val"]}, raw=x, hold_code=code,
                                 evidence=[Evidence(kind="HWP", document_id=DOC, location={"clause_no": "1"},
                                                    quote=x["quote"])]))
        return out

    def pair_key(self, c):
        return normalize_text(c.value["key"])


M = Dummy()
TASK = M.prepare(None, DocumentRef(id=DOC, role="SPEC", file_name="a.hwp", extension="hwp"))[0]


def reply(*items):
    return {"task": "x", "items": [{"key": k, "val": v, "quote": q} for k, v, q in items]}


def caller(by_model):
    return lambda task, model: by_model.get(model)


def one(results):
    assert len(results) == 1
    return results[0]


def test_normalize():
    assert normalize_text("  보온재의   두께\n25 ㎜ ") == "보온재의 두께 25 ㎜"
    assert normalize_text("ＡＢＣ　１２") == "ABC 12"
    assert normalize_text("Φ15.88") == normalize_text("ø15.88") == "Ø15.88"
    assert normalize_unit("㎜") == normalize_unit(" MM ") == "mm"
    assert normalize_unit("°C") == "℃" and normalize_unit("㎫") == "MPa" and normalize_unit("") == ""


def test_evidence_location_and_document_id():
    with pytest.raises(ValueError):
        Evidence(kind="PDF", document_id=DOC, location={"page": 3})          # clause_no 없음
    with pytest.raises(ValueError):
        Evidence(kind="HWP", document_id=None, location={"clause_no": "1"})  # MANUAL 아닌데 문서 없음
    Evidence(kind="MANUAL", document_id=None, location={"note": "직접 입력"})


def test_first_hold_priority():
    assert first_hold(["AI_DISAGREE", "AI_NO_EVIDENCE", None]) == "AI_NO_EVIDENCE"
    assert first_hold(["AI_CONFLICT", "AI_BUDGET"]) == "AI_BUDGET"
    assert first_hold([None]) is None


def test_agree_after_normalization():
    r = one(run_task(M, TASK, caller({"h": reply(("두께", "25 ㎜", "q")), "l": reply(("두께 ", "25  ㎜", "q"))}), "h", "l"))
    assert r.status == "PENDING" and r.agreed is True and set(r.candidates) == {"h", "l"}


def test_disagree_and_one_side_candidate():
    rs = run_task(M, TASK, caller({"h": reply(("두께", "25", "q"), ("냉매", "R410A", "q")),
                                   "l": reply(("두께", "30", "q"))}), "h", "l")
    by = {r.pair_key: r for r in rs}
    assert by["두께"].hold_code == "AI_DISAGREE" and by["두께"].agreed is False
    assert by["냉매"].hold_code == "AI_DISAGREE" and list(by["냉매"].candidates) == ["h"]   # 한쪽에만 있는 후보


def test_check_code_beats_disagree():
    """11.4 예: 한 후보는 G2, 다른 후보는 G3에 걸리면 앞선 AI_NO_EVIDENCE."""
    r = one(run_task(M, TASK, caller({"h": reply(("두께", "25", "")), "l": reply(("두께", "bad", "q"))}), "h", "l"))
    assert r.hold_code == "AI_NO_EVIDENCE"


def test_one_model_no_response_keeps_candidates():
    r = one(run_task(M, TASK, caller({"h": reply(("두께", "25", "q")), "l": None}), "h", "l"))
    assert r.hold_code == "AI_NO_RESPONSE" and r.candidates["h"].value["val"] == "25"


def test_schema_failure_is_no_response():
    rs = run_task(M, TASK, caller({"h": {"task": "x"}, "l": {"items": []}}), "h", "l")
    assert one(rs).hold_code == "AI_NO_RESPONSE" and one(rs).pair_key is None


def test_duplicate_pair_key_out_of_domain():
    r = one(run_task(M, TASK, caller({"h": reply(("두께", "25", "q"), ("두께", "30", "q"))}), "h"))
    assert r.hold_code == "AI_OUT_OF_DOMAIN"


def test_single_model_and_empty():
    r = one(run_task(M, TASK, caller({"h": reply(("두께", "25", "q"))}), "h", None))
    assert r.status == "PENDING" and r.agreed is None
    assert run_task(M, TASK, caller({"h": reply(), "l": reply()}), "h", "l") == []        # allow_empty


def test_not_allow_empty_gives_unreadable():
    class Strict(Dummy):
        allow_empty = False
    assert one(run_task(Strict(), TASK, caller({"h": reply(), "l": reply()}), "h", "l")).hold_code == "AI_UNREADABLE"


def test_conformance_schema():
    assert C.check_schema(M.schema) == []
    bad = {"type": "object", "additionalProperties": False, "required": ["a"],
           "properties": {"a": {"type": "string", "pattern": "x"}, "b": {"anyOf": []}}}
    probs = C.check_schema(bad)
    assert any("pattern" in p for p in probs) and any("required" in p for p in probs) and any("anyOf" in p for p in probs)


def test_conformance_imports(tmp_path):
    pkg = tmp_path / "l9_bad"
    (pkg / "tests").mkdir(parents=True)
    (pkg / "module.py").write_text("import os\nimport requests\nfrom ..l2_boq import x\nfrom ..contract import AITask\n"
                                   "k = os.environ['KEY']\n", encoding="utf-8")
    (pkg / "tests" / "t.py").write_text("import requests\n", encoding="utf-8")   # tests는 검사 밖
    probs = C.check_imports(pkg)
    assert len(probs) == 3 and any("requests" in p for p in probs) and any("l2_boq" in p for p in probs) \
        and any("environ" in p for p in probs)


def test_conformance_document_roles():
    assert C.check_document_roles(M) == []
    class Old(Dummy):
        document_role = "SPEC"
    class Bad(Dummy):
        document_roles = ("SPEC", "MEMO", "SPEC")
    class Empty(Dummy):
        document_roles = ()
    assert any("document_role(단수)" in p for p in C.check_document_roles(Old()))
    probs = C.check_document_roles(Bad())
    assert any("MEMO" in p for p in probs) and any("중복" in p for p in probs)
    assert C.check_document_roles(Empty()) and C.check_document_roles(type("L", (Dummy,), {"document_roles": ["SPEC"]})())
    assert DocumentRef(id=DOC, role="NOTICE", file_name="공고문.hwp", extension="hwp").role == "NOTICE"


def test_conformance_contract_major(tmp_path):
    class V2(Dummy):
        contract_version = "2.0"
    pkg = tmp_path / "l9"
    pkg.mkdir()
    assert any("주 번호" in p for p in C.check_module(V2(), pkg, FakeContext(paths={}), []))
    assert not any("주 번호" in p for p in C.check_module(M, pkg, FakeContext(paths={}), []))


def test_conformance_tasks_and_determinism():
    ctx = FakeContext(paths={}, role_limits=RoleLimits(max_prompt_tokens=10))
    doc = DocumentRef(id=DOC, role="SPEC", file_name="a.hwp", extension="hwp")
    assert C.check_prepare_deterministic(M, ctx, doc) == []
    assert C.check_tasks(M.prepare(ctx, doc), ctx, M) == []
    ctx.role_limits = RoleLimits(max_prompt_tokens=3)
    assert any("max_prompt_tokens" in p for p in C.check_tasks(M.prepare(ctx, doc), ctx, M))
