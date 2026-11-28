"""L3 시방서·공고문 조건 추출 역할 모듈 (AI 설계 v0.8 11.4 'L3 적용 예', 계약 1.1).

대상 문서: SPEC(시방서), NOTICE(공고문/현장설명서). 읽기·조항 나누기·프롬프트(l3-v3)는 둘 다 같다.
프롬프트 안에 공고문 규칙과 공사 방식 행 규칙이 있다 (공사 방식: item '냉매 배관', attribute '공사 방식', value R01 4종 코드).

prepare     시방서 하나 → 조항 묶음 작업들. 조항 단위로 chunk_tokens(기본 2,500) 안에 담고, 한 조항이 넘치면 줄 단위로 나눈다.
            모델에는 [[clause_no]] 줄 + 조항 자신의 원문만 보낸다. private에 G2 대조용 원문(하위 조항 포함)과 쪽 정보.
postprocess 규칙 하나 = Candidate 하나. clause_no 맞추기, 정규화, G2 인용문 대조(글자 값·공사 방식 근거 포함),
            G3 공사 방식 형식, G3 범위 값, G3 숫자·단위 붙여 씀, G3 단위 (checks.py)
            clause_no 맞추기 (2026-11-26 김선진 결정): 모델이 든 조항 원문(하위 포함)에 quote가 있으면,
            quote가 조항 자신의 본문에 없고 하위 조항 하나에만 있을 때 그 하위로 내려간다 (가장 아래 번호 — 정답과 같은 규칙).
            든 조항에 quote가 없으면 '#2' 꼬리만 다른 같은 번호 중 quote가 있는 조항이 하나일 때 그것으로 바꾼다.
            인용문 대조 자체는 그대로다 (모델이 든 번호 범위 밖으로는 옮기지 않음)
pair_key    clause_no | item | attribute | operator. item·attribute는 공백을 모두 뺀다
            (설계서는 normalize_text. 띄어쓰기만 다른 두 모델 답이 짝을 못 찾는 것을 막으려고 더 넓게 정규화 — README에 기록)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..contract import (CONTRACT_VERSION, AITask, Candidate, DocumentRef, Evidence, Part, RoleContext,
                        RoleInputError, normalize_text, normalize_unit)
from . import checks
from .clauses import ClauseDoc, split_clauses
from .reader import read_spec

HERE = Path(__file__).resolve().parent
PROMPT_VERSION = "l3-v3"
DEFAULT_CHUNK_TOKENS = 2_500   # 설계서 초기값 2만. 2026-11-26 실측: Haiku 출력 4096(설계 가정) 안에 들게 2,500 (README·트러블슈팅 기록)
HEADER = "아래 조항에서 조건을 뽑는다. (묶음 {n}/{total})\n\n"


def clause_label(no: str) -> str:
    return f"[[{no}]]"


class L3SpecModule:
    role = "L3"
    contract_version = CONTRACT_VERSION
    prompt_version = PROMPT_VERSION
    document_roles = ("SPEC", "NOTICE")
    allow_empty = True

    def __init__(self):
        self.system_prompt = (HERE / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
        self.schema = json.loads((HERE / "schemas" / f"{PROMPT_VERSION}.json").read_text(encoding="utf-8"))

    # ---------- prepare ----------

    def _blocks(self, doc: ClauseDoc, ctx: RoleContext, budget: int) -> list[tuple[str, str, bool]]:
        """(clause_no, 보낼 글, 첫 조각인가). 한 조항이 budget을 넘으면 줄 단위로 나눈다.
        한 줄이 머리표 포함 budget보다 길면 자르지 않고 여러 조각 줄로 나눈다 (2026-11-26 회귀 R-11: 뒷부분이 빠지던 것)."""
        out = []
        for c in doc.clauses.values():
            lim = max(1, budget - ctx.count_tokens(clause_label(c.no) + " (이어짐)\n"))
            lines = [p for x in c.lines for p in self._split_line(x.text, lim, ctx)]
            whole = clause_label(c.no) + "\n" + "\n".join(lines)
            if ctx.count_tokens(whole) <= budget:
                out.append((c.no, whole, True))
                continue
            piece, first = [], True
            for t in lines:
                cand = clause_label(c.no) + ("" if first else " (이어짐)") + "\n" + "\n".join(piece + [t])
                if piece and ctx.count_tokens(cand) > budget:
                    out.append((c.no, clause_label(c.no) + ("" if first else " (이어짐)") + "\n" + "\n".join(piece), first))
                    piece, first = [], False
                piece.append(t)
            if piece:
                out.append((c.no, clause_label(c.no) + ("" if first else " (이어짐)") + "\n" + "\n".join(piece), first))
        return out

    @staticmethod
    def _split_line(t: str, lim: int, ctx: RoleContext) -> list[str]:
        out = []
        while ctx.count_tokens(t) > lim:
            cut = min(len(t) - 1, lim)
            while cut > 1 and ctx.count_tokens(t[:cut]) > lim:
                cut = max(1, cut * 4 // 5)
            out.append(t[:cut])
            t = t[cut:]
        return out + [t]

    def prepare(self, ctx: RoleContext, doc: DocumentRef) -> list[AITask]:
        spec = read_spec(ctx.document_path(doc.id), doc.id, doc.extension)
        cdoc = split_clauses(spec)
        if not cdoc.clauses:
            raise RoleInputError("EMPTY", doc.id, "조항 번호를 찾지 못함")
        lim = ctx.limits()
        header = ctx.count_tokens(HEADER.format(n=999, total=999))
        overhead = ctx.count_tokens(self.system_prompt) + header
        # 묶음 크기(chunk_tokens)는 머리말을 포함한 사용자 글 전체 (2026-11-26: 머리말만큼 넘던 것)
        budget = min((lim.chunk_tokens or DEFAULT_CHUNK_TOKENS) - header, lim.max_prompt_tokens - overhead)
        if budget <= 0:
            raise RoleInputError("PARSE_FAILED", doc.id, "시스템 프롬프트가 max_prompt_tokens를 넘음")

        chunks: list[list[tuple[str, str, bool]]] = [[]]
        used = 0
        for blk in self._blocks(cdoc, ctx, budget):
            n = ctx.count_tokens(blk[1]) + 2
            if chunks[-1] and used + n > budget:
                chunks.append([])
                used = 0
            chunks[-1].append(blk)
            used += n

        kind = spec.kind
        tasks = []
        for i, chunk in enumerate(chunks):
            nos = list(dict.fromkeys(no for no, _, _ in chunk))
            text = HEADER.format(n=i + 1, total=len(chunks)) + "\n\n".join(t for _, t, _ in chunk)
            pages = {no: cdoc.clauses[no].pages for no in nos}
            first = nos[0]
            loc = {"clause_no": first, "chunk": i}
            if kind == "PDF":
                loc["page"] = (pages[first] or [0])[0]
            tasks.append(AITask(
                role="L3", target_key=f"spec:{doc.id}:{i}", parts=[Part(kind="text", text=text)],
                source=Evidence(kind=kind, document_id=doc.id, location=loc), affects_output=True,
                private={"kind": kind, "document_id": str(doc.id), "chunk": i,
                         "clauses": {no: cdoc.subtree_text(no) for no in nos},
                         # clause_no 맞추기용 조항 구조: 이 묶음 조항과 그 하위 전부 (하위가 다른 묶음이어도. 회귀 R-07)
                         "tree": {x.no: {"own": x.text, "children": list(x.children), "pages": x.pages}
                                  for no in nos for x in cdoc.subtree(no)},
                         "pages": pages,
                         "owned": [no for no, _, first_piece in chunk if first_piece],
                         "image_pages": spec.image_pages}))
        return tasks

    # ---------- postprocess ----------

    @staticmethod
    def normalize_rule(r: dict) -> dict:
        """비교·저장용 value. item·attribute는 공백 제거, value는 checks.normalize_value(공사 방식 행은 코드 대문자),
        unit은 공통 단위 정규화."""
        method = checks.is_method(r["attribute"])
        return {"item": checks.squash(normalize_text(r["item"])),
                "attribute": checks.squash(normalize_text(r["attribute"])),
                "operator": normalize_text(r["operator"]),
                "value": checks.normalize_method_value(r["value"]) if method else checks.normalize_value(r["value"]),
                "unit": normalize_unit(r["unit"])}

    @staticmethod
    def resolve_clause(no: str | None, cited: str, quote: str, priv: dict) -> str | None:
        """모델이 든 번호를 정답 규칙(quote가 든 가장 아래 조항)으로 맞춘다. 모듈 설명 참고."""
        q = checks.g2_norm(quote)
        clauses = priv["clauses"]
        if not q:
            return no
        tree = priv.get("tree", {})
        if no is None or q not in checks.g2_norm(clauses[no]):
            base = checks.squash(re.sub(r"#\d+", "", cited))
            same = [c for c in clauses if checks.squash(re.sub(r"#\d+", "", c)) == base
                    and q in checks.g2_norm(clauses[c])]
            if len(same) == 1:
                no = same[0]
        if no is None or q not in checks.g2_norm(clauses[no]):
            return no
        while no in tree and q not in checks.g2_norm(tree[no]["own"]):
            hit = [c for c in tree[no]["children"] if q in checks.g2_norm(L3SpecModule.source_text(priv, c))]
            if len(hit) != 1:
                break
            no = hit[0]
        return no

    @staticmethod
    def source_text(priv: dict, no: str) -> str:
        """G2 대조용 원문(하위 포함). 묶음 밖 하위 조항은 tree로 만든다."""
        if no in priv["clauses"]:
            return priv["clauses"][no]
        t = priv.get("tree", {}).get(no)
        if t is None:
            return ""
        return "\n".join([t["own"]] + [L3SpecModule.source_text(priv, c) for c in t["children"]])

    def postprocess(self, task: AITask, response: dict) -> list[Candidate]:
        priv = task.private
        by_squash = {checks.squash(no): no for no in priv["clauses"]}
        out = []
        for r in response["rules"]:
            cited = normalize_text(r["clause_no"]).replace("(이어짐)", "").strip("[] ")
            no = self.resolve_clause(by_squash.get(checks.squash(cited)), cited, r["quote"], priv)
            value = self.normalize_rule(r)
            code, note = None, ""
            if no is not None and checks.squash(no) != checks.squash(cited):
                note = f"clause_no 조정 '{cited}' → '{no}'"
            if no is None:
                code, note = "AI_NO_EVIDENCE", f"clause_no '{r['clause_no']}'가 이 묶음에 없음"
            elif why := checks.check_quote(r["quote"], self.source_text(priv, no), r["value"], r["attribute"]):
                code, note = "AI_NO_EVIDENCE", why
            elif why := checks.check_method(r["attribute"], r["operator"], r["value"], r["unit"], r["item"]):
                code, note = "AI_OUT_OF_DOMAIN", why
            elif why := checks.check_empty(r["value"]):
                code, note = "AI_OUT_OF_DOMAIN", why
            elif why := checks.check_range(r["value"]):
                code, note = "AI_OUT_OF_DOMAIN", why
            elif why := checks.check_glued(r["value"]):
                code, note = "AI_OUT_OF_DOMAIN", why
            elif why := checks.check_unit(r["value"], r["unit"]):
                code, note = "AI_OUT_OF_DOMAIN", why
            loc = {"clause_no": no or r["clause_no"], "chunk": priv["chunk"]}
            if priv["kind"] == "PDF":
                pg = (priv["pages"].get(no) or priv.get("tree", {}).get(no, {}).get("pages")) if no else None
                loc["page"] = (pg or [task.source.location.get("page", 0)])[0]
            ev = Evidence(kind=priv["kind"], document_id=task.source.document_id, location=loc, quote=r["quote"])
            out.append(Candidate(value=value, raw=dict(r), evidence=[ev], hold_code=code, note=note))
        return out

    # ---------- pair_key ----------

    def pair_key(self, candidate: Candidate) -> str:
        v = candidate.value
        clause = normalize_text(candidate.evidence[0].location["clause_no"])
        return "|".join([clause, v["item"], v["attribute"], v["operator"]])


MODULE = L3SpecModule()
