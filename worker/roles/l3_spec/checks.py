"""L3 역할 검사 (AI 설계 8장 G2·G3, 11.4 'L3 적용 예'). 판정은 코드가 한다.

G2 인용문 대조 (2026-11-25 김선진 결정)
  두 글 모두 g2_norm(공통 정규화 → NFKC → 물결 통일 → 표 칸 구분자 '|' 제거 → 공백 전부 제거) 뒤,
  모델이 든 clause_no 조항(하위 조항 포함) 원문 안에 quote가 들어 있으면 통과.
  숫자 조건이면 value의 숫자가 모두 quote 안에도 있어야 통과. 아니면 AI_NO_EVIDENCE.
  글자 값(공사 방식 코드 제외)이면 value 글자가 quote 안에 그대로 있어야 통과 (2026-11-26 Codex 3-1: KSC9306→KSC0417 같은
  바꿔치기가 통과하던 것). 영숫자로 끝나는 글자 값은 quote에서 앞뒤가 다른 영숫자와 이어지면 안 된다 (회귀 R-01: KSC930).
  숫자는 수 값으로 비교한다 (3.80 = 3.8, 회귀 R-06).
  공사 방식 행은 코드에 맞는 근거 말이 quote에 있어야 통과 (회귀 R-04·R-05):
    REUSE_PIPE 재사용·재활용·"기존 … 사용" / REPLACE_AFTER_DEMO 철거·교체·재시공 / REUSE_ROUTE 경로 / NEW_ROUTE 경로·신설·신규
    드레인·배관커버만 다시 쓰는 문장을 냉매 배관으로 착각하는 것은 막지 못한다 (교차 확인 G5와 담당자 확정 A03의 몫).
  NFKC는 양쪽에 똑같이 적용하므로(㎜→mm, ～→~, ①→1) 포함 여부 판정에만 쓰고 저장 값에는 쓰지 않는다.
G3 값 범위
  value가 숫자인데 unit이 단위 목록에 없으면 AI_OUT_OF_DOMAIN.
  value 전체가 "숫자 구분자 숫자[단위]"(1.5~2, 1.5-2, 1.5—2, 1.5−2, 1.5 내지 2, 1/50-1/100)면 AI_OUT_OF_DOMAIN
  (연산자 6개: 범위는 >=·<= 두 규칙. Codex 3-2, 회귀 R-03). 'KS D 5301-2' 같은 규격 표기와 음수 -10은 범위가 아니다.
  value에 숫자와 단위·관경 기호를 붙여 쓰면(30A, 30A이상, 1.5m, 50mm 이상, -10℃, 30inch, 3대, Ø6.35) AI_OUT_OF_DOMAIN
  (Codex 3-1, 회귀 R-02. 숫자 검사를 건너뛰게 됨). 2인 1조·1식·R410A·300*150*1500은 붙여 쓰기가 아니다.
  value가 비면 AI_OUT_OF_DOMAIN (회귀 R-10).
  unit이 비어도 되는 경우: 비율·기울기 값(1/50~1/100처럼 '/'가 있음). 설계서는 '비었으면 보류'라서 이 예외는 설계 밖 (README에 기록).
G3 공사 방식 (2026-11-25 김선진 결정: 설계서 형식대로 — 행 7칸 그대로, value에 R01 4종 코드)
  attribute가 '공사 방식'인 행: operator '=', value는 PIPING_MODES 중 하나, unit 빈칸이어야 한다.
  4종 코드를 다른 attribute에 쓴 행도 AI_OUT_OF_DOMAIN. item은 '냉매 배관'(공백 무시)이어야 한다 (2026-11-26 Codex 3-3).
"""
from __future__ import annotations

import re
import unicodedata

from ..contract import normalize_text, normalize_unit

# 설계 11.4 단위 목록(가정): mm, m, kg, kW, HP, W, A, V, Pa, kPa, MPa, ℃, %
# 2026-11-25 추가 (S24~S26 원문에 실제로 나온 단위, 설계서 '시험 뒤 늘린다'에 따름. README에 기록):
#   cm · m²(㎡) · T(보온 두께 25T) · kgf/cm²(10㎏/㎠) · mAq · mmHg · 개수(대·개·개소·선·통·EA) · 횟수·배수(회·배)
#   · 시간(년·개월·일·시간·분·초·min). A는 관경 호칭(30A)과 전류가 같은 글자다
UNITS = {"mm", "cm", "m", "m²", "kg", "kW", "HP", "W", "A", "V", "Pa", "kPa", "MPa", "℃", "%",
         "T", "kgf/cm²", "mAq", "mmHg",
         "대", "개", "개소", "선", "통", "EA", "회", "배", "년", "개월", "일", "시간", "분", "초", "min",
         "Hz"}   # Hz: 2026-11-26 추가 (S26 전원 주파수 60 Hz)
