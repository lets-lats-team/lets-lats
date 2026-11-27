"""L2(내역서 항목 연결) 평가 실행기. 정답: 03_수집_3년/정답셋_후보의 정답 엑셀 (읽기 전용).

  python run_l2_eval.py --primary gt                                   # 자체 점검 (정답이 있는 항목 100% 맞아야 정상)
  python run_l2_eval.py --primary fake-wrong                           # 틀림을 잡는지 점검
  python run_l2_eval.py --primary gpt-6-luna --verifier claude-haiku-5-5   # 실제 (외부 전송 동의 후)

결과: results/l2_<시각>_<주담당>[_<확인>]/ — 세트별 정답 엑셀 형식 CSV 4종, report.md
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from l2_eval import answers as A  # noqa: E402
from l2_eval.callers import CALL_LOG, make_router  # noqa: E402
from l2_eval.score import export, rate, score_set  # noqa: E402
from worker.steps.s5_docs.l2.pipeline import run_l2  # noqa: E402
from worker.steps.s5_docs.l2.prompt import PROMPT_VERSION  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--primary", required=True, help="gt · fake-wrong · gpt-6-luna · claude-haiku-5-5")
    ap.add_argument("--verifier", default=None, help="교차 확인 모델 (AI 설계 5장: L2는 Luna 주담당, Haiku 확인)")
    ap.add_argument("--sets", default="S24,S25,S26")
    ap.add_argument("--answers", type=Path, default=A.DEFAULT_ANSWERS)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()

    real = [m for m in (args.primary, args.verifier) if m and m.startswith(("gpt-", "claude-"))]
    need = {"gpt-": "OPENAI_API_KEY", "claude-": "ANTHROPIC_API_KEY"}
    missing = sorted({k for m in real for p, k in need.items() if m.startswith(p) and not os.environ.get(k)})
    if missing:
        raise SystemExit(f"환경 변수 없음: {', '.join(missing)} (키는 코드·저장소에 넣지 않고 실행 시 주입)")
    ans = A.load(args.answers)
    call = make_router(ans)
    tag = "_".join(re.sub(r"[^A-Za-z0-9.-]", "_", m) for m in (args.primary, args.verifier) if m)
    run_dir = args.out / f"l2_{datetime.now():%Y%m%d-%H%M%S}_{tag}"
    lines = [f"# L2 평가 — 주담당 {args.primary}" + (f", 확인 {args.verifier}" if args.verifier else ""), "",
             f"- 프롬프트 {PROMPT_VERSION}, 정답 파일 `{args.answers.name}` (작성 중인 정답은 채운 항목만 채점)", "",
             "| 세트 | 시트 종류 | 수량 시트 여부 | 열 역할 | 행 분류 | 머리글 행 일치 | 품목 셀 값 일치 | 호출 |",
             "|---|---|---|---|---|---|---|---|"]
    wrongs = []
    rule_holds = []
    blocked = []
    for sid in [s.strip() for s in args.sets.split(",") if s.strip()]:
        if sid not in ans:
            lines.append(f"| {sid} | 정답 없음 | | | | | | |")
            continue
        sa = ans[sid]
        res = run_l2(sa.path, call, args.primary, args.verifier)
        export(sid, res, run_dir)
        sc = score_set(sa, res)
        hr = sc["header_rows"]
        lines.append(f"| {sid} | {rate(sc['sheets_kind'])} | {rate(sc['sheets_yn'])} | {rate(sc['columns'])} | "
                     f"{rate(sc['rows'])} | {hr['같음']}/{sum(hr.values())} | {sc['values']['같음']}/{sum(sc['values'].values())} | {len(res.calls)} |")
        wrongs += [f"{sid} {w}" for w in sc["wrong"]]
        held = {}
        for s in res.sheets:
            for it in [s.kind, *s.columns.values(), *s.rows.values()]:
                if it.status == "HELD":
                    held[it.hold_code] = held.get(it.hold_code, 0) + 1
        lines.append(f"|  ↳ 보류 코드 | {held or '없음'} | | | | | | |")
        for s in res.sheets:   # 수량 시트 규칙 보류 (결정 가): 오보류를 나중에 보고 규칙을 좁히기 위해 하나씩 남긴다
            if s.kind.rules:
                yn = sa.sheets.get(s.name, {}).get("yn") or "미작성"
                rule_holds.append((sid, s.name, s.kind.rules, s.kind.candidates, yn))
            if s.items_blocked:
                blocked.append(f"{sid} {s.name}: " + "; ".join(s.items_blocked))
    by_rule = {}
    for *_, rules, _, _ in rule_holds:
        for r in rules:
            by_rule[r] = by_rule.get(r, 0) + 1
    lines += ["", f"## 수량 시트 규칙 보류 {len(rule_holds)}건"
              + (" (" + ", ".join(f"{r} {n}" for r, n in sorted(by_rule.items())) + ", 한 시트에 둘 다 걸리면 각각 셈)" if by_rule else ""),
              "", "규칙① 시트 종류가 원가계산서·집계표·일위대가·단가대비표·표지인데 Y, 규칙② 시트 이름에 일위대가·단가대비·원가계산·집계가 있는데 Y. "
              "정답이 Y인 시트가 걸렸으면 오보류다.", ""]
    lines += [f"- {sid} {name}: {'·'.join(rules)} · 모델 후보 {cands} · 정답 수량 시트 {yn}"
              + (" ← **오보류**" if yn == "Y" else "") for sid, name, rules, cands, yn in rule_holds] or ["- 없음"]
    lines += ["", f"## 품목을 내보내지 않은 수량 시트 {len(blocked)}개 (품명·단위·수량 열 중 확정 후보가 아닌 것)", ""]
    lines += [f"- {b}" for b in blocked] or ["- 없음"]
    lines += ["", "## 틀린 PENDING·셀 값 불일치 (최대 50)", ""] + [f"- {w}" for w in wrongs[:50]] + ([] if wrongs else ["- 없음"])
    lines += ["", "정답이 없는 항목(미작성)은 채점하지 않는다. 그런 항목은 gt에서 '보류:AI_NO_RESPONSE'로 나온다."]
    run_dir.mkdir(parents=True, exist_ok=True)
    if CALL_LOG:   # 실제 모델 호출 기록 (원문 없음)
        price = {"gpt-6-luna": (0.10, 0.50), "claude-haiku-5-5": (0.10, 0.50)}   # AI 설계 4장, 100만 토큰당 USD
        with open(run_dir / "calls.csv", "w", encoding="utf-8-sig", newline="") as f:
            cw = csv.DictWriter(f, fieldnames=list(CALL_LOG[0]))
            cw.writeheader()
            cw.writerows(CALL_LOG)
        lines += ["", "## 실제 호출 (calls.csv)", "", "| 모델 | 호출 | 실패 | 입력 토큰 | 출력 토큰 | 추정 비용(USD) | 평균 초 | 최대 초 |", "|---|---|---|---|---|---|---|---|"]
        for m in sorted({c["model"] for c in CALL_LOG}):
            cs = [c for c in CALL_LOG if c["model"] == m]
            i, o = sum(c["in_tok"] for c in cs), sum(c["out_tok"] for c in cs)
            pi, po = price.get(m, (0, 0))
            cost = f"{(i * pi + o * po) / 1e6:.4f}" if m in price else "단가 미등록"
            secs = [c["sec"] for c in cs]
            lines.append(f"| {m} | {len(cs)} | {sum(1 for c in cs if c['error'])} | {i} | {o} | {cost} | "
                         f"{sum(secs) / len(secs):.1f} | {max(secs):.1f} |")
        errs = {}
        for c in CALL_LOG:
            if c["error"]:
                errs[(c["model"], c["error"])] = errs.get((c["model"], c["error"]), 0) + 1
        lines += [f"- 실패: {m} {e} × {n}" for (m, e), n in errs.items()] or ["- 실패 없음"]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n결과 폴더: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
