"""L3(시방서·공고문 조건 추출) 평가 실행기. 정답: 03_수집_3년/정답셋_후보/정답_입력완.xlsx 'L3_조건' (읽기 전용).
세트마다 시방서('S24')와 공고문('S24-공고')을 따로 돌리고 따로 채점한다 (정답 행은 '파일' 칸으로 나뉜다).

  python -X utf8 eval/run_l3_eval.py --primary gt                         # 자체 점검: 정답이 전부 '맞음'이어야 정상
  python -X utf8 eval/run_l3_eval.py --primary fake-wrong                 # 틀림을 잡는지
  python -X utf8 eval/run_l3_eval.py --primary gt --verifier fake-wrong   # 교차 확인: 틀린 PENDING 0
  # 실제 (동의·키 주입 후): --primary claude-haiku-5-5 --verifier gpt-6-luna   (AI 설계 5장: L3 Haiku 주담당, Luna 확인)

결과: results/l3_<시각>_<주담당>[_<확인>]/ — 세트별 <세트>_L3_조건.csv, report.md, calls.csv(실제 호출 시)
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from l3_eval import answers as A  # noqa: E402
from l3_eval.callers import CALL_LOG, FAILED_RAW, make_router  # noqa: E402
from l3_eval.score import export, score_set  # noqa: E402
from worker.roles.contract import DocumentRef, RoleInputError, RoleLimits  # noqa: E402
from worker.roles.l3_spec.module import MODULE  # noqa: E402
from worker.roles.testing import FakeContext, run_document  # noqa: E402

PRICE = {"gpt-6-luna": (0.10, 0.50), "claude-haiku-5-5": (0.10, 0.50)}   # AI 설계 2장, 100만 토큰당 USD


def run(args, answers=None) -> Path:
    real = [m for m in (args.primary, args.verifier) if m and m.startswith(("gpt-", "claude-"))]
    need = {"gpt-": "OPENAI_API_KEY", "claude-": "ANTHROPIC_API_KEY"}
    missing = sorted({k for m in real for p, k in need.items() if m.startswith(p) and not os.environ.get(k)})
    if missing:
        raise SystemExit(f"환경 변수 없음: {', '.join(missing)} (키는 코드·저장소에 넣지 않고 실행 시 주입)")
    ans = answers if answers is not None else A.load(args.answers)
    docs = {sid: DocumentRef(id=uuid5(NAMESPACE_URL, f"l3-eval/{sid}"), role=sa.role, file_name=sa.spec.name,
                             extension=sa.spec.suffix.lstrip(".")) for sid, sa in ans.items()}
    doc_sets = {str(d.id): sid for sid, d in docs.items()}
    call = make_router(ans, doc_sets)
    ctx = FakeContext(paths={d.id: ans[sid].spec for sid, d in docs.items()},
                      role_limits=RoleLimits(chunk_tokens=args.chunk_tokens, max_tokens=4096, timeout_s=40))
    tag = "_".join(re.sub(r"[^A-Za-z0-9.-]", "_", m) for m in (args.primary, args.verifier) if m)
    run_dir = args.out / f"l3_{datetime.now():%Y%m%d-%H%M%S}_{tag}"
    lines = [f"# L3 평가 — 주담당 {args.primary}" + (f", 확인 {args.verifier}" if args.verifier else ""), "",
             f"- 프롬프트 {MODULE.prompt_version}, 묶음 {args.chunk_tokens:,}토큰(글자 수 기준 가짜 토큰), "
             f"정답 파일 `{Path(args.answers).name}` 시트 `{A.SHEET}`", "",
             "| 세트 | 정답 | 맞음 | 틀린 PENDING | 보류 | 놓침 | 정답에 없는 PENDING | 범위 밖 | 작업 | 호출 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    wrongs, notes = [], []
    keys = []
    for s in [s.strip() for s in args.sets.split(",") if s.strip()]:
        keys += [s] if s.endswith(A.NOTICE_SUFFIX) else [s, s + A.NOTICE_SUFFIX]
    for sid in keys:
        if sid not in ans:
            if sid.endswith(A.NOTICE_SUFFIX):
                continue
            lines.append(f"| {sid} | 원본 없음 | | | | | | | | |")
            continue
        sa = ans[sid]
        n_calls = len(CALL_LOG)
        try:
            tasks, results = run_document(MODULE, ctx, docs[sid], call, args.primary, args.verifier)
        except RoleInputError as e:
            lines.append(f"| {sid} | 읽기 실패 {e.code} | | | | | | | | |")
            continue
        sc = score_set(sa, tasks, results, args.primary)
        export(run_dir, sid, sc["rows"])
        c = sc["counter"]
        held = {k.split(":", 1)[1]: v for k, v in c.items() if k.startswith("보류:")}
        lines.append(f"| {sid} | {sc['answers']} | {c['맞음']} | {c['틀린 PENDING']} | {sum(held.values())} {held or ''} | "
                     f"{c['놓침']} | {c['정답에 없는 PENDING']} | {c['범위 밖']} | {len(tasks)} | "
                     f"{len(CALL_LOG) - n_calls if real else len(tasks) * (2 if args.verifier else 1)} |")
        wrongs += sc["wrong"]
        if sc["bad_clause_rows"]:
            notes.append(f"{sid}: clause_no가 조항 목록에 없는 정답 행 {sc['bad_clause_rows']} (조항목록 CSV 값과 다름)")
        if c["중복 결과"]:
            notes.append(f"{sid}: 같은 pair_key 결과가 여러 묶음에서 나와 한 번만 센 것 {c['중복 결과']}건 (CSV 판정 '중복 결과')")
        if sc["dup_rows"]:
            notes.append(f"{sid}: 같은 키(clause_no·item·attribute·operator)가 겹치는 정답 행 {sc['dup_rows']}")
        if sa.incomplete:
            notes.append(f"{sid}: item은 있는데 필수 칸(clause_no·attribute·operator·quote)이 빈 정답 행 {sa.incomplete}")
        if sa.bad_operator:
            notes.append(f"{sid}: operator가 6개(=, !=, >=, <=, >, <) 밖이라 채점에서 뺀 정답 행 {sa.bad_operator}")
        if sa.bad_file:
            notes.append(f"{sid}: '파일' 칸이 이 세트의 시방서·공고문 이름이 아닌 정답 행 {sa.bad_file}")
        if sa.v4_rows:
            notes.append(f"{sid}: 출처 '이미지 표(V4)' 정답 {sa.v4_rows}줄은 L3 채점에서 뺌")
    lines += ["", "## 틀린 PENDING·놓침 (최대 50)", ""] + [f"- {w}" for w in wrongs[:50]] + ([] if wrongs else ["- 없음"])
    lines += ["", "## 정답 입력 점검", ""] + [f"- {n}" for n in notes] + ([] if notes else ["- 문제 없음"])
    lines += ["", "'정답에 없는 PENDING'은 틀림으로 세지 않는다 (정답 미입력 조건일 수 있음). 결과 CSV에서 검토한다."]
    run_dir.mkdir(parents=True, exist_ok=True)
    if CALL_LOG:
        with open(run_dir / "calls.csv", "w", encoding="utf-8-sig", newline="") as f:
            cw = csv.DictWriter(f, fieldnames=list(CALL_LOG[0]))
            cw.writeheader()
            cw.writerows(CALL_LOG)
        lines += ["", "## 실제 호출 (calls.csv)", "", "| 모델 | 호출 | 실패 | 입력 토큰 | 출력 토큰 | 추정 비용(USD) | 평균 초 | 최대 초 |",
                  "|---|---|---|---|---|---|---|---|"]
        for m in sorted({x["model"] for x in CALL_LOG}):
            cs = [x for x in CALL_LOG if x["model"] == m]
            i, o = sum(x["in_tok"] for x in cs), sum(x["out_tok"] for x in cs)
            pi, po = PRICE.get(m, (0, 0))
            secs = [x["sec"] for x in cs]
            lines.append(f"| {m} | {len(cs)} | {sum(1 for x in cs if x['error'])} | {i} | {o} | "
                         f"{(i * pi + o * po) / 1e6:.4f} | {sum(secs) / len(secs):.1f} | {max(secs):.1f} |")
    if FAILED_RAW:
        # 끊김·해석 실패 호출의 원래 응답 (2026-11-26: Haiku thinking이 출력 한도를 먹던 것을 이걸로 찾음)
        fdir = run_dir / "failed_raw"
        fdir.mkdir(exist_ok=True)
        for k, x in enumerate(FAILED_RAW):
            name = f"{k:02d}_{re.sub(r'[^A-Za-z0-9.-]', '_', x['model'])}_{x['target_key'].rsplit(':', 1)[-1]}.txt"
            (fdir / name).write_text(f"target_key: {x['target_key']}\nmodel: {x['model']}\nerror: {x['error']}\n"
                                     f"in_tok: {x['in_tok']} out_tok: {x['out_tok']} 보이는 글자: {len(x['raw'])}\n\n"
                                     + x["raw"], encoding="utf-8")
        lines += ["", f"실패 호출 {len(FAILED_RAW)}건의 원래 응답: `failed_raw/`"]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n결과 폴더: {run_dir}")
    return run_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--primary", required=True, help="gt · fake-wrong · claude-haiku-5-5 · gpt-6-luna")
    ap.add_argument("--verifier", default=None)
    ap.add_argument("--sets", default="S24,S25,S26", help="세트(시방서+공고문) 또는 'S24-공고'처럼 문서 하나")
    ap.add_argument("--answers", type=Path, default=A.DEFAULT_ANSWERS)
    ap.add_argument("--chunk-tokens", type=int, default=2_500)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    run(ap.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
