"""L2 정답 읽기 (03_수집_3년/정답셋_후보의 정답 엑셀, 읽기 전용).

정답 엑셀은 사람이 작성 중인 파일이다. 이 코드는 절대 쓰지 않는다.
정답 칸이 빈 항목은 '미작성'으로 보고 채점에서 뺀다.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path

# 원본·정답 자료 폴더 (03_수집_3년이 있는 곳). 저장소에는 없다. 환경 변수 LETS_DATA_ROOT, 없으면 lets-lats의 상위 폴더
PROJECT = Path(os.environ.get("LETS_DATA_ROOT") or Path(__file__).resolve().parents[3])
COLLECT = PROJECT / "03_수집_3년"
DEFAULT_ANSWERS = COLLECT / "정답셋_후보" / "정답_입력완.xlsx"

# 세트 → (구간 폴더, 공고번호). 출처: 정답셋_후보/L2L3_후보_선정.md
SETS = {"S24": ("2024", "20240120529"), "S25": ("2025", "R25BK01074925"), "S26": ("2026", "R26BK01716759")}


@dataclass
class SetAnswers:
    set_id: str
    file: str
    path: Path
    sheets: dict[str, dict] = field(default_factory=dict)            # 시트 → {"yn", "kind", "rows"}
    columns: dict[tuple[str, str], dict] = field(default_factory=dict)  # (시트, 열) → {"role", "header_rows", "header_text"}
    rows: dict[tuple[str, int], dict] = field(default_factory=dict)     # (시트, 행) → {"cls", "name", "spec", "unit", "qty"}


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def boq_path(set_id: str, file: str) -> Path:
    yr, notice = SETS[set_id]
    hits = list((COLLECT / yr).glob(f"{notice}_*"))
    if not hits:
        raise FileNotFoundError(f"{set_id}: 공사 폴더 없음 ({yr}/{notice}_*)")
    p = hits[0] / "02_내역서" / file
    if not p.exists():
        raise FileNotFoundError(p)
    return p


def load(path: Path = DEFAULT_ANSWERS) -> dict[str, SetAnswers]:
    import openpyxl
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # 드롭다운(데이터 유효성) 확장 경고
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out: dict[str, SetAnswers] = {}

    def table(name):
        rows = list(wb[name].iter_rows(values_only=True))
        hdr = [_s(h) for h in rows[0]]
        return [dict(zip(hdr, r)) for r in rows[1:] if any(v not in (None, "") for v in r)]

    def get_set(sid, file):
        if sid not in out:
            out[sid] = SetAnswers(sid, file, boq_path(sid, file))
        return out[sid]

    for r in table("L2_시트구분"):
        sa = get_set(_s(r["세트"]), _s(r["파일"]))
        sa.sheets[_s(r["시트"])] = {"yn": _s(r["수량 시트 여부"]), "kind": _s(r["시트 종류"]), "rows": r.get("시트 행 수")}
    for r in table("L2_열대응"):
        sa = get_set(_s(r["세트"]), _s(r["파일"]))
        sa.columns[(_s(r["시트"]), _s(r["열"]).upper())] = {
            "role": _s(r["정답 역할"]), "header_rows": _s(r["머리글 행"]), "header_text": _s(r["머리글 원문"])}
    for r in table("L2_행분류"):
        sa = get_set(_s(r["세트"]), _s(r["파일"]))
        sa.rows[(_s(r["시트"]), int(_s(r["행 번호"])))] = {
            "cls": _s(r["정답 분류"]), "name": _s(r["품명 원문"]), "spec": _s(r["규격 원문"]),
            "unit": _s(r["단위 원문"]), "qty": _s(r["수량 원문"])}
    wb.close()
    return out
