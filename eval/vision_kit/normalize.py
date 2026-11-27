"""비교 전 정규화 (AI 설계 7장: 공백 제거, Ø·φ·ø 통일, 전각 변환, 단위 표기 통일)."""
import re
import unicodedata

_DIAMETER = str.maketrans({"φ": "Ø", "Φ": "Ø", "ø": "Ø", "⌀": "Ø", "∅": "Ø"})
_WS = re.compile(r"\s+")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)  # 전각→반각, ㎟→mm2, ²→2
    s = s.translate(_DIAMETER)
    s = _WS.sub("", s)
    return s


def has_digit(s: str) -> bool:
    return any(ch.isdigit() for ch in s)
