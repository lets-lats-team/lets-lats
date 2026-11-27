"""역할 모듈 계약 1.1 — AI 설계 v0.7 11.4를 그대로 옮긴 것.

1.0 → 1.1 (2026-11-25): 문서 역할 NOTICE(공고문/현장설명서) 허용, RoleModule.document_role → document_roles(튜플).

임시본 (2026-11-25, 김선진·Claude Code). 공통 엔진 담당이 정식본을 만들면 그것으로 바꾼다.
설계서와 다른 점은 아래 '설계서에 없는 것' 표시가 붙은 곳뿐이다.

- 역할 모듈은 DB·네트워크·환경 변수를 쓰지 않고 다른 역할 모듈을 가져다 쓰지 않는다 (계약 적합성 테스트가 확인).
- 공통 정규화(normalize_text·normalize_unit)는 엔진의 G5 비교도 같은 함수를 쓴다 (7장 3번).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

CONTRACT_VERSION = "1.1"

Role = Literal["V1", "V2", "V3", "V4", "L1", "L2", "L3", "L4", "L5", "E1"]
HoldCode = Literal["AI_NO_RESPONSE", "AI_UNREADABLE", "AI_DISAGREE", "AI_NO_EVIDENCE",
                   "AI_NOT_ATTACHED", "AI_OUT_OF_DOMAIN", "AI_CONFLICT", "AI_BUDGET", "AI_DISABLED"]

# 11.4 '실행 순서와 보류 코드': 여러 검사가 실패하면 앞에 있는 코드 하나만 남긴다
HOLD_PRIORITY: list[str] = ["AI_DISABLED", "AI_BUDGET", "AI_NO_RESPONSE", "AI_UNREADABLE", "AI_NO_EVIDENCE",
                            "AI_OUT_OF_DOMAIN", "AI_NOT_ATTACHED", "AI_DISAGREE", "AI_CONFLICT"]

DocRole = Literal["DRAWING", "BOQ", "SPEC", "NOTICE"]
EvidenceKind = Literal["CAD", "PDF", "XLSX", "HWP", "AI", "MANUAL"]   # HWPX도 HWP

# Evidence.location 필수 키 (11.4 표)
LOCATION_REQUIRED: dict[str, set[str]] = {
    "CAD": {"handle"}, "PDF": {"page", "clause_no"}, "HWP": {"clause_no"},
    "XLSX": {"sheet", "cell"}, "AI": {"image_key"}, "MANUAL": {"note"},
}


def first_hold(codes) -> str | None:
    """보류 코드 우선순위에서 가장 앞의 것. 없으면 None."""
    present = [c for c in codes if c]
    return min(present, key=HOLD_PRIORITY.index) if present else None


class DocumentRef(BaseModel):
    id: UUID
    role: DocRole                 # DRAWING / BOQ / SPEC / NOTICE
    file_name: str
    extension: str                # 소문자, 점 없이. 예: "hwpx", "pdf"
    revision_label: str | None = None


class Evidence(BaseModel):            # D05 source_ref 한 행이 된다
    kind: EvidenceKind
    document_id: UUID | None          # MANUAL만 None. 그 밖의 kind에서 None이면 검증 오류 (DB CHECK와 같음)
    location: dict
    quote: str | None = None          # 텍스트 역할은 필수 (G2)

    @model_validator(mode="after")
    def _check(self):
        if self.kind != "MANUAL" and self.document_id is None:
            raise ValueError(f"{self.kind} 근거에는 document_id가 필요하다")
        missing = LOCATION_REQUIRED[self.kind] - set(self.location)
        if missing:
            raise ValueError(f"{self.kind} location에 {sorted(missing)} 없음")
        return self


class Part(BaseModel):                # 모델에 실제로 보내는 조각
    kind: Literal["text", "image"]
    text: str | None = None
    image_key: str | None = None      # S3 키. RoleContext.put_image로 받는다


class AITask(BaseModel):
    role: Role
    target_key: str                   # 분석 안에서 유일. L3: "spec:<document_id>:<청크 순번>"
    parts: list[Part]
    source: Evidence | None           # 이 입력이 나온 원본 위치. 원본 문서가 없는 L5·E1만 None
    affects_output: bool              # SHD·대조에 쓰이면 True → 교차 확인
    private: dict = Field(default_factory=dict)   # 모델에 보내지 않는 역할 전용 자료. 예: G2 대조용 조항 원문


class Candidate(BaseModel):           # 한 모델이 낸 후보 하나 (정규화 뒤)
    value: dict                       # 비교하고 저장할 정규화 값. 표기 원문은 넣지 않는다
    raw: dict                         # 응답에서 이 후보에 해당하는 원문
    evidence: list[Evidence]          # 첫 번째가 이 후보의 원문 위치
    hold_code: HoldCode | None = None # postprocess가 붙인 보류 코드. None이면 통과
    note: str = ""                    # 설계서에 없는 것: 보류 사유 설명 (로그·평가용, 저장 계약 밖)


class CallMeta(BaseModel):            # 모델 호출 한 번의 기록. D05(kind=AI)에 남긴다
    model: str
    is_primary: bool
    response_id: str | None
    latency_ms: int
    tokens_in: int
    tokens_out: int


class AIResult(BaseModel):            # 엔진이 짝짓기와 비교를 끝낸 결과. 역할 모듈은 만들지 않는다
    role: Role
    target_key: str
    pair_key: str | None              # 후보가 0건이면 None
    status: Literal["PENDING", "HELD"]
    hold_code: HoldCode | None
    candidates: dict[str, Candidate]  # {"haiku": …, "luna": …}. 보류여도 남은 후보는 참고로 둔다
    agreed: bool | None               # 교차 확인 일치 여부. 단독 역할은 None
    source: Evidence | None           # AITask.source 그대로
    calls: list[CallMeta] = Field(default_factory=list)


class RoleInputError(Exception):      # prepare가 문서를 읽지 못함
    def __init__(self, code: Literal["UNSUPPORTED_FORMAT", "ENCRYPTED", "PARSE_FAILED", "EMPTY"],
                 document_id: UUID, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.document_id = document_id
        self.detail = detail          # 로그용. 문서 원문은 넣지 않는다


class RoleLimits(BaseModel):          # ai.routing의 역할 항목. 값이 없으면 기본값
    timeout_s: int = 20
    max_tokens: int = 1024
    max_prompt_tokens: int = 100_000
    chunk_tokens: int | None = None   # L3: 20_000


@runtime_checkable
class RoleContext(Protocol):          # 엔진이 만들어 넘긴다. DB를 바꾸지 않는다
    analysis_id: UUID

    def document_path(self, document_id: UUID) -> Path: ...
    def limits(self) -> RoleLimits: ...
    def count_tokens(self, text: str) -> int: ...
    def put_image(self, png: bytes, name: str) -> str: ...


@runtime_checkable
class RoleModule(Protocol):
    role: Role
    contract_version: str
    prompt_version: str
    system_prompt: str
    schema: dict
    document_roles: tuple[DocRole, ...]   # prepare에 넘길 문서 종류 (L3: ("SPEC", "NOTICE"))
    allow_empty: bool

    def prepare(self, ctx: RoleContext, doc: DocumentRef) -> list[AITask]: ...
    def postprocess(self, task: AITask, response: dict) -> list[Candidate]: ...
    def pair_key(self, candidate: Candidate) -> str: ...


# ---- 공통 정규화 (AI 설계 7장 3번). 엔진의 G5 비교도 같은 함수를 쓴다 ----

_WS = re.compile(r"\s+")
# Ø·φ·ø 통일. 설계서에 없는 것: 그리스 대문자 Φ와 지름 기호 ∅도 같은 글자로 본다 (S24 'Φ6.35', S26 '∅')
_DIAMETER = str.maketrans({"φ": "Ø", "ø": "Ø", "Φ": "Ø", "∅": "Ø", "ϕ": "Ø"})


def _halfwidth(s: str) -> str:
    """전각 ASCII(！~～)와 전각 공백을 반각으로. NFKC는 쓰지 않는다 (㎡→m2 같은 의미 변경을 피함)."""
    out = []
    for ch in s:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        elif o == 0x3000:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def normalize_text(s: str) -> str:
    """앞뒤 공백 제거, 연속 공백 하나로, 전각→반각, Ø·φ·ø 통일."""
    return _WS.sub(" ", _halfwidth(s or "").translate(_DIAMETER)).strip()


_UNITS = {
    "㎜": "mm", "밀리미터": "mm", "MM": "mm", "Mm": "mm",
    "㎝": "cm", "CM": "cm",
    "M": "m", "미터": "m",
    "㎏": "kg", "KG": "kg", "Kg": "kg",
    "㎾": "kW", "KW": "kW", "kw": "kW", "Kw": "kW",
    "hp": "HP", "Hp": "HP",
    "w": "W", "a": "A", "v": "V",
    "㎩": "Pa", "PA": "Pa", "pa": "Pa",
    "㎪": "kPa", "KPA": "kPa", "kpa": "kPa", "KPa": "kPa",
    "㎫": "MPa", "MPA": "MPa", "mpa": "MPa", "Mpa": "MPa",
    "°C": "℃", "˚C": "℃", "도": "℃", "C°": "℃",
    "퍼센트": "%", "％": "%",
    # 설계서에 없는 것 (2026-11-25, L3 원문에 나온 표기): 면적·압력·개수
    "㎡": "m²", "m2": "m²", "M2": "m²",
    "㎏/㎠": "kgf/cm²", "kg/㎠": "kgf/cm²", "kg/cm2": "kgf/cm²", "kgf/cm2": "kgf/cm²", "kg/cm²": "kgf/cm²",
    "t": "T", "ea": "EA", "Ea": "EA",
}


def normalize_unit(s: str) -> str:
    """단위 표기 통일 (예: "㎜"→"mm"). 목록에 없는 표기는 공백만 정리해 그대로 둔다."""
    t = normalize_text(s).replace(" ", "")
    return _UNITS.get(t, t)