# 2026-11-26 김선진 결정: 설계서 11.4대로 6개 (11-25의 10개 — 범위·포함·금지·기타 — 를 되돌림)
OPERATORS = ["=", "!=", ">=", "<=", ">", "<"]

# 기능 명세 R01 · DB 설계 analysis.input_json.pipingMode. L3 행은 A03 제안값 후보일 뿐 (G7: 확정은 담당자)
PIPING_MODES = ("NEW_ROUTE", "REUSE_ROUTE", "REPLACE_AFTER_DEMO", "REUSE_PIPE")
METHOD_ITEM = "냉매 배관"
METHOD_ATTRIBUTE = "공사 방식"

_TILDE = str.maketrans({"∼": "~", "〜": "~", "～": "~", "˜": "~"})
_WS = re.compile(r"\s+")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_NUMERIC_VALUE = re.compile(r"^[\d.,/~\-\s]+$")
_UNIT_CH = "A-Za-z%°℃㎜㎝㎡㎏㎾㎫㎪㎩㎠Ω²³"
_NUMTOK = r"[-−]?\d[\d.,]*(?:/\d[\d.,]*)?"
_RANGE = re.compile(rf"^\s*{_NUMTOK}\s*(?:~|-|–|—|−|내지)\s*{_NUMTOK}\s*(?:[{_UNIT_CH}][{_UNIT_CH}/\d]*)?\s*$")
_GLUED = re.compile(r"^[-−]?[\d.,/]+\s*(?P<unit>[^\d\s.,/]\S*?)\s*(?:이상|이하|초과|미만)?$")
_UNIT_TOKEN = re.compile(rf"[{_UNIT_CH}][{_UNIT_CH}/\d]*")
_METHOD_EVIDENCE = {
    "REUSE_PIPE": ("재사용·재활용·기존 … 사용", re.compile(r"재사용|재활용|기존[^.。]*사용")),
    "REPLACE_AFTER_DEMO": ("철거·교체·재시공", re.compile(r"철거|교체|재시공")),
    "REUSE_ROUTE": ("경로", re.compile(r"경로")),
    "NEW_ROUTE": ("경로·신설·신규", re.compile(r"경로|신설|신규")),
}


def squash(s: str) -> str:
    return _WS.sub("", s or "")


def g2_norm(s: str) -> str:
    """인용문 포함 판정용 정규화. 공백·줄바꿈 차이, 전각, ㎜·mm, ～·~ 차이를 없앤다."""
    t = unicodedata.normalize("NFKC", normalize_text(s)).translate(_TILDE).replace("|", "")
    return squash(t)


def numbers(s: str) -> list[str]:
    """글 속 숫자들. 천 단위 쉼표는 지운다 (1,500 → 1500)."""
    return _NUM.findall(re.sub(r"(?<=\d),(?=\d{3})", "", g2_norm(s)))


def _num(n: str) -> float:
    return float(n)


def _in_quote(value: str, q: str) -> bool:
    """g2_norm 된 value가 q 안에 있고, 영숫자 끝은 다른 영숫자와 이어지지 않는가 (KSC930 ⊂ KSC9306 막기)."""
    v = g2_norm(value)
    alnum = lambda c: c.isascii() and c.isalnum()  # noqa: E731
    i = q.find(v)
    while i >= 0:
        before, after = q[i - 1] if i else "", q[i + len(v)] if i + len(v) < len(q) else ""
        if not (alnum(v[0]) and before and alnum(before)) and not (alnum(v[-1]) and after and alnum(after)):
            return True
        i = q.find(v, i + 1)
    return False


def is_numeric_value(v: str) -> bool:
    v = normalize_text(v).translate(_TILDE)
    return bool(v) and any(ch.isdigit() for ch in v) and bool(_NUMERIC_VALUE.match(v))


def normalize_value(v: str) -> str:
    """저장·비교용 value. 공통 정규화 + 물결 통일. 숫자 값은 공백을 모두 뺀다 (1.5 ~ 2 → 1.5~2)."""
    t = normalize_text(v).translate(_TILDE)
    return squash(t) if is_numeric_value(t) else t


