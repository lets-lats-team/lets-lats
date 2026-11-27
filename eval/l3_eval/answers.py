"""L3 정답 읽기: 정답 엑셀 'L3_조건' 시트 (읽기 전용, 저장하지 않음).

- 세트·item이 채워진 줄만 정답으로 쓴다. 출처 '이미지 표(V4)' 줄은 L3 채점에서 뺀다 (V4 몫, 개수만 센다)
- 정답 키는 모듈 pair_key와 같은 정규화: clause_no | item·attribute 공백 제거 | operator
- 문서 단위로 채점한다. '파일' 칸이 그 세트의 공고문 파일 이름이면 '<세트>-공고'(NOTICE), 비었거나 시방서 이름이면 '<세트>'(SPEC).
  그 밖의 파일 이름은 bad_file 행으로 센다
- operator가 6개(checks.OPERATORS) 밖이면 채점에서 빼고 bad_operator 행으로 센다 (11-26 연산자 6개 확정 전 입력분)
"""
from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # lets-lats
sys.path.insert(0, str(ROOT))

from worker.roles.contract import normalize_text, normalize_unit  # noqa: E402
from worker.roles.l3_spec import checks  # noqa: E402

# 원본·정답 자료 (저장소에는 없다). 환경 변수 LETS_DATA_ROOT(03_수집_3년이 있는 폴더), 없으면 lets-lats의 상위 폴더
COLLECT = Path(os.environ.get("LETS_DATA_ROOT") or ROOT.parent) / "03_수집_3년"
DEFAULT_ANSWERS = COLLECT / "정답셋_후보" / "정답_입력완.xlsx"
SHEET = "L3_조건"
SPECS = {   # 세트 → 시방서 원본 (정답셋_후보 안 복사본이 아니라 원본 경로)
    "S24": "2024/20240120529_*/03_시방서_과업/20240120529-01_*공사시방서.hwp",
    "S25": "2025/R25BK01074925_*/03_시방서_과업/*.hwp",
    "S26": "2026/R26BK01716759_*/03_시방서_과업/*.pdf",
}
NOTICE_SUFFIX = "-공고"
NOTICES = {   # 세트 → 공고문 원본 (2026-11-25 추가. S24는 같은 파일 -00·-02 중 -00, S26은 HWP·PDF 중 HWP)
    "S24": "2024/20240120529_*/00_공고문/20240120529-00_*입찰공고*.hwp",
    "S25": "2025/R25BK01074925_*/00_공고문/*.hwp",
    "S26": "2026/R26BK01716759_*/00_공고문/*입찰공고서.hwp",
}


def documents() -> dict[str, tuple[str, str, str]]:
    """채점 단위 키 → (세트, 문서 역할, 원본 경로 패턴). 키: 'S24'(시방서), 'S24-공고'(공고문)."""
    out = {}
    for sid, pat in SPECS.items():
        out[sid] = (sid, "SPEC", pat)
        if sid in NOTICES:
            out[sid + NOTICE_SUFFIX] = (sid, "NOTICE", NOTICES[sid])
    return out
SCOPE_PAGES = {"S26": (48, 57)}     # 정답 범위 (S26은 48~57쪽만 입력)


def answer_key(clause_no, item, attribute, operator) -> str:
    return "|".join([normalize_text(str(clause_no)), checks.squash(normalize_text(str(item))),
                     checks.squash(normalize_text(str(attribute))), normalize_text(str(operator))])


@dataclass
class Rule:
    row: int                     # 엑셀 행 번호
    clause_no: str
    item: str
    attribute: str
    operator: str
    value: str
    unit: str
    quote: str

    @property
    def key(self) -> str:
        return answer_key(self.clause_no, self.item, self.attribute, self.operator)

    @property
    def norm_value(self) -> tuple[str, str]:
        return checks.normalize_value(self.value), normalize_unit(self.unit)


@dataclass
class SetAnswers:
    set_id: str                  # 채점 단위 키 ('S24' 또는 'S24-공고')
    spec: Path                   # 원본 문서 (시방서 또는 공고문)
    role: str = "SPEC"           # SPEC · NOTICE
    rules: list[Rule] = field(default_factory=list)
    v4_rows: int = 0
    incomplete: list[int] = field(default_factory=list)     # item은 있는데 필수 칸이 빈 행
    bad_file: list[int] = field(default_factory=list)       # '파일' 칸이 그 세트의 시방서·공고문 이름이 아닌 행
    bad_operator: list[int] = field(default_factory=list)   # operator가 6개 밖인 행 (범위·포함 등)


def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def load(path: Path = DEFAULT_ANSWERS, rows: list[tuple] | None = None,
         require_source: bool = True) -> dict[str, SetAnswers]:
    """rows를 주면 엑셀 대신 그 값을 쓴다 (시험용). 각 행은 시트 머리글과 같은 순서.
    require_source=False면 원본 문서가 없어도 세트를 만든다 (spec은 경로 패턴. 채점만 하는 시험용)."""
    if rows is None:
        import openpyxl
        with warnings.catch_warnings():      # 드롭다운(x14) 미지원 경고. 읽기만 하므로 무시
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            rows = list(wb[SHEET].iter_rows(values_only=True))
            wb.close()
    head = [_s(h) for h in rows[0]]
    col = {h: i for i, h in enumerate(head)}
    out: dict[str, SetAnswers] = {}
    for key, (_, role, pat) in documents().items():
        found = sorted(COLLECT.glob(pat))
        if found or not require_source:
            out[key] = SetAnswers(key, found[0] if found else COLLECT / pat, role)
    for n, r in enumerate(rows[1:], 2):
        get = lambda h: _s(r[col[h]]) if col.get(h) is not None and col[h] < len(r) else ""  # noqa: E731
        sid = get("세트")
        if sid not in out or not get("item"):
            continue
        fname = get("파일")
        notice = out.get(sid + NOTICE_SUFFIX)
        if notice is not None and fname == notice.spec.name:
            sid = notice.set_id
        elif fname and fname != out[sid].spec.name:
            out[sid].bad_file.append(n)
            continue
        if get("출처").startswith("이미지 표"):
            out[sid].v4_rows += 1
            continue
        if not all(get(h) for h in ("clause_no", "attribute", "operator", "quote")):
            out[sid].incomplete.append(n)
            continue
        if get("operator") not in checks.OPERATORS:
            out[sid].bad_operator.append(n)
            continue
        out[sid].rules.append(Rule(n, get("clause_no"), get("item"), get("attribute"), get("operator"),
                                   get("value"), get("unit"), get("quote")))
    return out
