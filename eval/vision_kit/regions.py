"""시험 키트 v0.1의 판독 영역 (고려대 세종캠퍼스 행정관 DWG, 모델 공간 좌표 mm).

영역을 고른 근거는 eval/README.md의 '영역' 표를 본다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    key: str
    title: str
    # 정답 후보를 고르는 사각형 (삽입점 기준). 렌더 범위는 이 글자들의 상자로 정한다.
    x0: float
    y0: float
    x1: float
    y1: float
    # 같은 블록이 여러 번 삽입된 경우 등, 이 블록 경로로 시작하는 글자만 쓰고 싶을 때
    note: str = ""


REGIONS = [
    Region("legend", "기호표 (지하 1층 냉난방배관 평면도의 RGRLV 범례 블록)",
           383500, 503000, 392000, 513300,
           "AI 설계 3장 '기호표 30개'와 같은 블록. 관경 기호 A~I와 액관·가스관 관경"),
    Region("equipment", "장비일람표 (실외기 + 실내기 표)",
           464500, 566000, 496000, 580500,
           "AI 설계 3장 '장비일람표 239개'와 같은 범위"),
    Region("plan_3f", "3층 냉난방배관 평면도 일부",
           647000, 519260, 671000, 533260,
           "배관 기호(A~K)·장비 표기·실명이 섞인 영역. AI 설계의 '평면 29개'와 같은 영역인지는 기록이 없어 확인 불가"),
]

BY_KEY = {r.key: r for r in REGIONS}
