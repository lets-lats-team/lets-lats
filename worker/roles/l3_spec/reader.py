"""시방서 원문 읽기 (L3 1단계). 모델을 쓰지 않는다.

- HWP·HWPX: hwp-hwpx-parser (AI 설계 6.2·17장 결정). 표는 마크다운 줄(| … |)로 본문에 들어온다
- PDF: 글자층 (pymupdf). 쪽마다 글자를 읽고, 쪽 번호 줄("- 3 -")은 뺀다. 글자층이 없는 쪽은 image_pages에 남긴다
  (V4 후보 — L3는 읽지 않고 기록만 한다)
- 읽지 못하면 RoleInputError: 암호화 ENCRYPTED, 글자 없음 EMPTY, 그 밖의 형식 UNSUPPORTED_FORMAT, 파서 예외 PARSE_FAILED

결과는 줄 목록이다. 줄마다 PDF 쪽 번호를 붙인다 (HWP는 None). 조항 나누기는 clauses.py가 한다.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID

from ..contract import RoleInputError

PAGE_NO = re.compile(r"^\s*[-–]\s*\d+\s*[-–]\s*$")   # PDF 쪽 번호 줄 "- 3 -"
HWP_CTRL = re.compile(r"\tĀ\t")                  # HWP 인라인 제어 문자가 'Ā'로 읽히는 경우 (S24 7.가)
MIN_PAGE_CHARS = 5                                    # 쪽 번호를 뺀 글자(공백 제외)가 이보다 적으면 글자층 없는 쪽


@dataclass
class Line:
    text: str
    page: int | None = None


@dataclass
class SpecText:
    kind: Literal["HWP", "PDF"]
    lines: list[Line]
    pages: int | None = None                          # PDF 쪽 수
    image_pages: list[int] = field(default_factory=list)


def clean(s: str) -> str:
    """제어 문자·미할당 문자(U+FFFF 체크박스 등)·사용자 정의 문자를 지운다. 줄바꿈·탭은 남긴다. NBSP는 공백으로."""
    s = HWP_CTRL.sub("\t", s).replace("\xa0", " ")
    return "".join(ch for ch in s if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cn", "Co", "Cs"))


def _read_hwp(path: Path, doc_id: UUID) -> SpecText:
    from hwp_hwpx_parser import Reader
    try:
        with Reader(path) as r:
            if r.is_encrypted:
                raise RoleInputError("ENCRYPTED", doc_id, "암호화된 HWP")
            text = r.extract_text()
    except RoleInputError:
        raise
    except Exception as e:  # noqa: BLE001 — 파서 내부 예외는 종류가 다양하다
        raise RoleInputError("PARSE_FAILED", doc_id, f"{type(e).__name__}: {str(e)[:200]}") from e
    lines = [Line(t) for t in clean(text).split("\n")]
    if not any(x.text.strip() for x in lines):
        raise RoleInputError("EMPTY", doc_id, "HWP에서 글자를 읽지 못함")
    return SpecText("HWP", lines)


def _read_pdf(path: Path, doc_id: UUID) -> SpecText:
    import pymupdf
    try:
        doc = pymupdf.open(path)
    except Exception as e:  # noqa: BLE001
        raise RoleInputError("PARSE_FAILED", doc_id, f"{type(e).__name__}: {str(e)[:200]}") from e
    with doc:
        if doc.needs_pass:
            raise RoleInputError("ENCRYPTED", doc_id, "암호화된 PDF")
        lines, image_pages = [], []
        for i, page in enumerate(doc, 1):
            raw = [clean(t) for t in page.get_text("text").split("\n")]
            body = [t for t in raw if not PAGE_NO.match(t)]
            if sum(len("".join(t.split())) for t in body) < MIN_PAGE_CHARS:
                image_pages.append(i)
                continue
            lines += [Line(t, i) for t in body]
        pages = doc.page_count
    if not lines:
        raise RoleInputError("EMPTY", doc_id, "글자층이 있는 쪽이 없음")
    return SpecText("PDF", lines, pages, image_pages)


def read_spec(path: Path, doc_id: UUID, extension: str) -> SpecText:
    ext = extension.lower().lstrip(".")
    if ext in ("hwp", "hwpx"):
        return _read_hwp(path, doc_id)
    if ext == "pdf":
        return _read_pdf(path, doc_id)
    raise RoleInputError("UNSUPPORTED_FORMAT", doc_id, f"확장자 {ext}")
