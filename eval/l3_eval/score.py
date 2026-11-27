"""L3 결과를 정답과 맞대 채점하고 CSV로 내보낸다.

판정 (AIResult 하나 = 조건 후보 하나, pair_key로 정답과 짝지음)
- 맞음          : PENDING이고 정답 value·unit과 같음 (정규화 뒤)
- 틀린 PENDING  : PENDING인데 value 또는 unit이 다름  ← 가장 중요한 지표 (AI 설계 14.2)
- 보류:<코드>   : HELD
- 정답에 없음   : 정답 키가 없는 후보. PENDING이면 '검토 필요' (정답 미입력일 수도 있어 틀림으로 세지 않음)
                  S26은 정답 범위(48~57쪽) 밖 조항이면 '범위 밖'으로 따로 센다
- 놓침          : 정답은 있는데 결과가 없음
같은 pair_key 결과가 여러 개(긴 조항이 여러 묶음에 걸침)면 한 번만 센다: PENDING 중 틀린 값이 있으면 틀린 PENDING,
  아니면 맞음, 모두 HELD면 첫 보류 코드. 나머지는 '중복 결과'로 따로 센다 (2026-11-26 Codex 4-1)
같은 키 정답이 여러 줄이면 그중 하나와 같으면 맞음 (덮어쓰지 않음, dup_rows로 보고. Codex 5-1)
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from worker.roles.contract import normalize_text
from worker.roles.l3_spec import checks

from .answers import SCOPE_PAGES, SetAnswers, answer_key


def _in_scope(sid: str, pages: list[int]) -> bool:
    if sid not in SCOPE_PAGES:
        return True
    lo, hi = SCOPE_PAGES[sid]
    return bool(pages) and any(lo <= p <= hi for p in pages)


def score_set(sa: SetAnswers, tasks, results, primary: str) -> dict:
    pages = {}
    canon = {}                       # 공백 뺀 clause_no → 조항 목록의 정식 clause_no
    for t in tasks:
        pages.update(t.private["pages"])
        canon.update({checks.squash(no): no for no in t.private["clauses"]})
    answers: dict[str, list] = {}
    dup_keys, bad_clause = [], []
    for r in sa.rules:
        no = canon.get(checks.squash(normalize_text(r.clause_no)))
        if no is None:
            bad_clause.append(r.row)
        key = answer_key(no or r.clause_no, r.item, r.attribute, r.operator)
        if key in answers:
            dup_keys.append(r.row)
        answers.setdefault(key, []).append(r)

    def judge(res, v, alts):
        if res.status == "HELD":
            return f"보류:{res.hold_code}", alts[0]
        for a in alts:
            if (v.get("value"), v.get("unit")) == a.norm_value:
                return "맞음", a
        return "틀린 PENDING", alts[0]

    # 결과마다 먼저 판정하고, 같은 pair_key 안에서 대표 하나를 고른다 (2026-11-26 회귀 R-08·R-09)
    # 순위: 틀린 PENDING < 맞음·정답에 없는 PENDING·범위 밖(PENDING) < 보류. 같은 순위면 먼저 나온 결과
    per = []
    for res in results:
        cand = res.candidates.get(primary) or next(iter(res.candidates.values()), None)
        v = cand.value if cand else {}
        alts = answers.get(res.pair_key) if res.pair_key else None
        clause = res.pair_key.split("|")[0] if res.pair_key else ""
        if alts:
            j, ans = judge(res, v, alts)
        elif not _in_scope(sa.set_id, pages.get(clause, [])):
            j, ans = "범위 밖", None
        elif res.status == "PENDING":
            j, ans = "정답에 없는 PENDING", None
        else:
            j, ans = f"정답에 없는 보류:{res.hold_code}", None
        rank = 0 if j == "틀린 PENDING" else (1 if res.status == "PENDING" else 2)
        per.append((res, cand, v, j, ans, rank))
    rep: dict[str, int] = {}
    for i, (res, *_rest, rank) in enumerate(per):
        if res.pair_key and (res.pair_key not in rep or rank < per[rep[res.pair_key]][5]):
            rep[res.pair_key] = i

    c = Counter()
    rows, wrong, seen = [], [], set()
    for i, (res, cand, v, j, ans, _rank) in enumerate(per):
        if ans is not None:
            seen.add(res.pair_key)
        if res.pair_key and rep[res.pair_key] != i:
            j = f"중복 결과({j})"
        elif j == "틀린 PENDING":
            wrong.append(f"{sa.set_id} {res.pair_key}: 모델 {v.get('value')} {v.get('unit')} / 정답 "
                         + " 또는 ".join(f"{a.value} {a.unit}" for a in answers[res.pair_key])
                         + f" (정답 {ans.row}행, {res.target_key})")
        c["중복 결과" if j.startswith("중복 결과") else j] += 1
        rows.append({"세트": sa.set_id, "target_key": res.target_key, "pair_key": res.pair_key or "",
                     "상태": res.status, "hold_code": res.hold_code or "", "agreed": res.agreed, "판정": j,
                     "value": v.get("value", ""), "unit": v.get("unit", ""),
                     "정답 value": ans.value if ans else "", "정답 unit": ans.unit if ans else "",
                     "정답 행": ans.row if ans else "",
                     "quote": cand.evidence[0].quote if cand else "",
                     "모델별 후보": {m: {**x.value, "hold": x.hold_code, "note": x.note} for m, x in res.candidates.items()}})
    missed = [(k, rs[0]) for k, rs in answers.items() if k not in seen]
    c["놓침"] = len(missed)
    wrong += [f"{sa.set_id} 놓침: {k} (정답 {r.row}행)" for k, r in missed]
    return {"counter": c, "rows": rows, "wrong": wrong, "answers": len(answers), "dup_rows": dup_keys,
            "bad_clause_rows": bad_clause}


def export(out_dir: Path, set_id: str, rows: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = ["세트", "target_key", "pair_key", "상태", "hold_code", "agreed", "판정", "value", "unit",
              "정답 value", "정답 unit", "정답 행", "quote", "모델별 후보"]
    with open(out_dir / f"{set_id}_L3_조건.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
