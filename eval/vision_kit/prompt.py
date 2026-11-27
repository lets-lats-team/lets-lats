"""모델에 보내는 지시문과 응답 스키마 (두 모델 공통).

AI 설계 6.1: 표준 관경 목록·장비일람표 값 같은 '답'은 주지 않는다.
모델이 매긴 신뢰도는 받지 않는다.
"""

PROMPT_VERSION = "region_text.v1"

PROMPT = """이 이미지는 냉난방 설비 도면(CAD)의 일부를 흑백으로 그린 것입니다.
이미지에 보이는 글자를 모두 읽어 주세요.

규칙:
- 도면에서 따로 떨어져 있는 글자 덩어리 하나(한 줄)를 readings의 항목 하나로 적습니다.
- 보이는 그대로 적습니다. 맞춤법을 고치거나, 단위를 붙이거나, 빠진 글자를 추측해 채우지 않습니다.
- 표 안의 글자는 칸마다 따로 적습니다.
- 이미지 가장자리에서 잘려 일부만 보이는 글자는 적지 않습니다.
- 글자를 하나도 읽을 수 없으면 status를 UNREADABLE로, readings는 빈 목록으로 둡니다."""

SCHEMA = {
    "type": "object",
    "properties": {
        "task": {"type": "string", "enum": ["REGION_TEXT"]},
        "status": {"type": "string", "enum": ["READ", "UNREADABLE"]},
        "readings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"raw_text": {"type": "string"}},
                "required": ["raw_text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["task", "status", "readings"],
    "additionalProperties": False,
}
