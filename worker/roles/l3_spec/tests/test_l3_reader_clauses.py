"""L3 1·2단계 (원문 읽기, 조항 나누기) 단위 시험. 모델·네트워크 없음.
실제 공고 원본(03_수집_3년)이 있으면 S24·S25·S26 조항 수도 확인하고, 없으면 그 시험만 건너뛴다."""
import os
import sys
from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest

APP = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(APP))

from worker.roles.contract import RoleInputError  # noqa: E402
from worker.roles.l3_spec.clauses import split_clauses  # noqa: E402
from worker.roles.l3_spec.reader import Line, SpecText, clean, read_spec  # noqa: E402

DOC = uuid4()
COLLECT = Path(os.environ.get("LETS_DATA_ROOT") or APP.parent) / "03_수집_3년"   # 원본이 없으면 그 시험만 건너뜀


def spec(text: str, kind="HWP") -> SpecText:
    return SpecText(kind, [Line(t) for t in text.split("\n")])


def nos(doc):
    return list(doc.clauses)


# ---- 1단계 읽기 ----

def test_clean_removes_parser_artifacts():
    assert clean("\tĀ\t가. 자동제어기능") == "\t가. 자동제어기능"       # S24 7.가 HWP 제어 문자
    assert clean("￿공사구역은") == "공사구역은"                       # S26 점검표 체크박스
    assert clean("a\xa0b\x07c") == "a bc"


def _pdf(tmp_path, pages):
    d = pymupdf.open()
    for lines in pages:
        p = d.new_page()
        for i, t in enumerate(lines):
            p.insert_text((72, 72 + 14 * i), t)
    f = tmp_path / "s.pdf"
    d.save(f)
    return f


def test_read_pdf_pages_and_image_pages(tmp_path):
    f = _pdf(tmp_path, [["- 1 -", "1. Scope", "body line"], ["- 2 -"], ["2. Pipe", "- 3 -"]])
    s = read_spec(f, DOC, "pdf")
    assert s.kind == "PDF" and s.pages == 3 and s.image_pages == [2]
    assert [(x.text, x.page) for x in s.lines if x.text] == [("1. Scope", 1), ("body line", 1), ("2. Pipe", 3)]


def test_read_errors(tmp_path):
    with pytest.raises(RoleInputError) as e:
        read_spec(_pdf(tmp_path, [["- 1 -"]]), DOC, "pdf")
    assert e.value.code == "EMPTY" and e.value.document_id == DOC
    with pytest.raises(RoleInputError) as e:
        read_spec(tmp_path / "x.docx", DOC, "docx")
    assert e.value.code == "UNSUPPORTED_FORMAT"
    bad = tmp_path / "bad.hwp"
    bad.write_bytes(b"not an ole file")
    with pytest.raises(RoleInputError) as e:
        read_spec(bad, DOC, "hwp")
    assert e.value.code in ("PARSE_FAILED", "EMPTY")


# ---- 2단계 조항 나누기 ----

def test_s24_style_boxes_restart_numbering():
    d = split_clauses(spec("표지\n□ 일반사항\n1. 공사명 : 시험\n2. 일반사항\n 가. 제품은 준수한다.\n"
                           "5. 번호가 이어지지 않는 끊긴 줄\n4. 하나 건너뛴 번호\n"
                           "□ 설치 시방서\n1. 실내기 설치\n 가. 설치 위치\n    ① 흡입구 부근\n"
                           "2. 냉매 배관\n 가. 냉매 배관은\n 나. 1.5～2m 간격으로 지지\n  (1) 유선 리모컨\n   ① 천장 속"))
    assert d.dropped_preamble == 1
    assert nos(d) == ["□1", "□1 1.", "□1 2.", "□1 2. 가.", "□1 4.", "□2", "□2 1.", "□2 1. 가.", "□2 1. 가. ①",
                      "□2 2.", "□2 2. 가.", "□2 2. 나.", "□2 2. 나. (1)", "□2 2. 나. (1) ①"]
    assert "5. 번호가" in d.clauses["□1 2. 가."].text                     # 2. 다음 5.(+3)는 본문
    assert d.clauses["□1 4."].memo.startswith("번호 건너뜀")              # 2. 다음 4.(+2)는 조항 + 메모
    assert d.clauses["□2 1."].parent == "□2" and d.clauses["□2"].children == ["□2 1.", "□2 2."]


