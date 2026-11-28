"""L3 정답 입력용 조항 목록 CSV 만들기 (모델 없음, 원본 읽기만).

  python -X utf8 eval/l3_clause_list.py                 # S24·S25·S26 시방서 → 정답셋_후보/L3_조항목록_<세트>.csv
                                                        #          공고문 → 정답셋_후보/L3_조항목록_<세트>_공고문.csv
  python -X utf8 eval/l3_clause_list.py --out <폴더> --show 40

정답의 clause_no는 이 CSV의 clause_no를 그대로 쓴다 (모델 출력의 pair_key와 같은 문자열이어야 짝이 맞는다).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from uuid import UUID

HERE = Path(__file__).resolve().parent
APP = HERE.parent
sys.path.insert(0, str(APP))
sys.path.insert(0, str(HERE))

from worker.roles.l3_spec.clauses import split_clauses  # noqa: E402
from worker.roles.l3_spec.reader import read_spec  # noqa: E402
from l3_eval.answers import COLLECT, NOTICE_SUFFIX, documents  # noqa: E402  (시방서·공고문 경로는 여기 한 곳)
FIELDS = ["세트", "파일", "순서", "clause_no", "상위 clause_no", "단계", "쪽", "첫 줄", "글자 수", "하위 조항 수", "메모"]
KIND = {"chapter": "장", "box": "□", "attach": "첨부·서식", "decimal": "소수점 번호", "num_dot": "1.",
        "hangul": "가.", "paren_r": "1)", "paren_both": "(1)", "circled": "①"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=COLLECT / "정답셋_후보")
    ap.add_argument("--show", type=int, default=0, help="세트마다 앞 N개 조항을 화면에 출력")
    args = ap.parse_args()
    for key, (sid, role, pat) in documents().items():
        path = next(COLLECT.glob(pat))
        spec = read_spec(path, UUID(int=0), path.suffix)
        doc = split_clauses(spec)
        rows = []
        for i, c in enumerate(doc.clauses.values(), 1):
            pages = c.pages
            memo = c.memo
            rows.append({"세트": sid, "파일": path.name, "순서": i, "clause_no": c.no, "상위 clause_no": c.parent or "",
                         "단계": KIND[c.kind], "쪽": (f"{pages[0]}" if len(pages) == 1 else f"{pages[0]}~{pages[-1]}")
                         if pages else "", "첫 줄": c.title, "글자 수": len(c.text), "하위 조항 수": len(c.children),
                         "메모": memo})
        args.out.mkdir(parents=True, exist_ok=True)
        out = args.out / (f"L3_조항목록_{sid}_공고문.csv" if key.endswith(NOTICE_SUFFIX) else f"L3_조항목록_{sid}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"{key} {path.name}: 조항 {len(rows)}개, 앞부분 뺀 줄 {doc.dropped_preamble}, 목차 뺀 줄 {doc.dropped_toc}, "
              f"번호 중복 {len(doc.duplicates)} {doc.duplicates[:5]}, 메모 {[c.no + ': ' + c.memo for c in doc.clauses.values() if c.memo]}"
              + (f", 글자층 없는 쪽 {len(spec.image_pages)}개 ({spec.image_pages[0]}~{spec.image_pages[-1]})"
                 if spec.image_pages else "") + f" → {out}")
        for r in rows[:args.show]:
            print(f"   {r['clause_no']:<22} {r['쪽']:<6} {r['첫 줄'][:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
