"""시방서 조항 나누기 (L3 2단계). 모델을 쓰지 않는다.

조항 번호 표시 (S24·S25·S26 원본에서 확인한 것)
  고정 단계  제N장 · □(덩어리) · 첨부N/서식N/부록N/별첨N/붙임N · 1.1 / 1.1.7 (소수점 번호)
  순서 단계  1.  가.  1)  (1)  ①  — 문서마다 중첩 순서가 달라서 처음 나온 순서대로 단계를 정한다
             (S24: 1. > 가. > ① · (1),  S25 3장: 1. > 1) > (1) > ①,  S26: 제N장 > 1. > 1) > (1) > ①)

clause_no 만드는 법 (정답 입력과 pair_key가 같은 문자열을 쓴다)
  경로의 표시를 공백으로 잇는다. 소수점 번호가 경로에 있으면 그 앞(장)은 뺀다 (소수점 번호가 이미 장을 담음).
  □는 문서 안 순서로 번호를 붙인다 (원문에 번호가 없음).
  예) S25 "1.1.7 2)"  "3.2 3. 8)"   S24 "□2 3. 아."   S26 "제2장 3. 8)"  "제3장 2. 3) (1) ③"
  같은 번호가 다시 나오면 "#2"를 붙인다 (예: 병합 PDF의 첨부 문서).

같은 표시가 겹쳐 쓰인 목록: 직전 같은 표시보다 더 들여 쓴 "1)"은 하위 목록으로 본다 (S25 "1.1.14 4) 1)")
번호를 하나 건너뛴 경우(원문 오타, S25 2.3.7의 8) 다음 10))는 조항 번호로 받고 메모에 남긴다
한 줄에 다음 번호가 붙은 경우: "1) …한다. 2) …"처럼 줄이 순서 번호로 시작하고, 문장 끝(마침표) 뒤에 같은 표시의 다음 번호가
  오면 그 자리에서 줄을 나눈다 (2026-11-26, S25 "3.2 4. 1)" 안의 "2) 실외노출 배관 트레이"). 1)·(1)·① 표시만

본문으로 보는 것 (조항 번호 아님)
  - 번호가 이어지지 않는 줄: 같은 단계 직전 번호+1·+2가 아니고 1도 아니면 줄바꿈으로 끊긴 문장으로 본다
  - 소수점 번호는 뒤에 한글 제목이 오고, 장 안에서는 첫 자리가 장 번호와 같을 때만 ("1.5 m 간격" 같은 줄 방지)
  - 마침표 없는 "3 냉매 배관"은 같은 단계 직전 번호가 2.일 때만 3.으로 본다 (S25 3.2)
  - 표 줄(| … |), 글머리표(-, ○, ▪)
목차: "목차" 줄부터 목차 첫 항목이 본문에 다시 나오기 전까지 뺀다. 첫 조항 번호 앞(표지)도 뺀다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .reader import Line, SpecText

HANGUL_SEQ = "가나다라마바사아자차카타파하"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

RE_CHAPTER = re.compile(r"^제\s*(\d{1,2})\s*장(?=\s|$)")
RE_BOX = re.compile(r"^□\s*(\S.*)$")
RE_ATTACH = re.compile(r"^(첨부|서식|부록|별첨|붙임)\s*(\d{1,2})\s*$")
RE_DECIMAL = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s*(?=[가-힣])")
RE_NUM_DOT = re.compile(r"^(\d{1,2})\.(?!\d)\s*(?=\S)")
RE_NUM_SPACE = re.compile(r"^(\d{1,2})\s+(?=[가-힣])")
RE_HANGUL = re.compile(rf"^([{HANGUL_SEQ}])\.\s*(?=\S)")
RE_PAREN_R = re.compile(r"^(\d{1,2})\)\s*(?=\S)")
RE_PAREN_BOTH = re.compile(r"^\((\d{1,2})\)\s*(?=\S)")
RE_CIRCLED = re.compile(rf"^([{CIRCLED}])\s*(?=\S)")
SQUASH = re.compile(r"\s+")

FIXED_RANK = {"chapter": 0, "box": 1, "attach": 1}   # 소수점 번호는 1 + 자리 수 (1.1 → 3, 1.1.7 → 4)
DYNAMIC = ("num_dot", "hangul", "paren_r", "paren_both", "circled")


def squash(s: str) -> str:
    return SQUASH.sub("", s)


@dataclass
class Clause:
    no: str
    parent: str | None
    kind: str
    title: str
    lines: list[Line] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    memo: str = ""                         # 번호를 추정했거나 건너뛴 번호를 받았으면 사유

    @property
    def text(self) -> str:
        return "\n".join(x.text for x in self.lines)

    @property
    def pages(self) -> list[int]:
        return sorted({x.page for x in self.lines if x.page is not None})


@dataclass
class ClauseDoc:
    clauses: dict[str, Clause]             # 문서 순서
    dropped_preamble: int = 0
    dropped_toc: int = 0
    duplicates: list[str] = field(default_factory=list)

    def subtree(self, no: str) -> list[Clause]:
        out, todo = [], [no]
        while todo:
            c = self.clauses[todo.pop(0)]
            out.append(c)
            todo = c.children + todo
        return out

    def subtree_text(self, no: str) -> str:
        """조항과 하위 조항 원문 전체 (인용문 대조 G2는 모델이 든 조항의 하위까지 본다)."""
        return "\n".join(c.text for c in self.subtree(no))


@dataclass
class _Node:
    kind: str
    rank: int
    value: int
    token: str
    no: str
    indent: int = 0


def indent_of(text: str) -> int:
    t = text.expandtabs(4)
    return len(t) - len(t.lstrip(" "))


def _dynamic(kind: str, value: int, token: str, stack: list[_Node], ind: int):
    """순서 단계 번호 판정. (kind, 99, value, token, memo, cut) 또는 None.
    cut: 스택에서 지울 위치(그 자리의 형제가 됨). None이면 지우지 않고 하위로 넣는다.
    - 같은 표시가 스택에 없으면 새 하위 목록
    - 같은 표시 중 위에서부터 번호+1이 맞는 것의 형제 (중첩 목록이 끝나고 바깥 번호가 이어지는 경우 포함)
    - 1이면: 직전 같은 표시보다 더 들여 썼으면 하위 목록, 아니면 새로 시작하는 형제
    - 맨 위 같은 표시의 번호+2면 건너뛴 번호로 받고 메모
    - 그 밖은 본문 (줄바꿈으로 끊긴 문장)"""
    same = [k for k in range(len(stack) - 1, -1, -1) if stack[k].kind == kind]
    if not same:
        return kind, 99, value, token, "", None
    for k in same:
        if value == stack[k].value + 1:
            return kind, 99, value, token, "", k
    top = same[0]
    if value == 1:
        return kind, 99, value, token, "", (None if ind > stack[top].indent + 1 else top)
    if value == stack[top].value + 2:
        return kind, 99, value, token, f"번호 건너뜀 ({stack[top].token} 다음 {token})", top
    return None


def _match(text: str, stack: list[_Node], ind: int):
    """줄 앞의 조항 번호. (kind, rank, value, token, memo, cut) 또는 None. cut은 순서 단계에만 쓴다."""
    s = text.strip()
    if not s or s.startswith("|"):
        return None
    if m := RE_CHAPTER.match(s):
        n = int(m.group(1))
        return "chapter", 0, n, f"제{n}장", "", None
    if RE_BOX.match(s):
        return "box", 1, 0, "□", "", None
    if m := RE_ATTACH.match(s):
        return "attach", 1, int(m.group(2)), f"{m.group(1)}{m.group(2)}", "", None
    if m := RE_DECIMAL.match(s):
        parts = [int(p) for p in m.group(1).split(".")]
        chapter = next((n.value for n in reversed(stack) if n.kind == "chapter"), None)
        if chapter is None or parts[0] == chapter:
            return "decimal", 1 + len(parts), parts[-1], ".".join(map(str, parts)), "", None
    if m := RE_PAREN_BOTH.match(s):
        v = int(m.group(1))
        return _dynamic("paren_both", v, f"({v})", stack, ind)
    if m := RE_PAREN_R.match(s):
        v = int(m.group(1))
        return _dynamic("paren_r", v, f"{v})", stack, ind)
    if m := RE_NUM_DOT.match(s):
        v = int(m.group(1))
        return _dynamic("num_dot", v, f"{v}.", stack, ind)
    if m := RE_HANGUL.match(s):
        v = HANGUL_SEQ.index(m.group(1)) + 1
        return _dynamic("hangul", v, f"{m.group(1)}.", stack, ind)
    if m := RE_CIRCLED.match(s):
        v = CIRCLED.index(m.group(1)) + 1
        return _dynamic("circled", v, m.group(1), stack, ind)
    if (m := RE_NUM_SPACE.match(s)) and len(s) <= 40:
        v = int(m.group(1))
        k = next((k for k in range(len(stack) - 1, -1, -1) if stack[k].kind == "num_dot"), None)
        if k is not None and v == stack[k].value + 1:
            return "num_dot", 99, v, f"{v}.", f"마침표 없는 번호를 순서로 추정 ('{s[:10]}')", k
    return None


_INLINE = (
    (re.compile(r"^(\d{1,2})\)\s*\S"), lambda v: rf"{v + 1}\)"),
    (re.compile(r"^\((\d{1,2})\)\s*\S"), lambda v: rf"\({v + 1}\)"),
    (re.compile(rf"^([{CIRCLED}])\s*\S"), None),
)


def _split_inline(lines: list[Line]) -> list[Line]:
    """줄 안에서 문장 끝 뒤에 다음 순서 번호가 오면 나눈다 (모듈 설명 참고)."""
    out = []
    for line in lines:
        todo = line.text
        while True:
            t = todo.strip()
            nxt = None
            for rx, make in _INLINE:
                if m := rx.match(t):
                    if make is None:
                        v = CIRCLED.index(m.group(1)) + 1
                        nxt = re.escape(CIRCLED[v]) if v < len(CIRCLED) else None
                    else:
                        nxt = make(int(m.group(1)))
                    break
            hit = re.search(rf"(?<=\.)\s+(?={nxt}\s*\S)", todo) if nxt else None
            if not hit:
                out.append(Line(todo, line.page) if todo is not line.text else line)
                break
            pad = todo[:len(todo) - len(todo.lstrip(" "))]
            out.append(Line(todo[:hit.start()], line.page))
            todo = pad + todo[hit.end():]
    return out


def _drop_toc(lines: list[Line]) -> tuple[list[Line], int]:
    out, dropped, i = [], 0, 0
    while i < len(lines):
        if squash(lines[i].text) == "목차":
            first = next((j for j in range(i + 1, len(lines)) if squash(lines[j].text)), None)
            key = squash(lines[first].text) if first is not None else None
            again = next((j for j in range(first + 1, len(lines)) if squash(lines[j].text) == key), None) \
                if key else None
            end = again if again is not None else i + 1
            dropped += end - i
            i = end
            continue
        out.append(lines[i])
        i += 1
    return out, dropped


def _clause_no(stack: list[_Node]) -> str:
    """상위 조항의 실제 번호(#2가 붙었으면 그것까지) + 이 표시. 소수점 번호는 그 자체가 번호다."""
    node = stack[-1]
    if node.kind == "decimal" or len(stack) == 1:
        return node.token
    return f"{stack[-2].no} {node.token}"


def split_clauses(spec: SpecText) -> ClauseDoc:
    lines, dropped_toc = _drop_toc(_split_inline(spec.lines))
    doc = ClauseDoc({}, dropped_toc=dropped_toc)
    stack: list[_Node] = []
    boxes = 0
    current: Clause | None = None
    for line in lines:
        ind = indent_of(line.text)
        m = _match(line.text, stack, ind)
        if m is None:
            if current is None:
                doc.dropped_preamble += 1
            else:
                current.lines.append(line)
            continue
        kind, rank, value, token, memo, cut = m
        if kind == "box":
            boxes += 1
            token = f"□{boxes}"
        if kind in DYNAMIC:
            if cut is not None:
                del stack[cut:]
        else:
            while stack and stack[-1].rank >= rank:
                stack.pop()
        parent = stack[-1].no if stack else None
        stack.append(_Node(kind, rank, value, token, "", ind))
        no = _clause_no(stack)
        if no in doc.clauses:
            k = 2
            while f"{no}#{k}" in doc.clauses:
                k += 1
            doc.duplicates.append(no)
            no = f"{no}#{k}"
        stack[-1].no = no
        current = Clause(no, parent, kind, line.text.strip()[:80], [line], memo=memo)
        doc.clauses[no] = current
        if parent is not None:
            doc.clauses[parent].children.append(no)
    return doc