def test_s25_style_toc_decimal_nested_skip_and_missing_dot():
    d = split_clauses(spec(
        "시 방 서\n목       차\n제 1 장 일반사항\n      1.1 일반사항\n제 3 장 설치\n"
        "제1장  일반사항\n1.1 일반사항\n1.1.8. 지급자재\n  1) 인도장소\n1.1.14 기타사항\n  3) 사진보고\n"
        "  4) 일요일 휴무제\n      1) 운영 제한\n      2) 승인 후 실시\n  5) 바깥 목록\n"
        "제3장 설치공사\n3.2 냉난방기 설치시방서\n1. 실내기 설치\n2. 자동제어공사\n 1) 자동제어기능\n"
        "3 냉매 배관\n8) 냉매 배관은\n1.5 m 간격으로 지지\n 8) 접합 작업\n 10) 사후 관리"))
    assert d.dropped_toc == 4 and d.dropped_preamble == 1                 # 목차 4줄, 표지 1줄
    assert "1.1.8 1)" in d.clauses and "1.1.14 4) 1)" in d.clauses and "1.1.14 4) 2)" in d.clauses
    assert d.clauses["1.1.14 5)"].parent == "1.1.14"                     # 중첩 목록 뒤 바깥 번호
    assert d.clauses["3.2 3."].memo.startswith("마침표 없는 번호")
    assert "1.5 m 간격으로 지지" in d.clauses["3.2 3. 8)"].text          # 줄 첫머리 1.5는 조항 아님
    assert "3.2 3. 10)" in d.clauses and d.clauses["3.2 3. 10)"].memo.startswith("번호 건너뜀")
    assert not d.duplicates


def test_s26_style_chapters_attachments_and_wrapped_lines():
    d = split_clauses(spec(
        "공통시방서\n□ 일반사항\n ○ 계약자는\n첨부1\n1. 병원내의 정보\n2. 출입\n첨부2\n1. 화재예방\n"
        "목 차\n제 1 장  일 반 사 항\n1. 적용 범위\n제 1 장  일 반 사 항\n1. 적용 범위\n본 시방서는\n"
        "제 3 장  멀티형\n2. 장비 설치\n1) 실외기\n(4) 최장 배관 길이 175m\n, 헤더 적용 시\n(5) 상부 1,500 ㎜ 이내",
        kind="PDF"))
    assert nos(d)[:6] == ["□1", "첨부1", "첨부1 1.", "첨부1 2.", "첨부2", "첨부2 1."]
    assert "제1장 1." in d.clauses and d.dropped_toc == 3                 # 목 차 · 제1장 · 1. 적용 범위
    assert "제3장 2. 1) (5)" in d.clauses and ", 헤더 적용 시" in d.clauses["제3장 2. 1) (4)"].text


def test_duplicate_numbers_get_suffix_and_subtree_text():
    d = split_clauses(spec("1. 가\n1. 나\n 가. 하위 문장\n  ① 더 아래"))
    assert nos(d) == ["1.", "1.#2", "1.#2 가.", "1.#2 가. ①"] and d.duplicates == ["1."]
    assert d.subtree_text("1.#2") == "1. 나\n 가. 하위 문장\n  ① 더 아래"


def test_table_lines_are_body():
    d = split_clauses(spec("1.2.8 보온공사\n| 1. 장비류 철거 2. 구멍뚫기 |\n| 결로방지용 | 25T |"))
    assert nos(d) == ["1.2.8"] and "25T" in d.clauses["1.2.8"].text


def test_package_imports_follow_contract():
    from worker.roles.conformance import check_imports
    assert check_imports(Path(__file__).resolve().parents[1]) == []


# ---- 실제 원본 (있을 때만) ----

REAL = {"S24": ("2024/20240120529_*/03_시방서_과업/20240120529-01_*공사시방서.hwp", 88),
        "S25": ("2025/R25BK01074925_*/03_시방서_과업/*.hwp", 316),   # 11-26 한 줄에 붙은 '3.2 4. 2)' 나눔
        "S26": ("2026/R26BK01716759_*/03_시방서_과업/*.pdf", 301)}


@pytest.mark.parametrize("sid", list(REAL))
def test_real_specs(sid):
    pat, n = REAL[sid]
    found = list(COLLECT.glob(pat))
    if not found:
        pytest.skip("공고 원본 없음")
    s = read_spec(found[0], DOC, found[0].suffix)
    d = split_clauses(s)
    assert len(d.clauses) == n and not d.duplicates
    if sid == "S26":
        assert s.image_pages == list(range(23, 48))
        assert "제2장 3. 8)" in d.clauses and "1.2 ~1.5 m" in d.clauses["제2장 3. 8)"].text
    if sid == "S25":
        assert "3.2 3. 8)" in d.clauses and "1.1.14 4) 3)" in d.clauses
        assert "실외노출 배관 트레이" in d.clauses["3.2 4. 2)"].text                 # 한 줄에 붙은 2) 나눔 (Codex 4-4)
        assert "실외노출 배관 트레이" not in d.clauses["3.2 4. 1)"].text
    if sid == "S24":
        assert "□2 3. 아." in d.clauses and "1.5～2m" in d.clauses["□2 3. 아."].text
