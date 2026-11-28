"""L2 프롬프트와 응답 스키마 (세 가지 작업, 두 모델 공통).

AI 설계 6.2: 모델은 열이 무엇인지, 행이 무엇인지 분류만 한다. 숫자는 코드가 원본 셀에서 가져온다.
스키마는 모든 필드 required, additionalProperties false (11.1).
"""
from .vocab import COL_ROLES, ROW_CLASSES, SHEET_KINDS, YN

PROMPT_VERSION = "L2.v4"

SYSTEM = (
    "당신은 한국 건설 공사의 공내역서(엑셀)를 정리하는 도우미입니다. "
    "주어진 셀 글자만 보고 분류합니다. 셀에 없는 내용을 지어내지 않습니다. "
    "숫자를 고치거나 계산하지 않습니다."
)

SHEETS_PROMPT = """아래는 한 내역서 엑셀 파일의 시트 목록과 각 시트 앞부분 셀입니다.
셀은 '행번호 | 열:값 ...' 형식입니다.

시트마다 두 가지를 답하세요.
1. sheet_kind: 원가계산서 · 집계표 · 내역서 · 일위대가 · 단가대비표 · 표지 · 기타 중 하나
2. is_qty_sheet: 이 공사에 실제로 들어가는 품목별 수량이 적힌 시트면 Y, 아니면 N
   - 일위대가(1단위 시공의 구성)와 단가대비표(단가 출처 목록)는 이 공사의 물량이 아니므로 N입니다.
   - 금액만 요약한 시트도 N입니다.

모든 시트에 한 줄씩, 시트 이름은 주어진 그대로 적으세요.

{sheets}"""

COLUMNS_PROMPT = """아래는 내역서 시트 '{sheet}'의 머리글과 앞부분 행입니다.
각 열의 머리글 글자는 '열: 머리글' 형식으로 주어집니다 (두 줄 머리글은 ' / '로 합쳤습니다).

열마다 역할을 하나 고르세요: 품명 · 규격 · 단위 · 수량 · 단가 · 금액 · 코드 · 비고 · 기타
- header_quote에는 그 열의 머리글 글자를 주어진 그대로 옮깁니다.
- 품명·단위·수량 열은 보통 하나씩입니다.
- '(숨김)' 표시는 엑셀에서 숨겨진 열입니다. 앞부분 행에는 보이는 열만 나오므로, 숨김 열은 머리글 옆에 '예:' 값 몇 개를 붙였습니다.
  숨김 열도 머리글과 예시 값을 보고 역할을 고르세요.
- header_quote에는 '(숨김)' 표시와 예시 값을 넣지 않습니다.
- 코드: 품목·공종을 식별하는 번호나 기호가 들어 있는 열 (예: 품목코드, 공종코드, 고유번호)
- 주어진 모든 열에 한 줄씩 답하세요.

머리글:
{header}

앞부분 행:
{rows}"""

ROWS_PROMPT = """아래는 내역서 시트 '{sheet}'의 행 묶음입니다. 열 역할은 다음과 같습니다: {col_roles}
행은 '행번호 | 열:값 ...' 형식입니다.

행마다 분류를 하나 고르세요: 공종 제목 · 품목 · 소계 · 합계 · 빈 행 · 기타
- 공종 제목: 아래 품목들을 묶는 제목 행 (예: "1. 장비", "010102 냉매배관공사")
- 품목: 품명이 있고 이 공사에 들어가는 자재·장비·작업 한 가지 (수량 칸이 비어도 품목)
- 소계: 셀 글자가 "소계"·"계"인 합계 행
- 합계: 셀 글자가 "합계"·"총계"인 행 (공종 하나의 합이어도 글자가 "합계"면 합계)
- 빈 행: 의미 있는 글자가 없는 행
- 기타: 그 밖 (두 번째 머리글 줄, 주석 등)

주어진 모든 행 번호에 한 줄씩 답하세요.

{rows}"""


def _strict(obj_props: dict) -> dict:
    return {"type": "object", "properties": obj_props, "required": list(obj_props), "additionalProperties": False}


SHEETS_SCHEMA = _strict({
    "task": {"type": "string", "enum": ["BOQ_SHEETS"]},
    "sheets": {"type": "array", "items": _strict({
        "sheet": {"type": "string"},
        "sheet_kind": {"type": "string", "enum": SHEET_KINDS},
        "is_qty_sheet": {"type": "string", "enum": YN},
    })},
})

COLUMNS_SCHEMA = _strict({
    "task": {"type": "string", "enum": ["BOQ_COLUMNS"]},
    "columns": {"type": "array", "items": _strict({
        "col": {"type": "string"},
        "role": {"type": "string", "enum": COL_ROLES},
        "header_quote": {"type": "string"},
    })},
})

ROWS_SCHEMA = _strict({
    "task": {"type": "string", "enum": ["BOQ_ROWS"]},
    "rows": {"type": "array", "items": _strict({
        "row": {"type": "integer"},
        "class": {"type": "string", "enum": ROW_CLASSES},
    })},
})

SCHEMAS = {"BOQ_SHEETS": SHEETS_SCHEMA, "BOQ_COLUMNS": COLUMNS_SCHEMA, "BOQ_ROWS": ROWS_SCHEMA}