def check_quote(quote: str, source: str, value: str, attribute: str = "") -> str | None:
    """G2. 문제 없으면 None, 있으면 사유 (보류 코드는 AI_NO_EVIDENCE)."""
    q = g2_norm(quote)
    if not q:
        return "인용문 없음"
    if q not in g2_norm(source):
        return "인용문이 조항 원문에 없음"
    if is_method(attribute):
        code = normalize_method_value(value)
        if code in _METHOD_EVIDENCE:
            words, rx = _METHOD_EVIDENCE[code]
            if not rx.search(q):
                return f"공사 방식 {code}의 근거 말({words})이 인용문에 없음"
    elif is_numeric_value(value):
        have = {_num(n) for n in numbers(quote)}
        missing = [n for n in numbers(value) if _num(n) not in have]
        if missing:
            return f"value 숫자 {missing}가 인용문에 없음"
    elif g2_norm(value) and not _in_quote(value, q):
        return f"글자 값 '{value}'가 인용문에 그대로 없음"
    return None


def is_method(attribute: str) -> bool:
    return squash(normalize_text(attribute)) == squash(METHOD_ATTRIBUTE)


def normalize_method_value(v: str) -> str:
    """공사 방식 코드: 대문자, 공백·하이픈은 밑줄 (reuse pipe → REUSE_PIPE)."""
    return re.sub(r"[\s\-]+", "_", normalize_text(v)).upper()


def check_method(attribute: str, operator: str, value: str, unit: str, item: str = METHOD_ITEM) -> str | None:
    """G3 공사 방식 행 형식. 문제 없으면 None, 있으면 사유 (보류 코드는 AI_OUT_OF_DOMAIN)."""
    code = normalize_method_value(value)
    if not is_method(attribute):
        return f"공사 방식 코드 '{code}'는 attribute '{METHOD_ATTRIBUTE}'에만 쓴다" if code in PIPING_MODES else None
    if squash(normalize_text(item)) != squash(METHOD_ITEM):
        return f"공사 방식 item은 '{METHOD_ITEM}'만 (받은 값 '{item}')"
    if code not in PIPING_MODES:
        return f"공사 방식 값 '{value}'가 4종 코드({', '.join(PIPING_MODES)})가 아님"
    if normalize_text(operator) != "=":
        return f"공사 방식 operator는 '='만 (받은 값 '{operator}')"
    if normalize_unit(unit):
        return f"공사 방식에는 단위가 없다 (받은 값 '{unit}')"
    return None


def check_range(value: str) -> str | None:
    """G3. 범위 값(1.5~2, 1.5-2, 1.5 내지 2)은 한 규칙에 담지 않는다. 문제 없으면 None (보류 코드는 AI_OUT_OF_DOMAIN)."""
    if _RANGE.match(normalize_text(value).translate(_TILDE)):
        return f"범위 값 '{value}'는 >=·<= 두 규칙으로 나눠야 함"
    return None


def check_empty(value: str) -> str | None:
    """G3. 값 없는 후보는 대조에 쓸 수 없다 (보류 코드는 AI_OUT_OF_DOMAIN)."""
    return None if normalize_text(value) else "value가 비어 있음"


def check_glued(value: str) -> str | None:
    """G3. 숫자와 단위·관경 기호를 value에 붙여 쓰면 숫자 검사를 건너뛰므로 보류 (보류 코드는 AI_OUT_OF_DOMAIN)."""
    t = normalize_text(value).translate(_TILDE)
    if is_numeric_value(t):
        return None
    glued = bool(re.match(r"^Ø\s*\d", t))
    if not glued and (m := _GLUED.match(t)):
        unit = m.group("unit")
        glued = bool(_UNIT_TOKEN.fullmatch(unit)) or normalize_unit(unit) in UNITS
    return f"value '{value}'에 숫자와 단위·기호를 붙여 씀 (숫자는 value, 단위는 unit에)" if glued else None


def check_unit(value: str, unit: str) -> str | None:
    """G3. 문제 없으면 None, 있으면 사유 (보류 코드는 AI_OUT_OF_DOMAIN)."""
    if not is_numeric_value(value):
        return None
    u = normalize_unit(unit)
    if not u:
        return None if "/" in value else "숫자 값인데 단위 없음"
    return None if u in UNITS else f"단위 '{unit}'가 단위 목록에 없음"
