"""Vision 시험 키트 v0.1 실행기.

  python run_vision_eval.py --provider gt
  python run_vision_eval.py --provider openai    --model gpt-6-luna       --tiles 2 --repeat 3
  python run_vision_eval.py --provider anthropic --model claude-haiku-5-5 --tiles 2 --repeat 3
  python run_vision_eval.py --provider openai_compat --model <이름> --base-url http://localhost:8000/v1

결과: results/<시각>_<공급자>_<모델>/ (config.json, calls.jsonl, scores.json, report.md)
실제 모델 호출은 도면 crop을 외부로 보낸다 (AI 설계 16장: 제공처·팀 동의 후 실행).
"""
from __future__ import annotations

import argparse
import io
import json
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vision_kit import prompt as P  # noqa: E402
from vision_kit.providers import CallOptions, get_provider  # noqa: E402
from vision_kit.score import score_region, score_tile  # noqa: E402
from vision_kit.tiles import make_tiles  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

# 100만 토큰당 (입력, 출력) USD. AI 설계 2장 (2026-11-21 확인). Haiku는 프롬프트 10만 토큰 이하 구간.
PRICES = {"gpt-6-luna": (0.10, 0.50), "claude-haiku-5-5": (0.10, 0.50)}


def crop_png(img: Image.Image, box, max_side: int) -> tuple[bytes, list[int], float]:
    c = img.crop(box)
    scale = 1.0
    if max(c.size) > max_side:
        scale = max_side / max(c.size)
        c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    c.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), list(c.size), scale


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", required=True, choices=["gt", "openai", "anthropic", "openai_compat"])
    ap.add_argument("--model", default="gt")
    ap.add_argument("--tiles", type=int, default=2, help="N이면 N×N 조각 (1 = 나누지 않음)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--regions", default="all", help="쉼표로 구분 (legend,equipment,plan_3f)")
    ap.add_argument("--effort", default=None, help="추론 강도 (예: none·low / low·medium)")
    ap.add_argument("--detail", default=None, help="Luna 이미지 detail (high / original)")
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--timeout", type=float, default=120.0, help="호출 시간 상한(초)")
    ap.add_argument("--max-side", type=int, default=8000, help="조각 이미지 긴 변 상한(px), 넘으면 줄임")
    ap.add_argument("--concurrency", type=int, default=4, help="동시 호출 수 (AI 설계 11.2: 모델별 4)")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--price-in", type=float, default=None, help="100만 입력 토큰당 USD (기본: 표)")
    ap.add_argument("--price-out", type=float, default=None)
    ap.add_argument("--data", type=Path, default=HERE / "data" / "vision_v0.1")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()

    manifest = json.loads((args.data / "manifest.json").read_text(encoding="utf-8"))
    keys = [r["key"] for r in manifest["regions"]]
    if args.regions != "all":
        keys = [k for k in args.regions.split(",") if k in keys]

    opts = CallOptions(model=args.model, max_tokens=args.max_tokens, timeout_s=args.timeout,
                       effort=args.effort, detail=args.detail, base_url=args.base_url)
    provider = get_provider(args.provider, opts)

    run_dir = args.out / f"{datetime.now():%Y%m%d-%H%M%S}_{args.provider}_{re.sub(r'[^A-Za-z0-9.-]', '_', args.model)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(json.dumps({
        **{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "prompt_version": P.PROMPT_VERSION, "kit": manifest["kit"], "source_sha256": manifest["source_sha256"],
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 작업 목록: 영역 × 조각 × 반복
    regions = {}
    jobs = []
    for k in keys:
        gt = json.loads((args.data / f"{k}.gt.json").read_text(encoding="utf-8"))
        img = Image.open(args.data / gt["image"]).convert("RGB")
        tiles = make_tiles(img.width, img.height, args.tiles, gt["items"])
        regions[k] = {"gt": gt, "tiles": tiles}
        for t in tiles:
            png, size, scale = crop_png(img, t.box, args.max_side)
            for rep in range(args.repeat):
                jobs.append((k, t, rep, png, size, scale))
    print(f"{args.provider}/{args.model}: 영역 {len(keys)}개, 호출 {len(jobs)}회 (조각 {args.tiles}x{args.tiles}, 반복 {args.repeat})")

    def run(job):
        k, t, rep, png, size, scale = job
        res = provider.call(png, P.PROMPT, P.SCHEMA, tile_full_texts=[it["text"] for it in t.full])
        readings = []
        if res.parsed and isinstance(res.parsed.get("readings"), list):
            readings = [str(r.get("raw_text", "")) for r in res.parsed["readings"] if isinstance(r, dict)]
        return {
            "region": k, "tile": t.key, "repeat": rep, "image_px": size, "image_scale": scale,
            "image_bytes": len(png), "latency_ms": res.latency_ms, "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens, "error": res.error, "response_id": res.response_id,
            "status": (res.parsed or {}).get("status"), "readings": readings, "extra": res.extra,
        }

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        calls = list(ex.map(run, jobs))
    wall = time.perf_counter() - t0
    with open(run_dir / "calls.jsonl", "w", encoding="utf-8") as f:
        for c in calls:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # 채점: 영역 × 반복
    scores = {"regions": {}, "overall": {}}
    per_rep_overall = []
    for rep in range(args.repeat):
        tot = {"scorable": 0, "hits": 0, "numeric_total": 0, "numeric_hits": 0, "tp": 0, "fp": 0}
        for k in keys:
            tiles = regions[k]["tiles"]
            tr = {}
            for c in calls:
                if c["region"] == k and c["repeat"] == rep:
                    t = next(x for x in tiles if x.key == c["tile"])
                    tr[t.key] = None if c["error"] else score_tile(t, c["readings"])
            s = score_region(regions[k]["gt"]["items"], tiles, tr)
            scores["regions"].setdefault(k, {"repeats": []})["repeats"].append(s)
            for f in tot:
                tot[f] += s[f]
        tot["recall"] = tot["hits"] / tot["scorable"] if tot["scorable"] else None
        tot["numeric_recall"] = tot["numeric_hits"] / tot["numeric_total"] if tot["numeric_total"] else None
        tot["precision"] = tot["tp"] / (tot["tp"] + tot["fp"]) if (tot["tp"] + tot["fp"]) else None
        per_rep_overall.append(tot)

    def summarize(reps):
        out = {}
        for f in ("recall", "numeric_recall", "precision"):
            vals = [r[f] for r in reps if r[f] is not None]
            out[f + "_mean"] = statistics.mean(vals) if vals else None
            out[f + "_spread_pp"] = (max(vals) - min(vals)) * 100 if len(vals) > 1 else 0.0
        return out

    for k in keys:
        reps = scores["regions"][k]["repeats"]
        scores["regions"][k].update(summarize(reps))
        scores["regions"][k]["scorable"] = reps[0]["scorable"]
        scores["regions"][k]["excluded"] = reps[0]["excluded_never_whole_in_a_tile"]
    scores["overall"] = summarize(per_rep_overall)
    scores["overall"]["repeats"] = per_rep_overall

    lat = [c["latency_ms"] for c in calls if not c["error"]]
    tin = sum(c["input_tokens"] for c in calls)
    tout = sum(c["output_tokens"] for c in calls)
    pin, pout = PRICES.get(args.model, (None, None))
    pin = args.price_in if args.price_in is not None else pin
    pout = args.price_out if args.price_out is not None else pout
    cost = (tin * pin + tout * pout) / 1e6 if pin is not None and pout is not None else None
    errors = {}
    for c in calls:
        if c["error"]:
            errors[c["error"]] = errors.get(c["error"], 0) + 1
    scores["calls"] = {
        "count": len(calls), "errors": errors, "wall_s": round(wall, 1),
        "latency_p50_ms": pct(lat, 0.5), "latency_p95_ms": pct(lat, 0.95),
        "input_tokens": tin, "output_tokens": tout, "cost_usd": cost,
        "cost_per_1000_calls_usd": (cost / len(calls) * 1000) if cost is not None and calls else None,
    }
    (run_dir / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=1), encoding="utf-8")

    def f(v, pctv=True):
        if v is None:
            return "-"
        return f"{v * 100:.1f}%" if pctv else f"{v:.1f}"

    lines = [f"# Vision 시험 결과 — {args.provider} / {args.model}", "",
             f"- 키트 {manifest['kit']}, 프롬프트 {P.PROMPT_VERSION}, 조각 {args.tiles}x{args.tiles}, 반복 {args.repeat}, "
             f"추론 강도 {args.effort or '기본'}, detail {args.detail or '기본'}", "",
             "| 영역 | 채점 글자 | 경계 제외 | 재현율 | 숫자 칸 재현율 | 정밀도 | 반복 편차(재현율) |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for k in keys:
        s = scores["regions"][k]
        lines.append(f"| {k} | {s['scorable']} | {s['excluded']} | {f(s['recall_mean'])} | {f(s['numeric_recall_mean'])} | "
                     f"{f(s['precision_mean'])} | {s['recall_spread_pp']:.1f}%p |")
    o = scores["overall"]
    lines.append(f"| **전체** | | | **{f(o['recall_mean'])}** | **{f(o['numeric_recall_mean'])}** | "
                 f"**{f(o['precision_mean'])}** | {o['recall_spread_pp']:.1f}%p |")
    cs = scores["calls"]
    lines += ["", f"- 호출 {cs['count']}회, 오류 {cs['errors'] or '없음'}, 걸린 시간 {cs['wall_s']}초",
              f"- 호출 시간 p50 {cs['latency_p50_ms'] or '-'} ms · p95 {cs['latency_p95_ms'] or '-'} ms",
              f"- 토큰 입력 {tin:,} · 출력 {tout:,}, 추정 비용 "
              + (f"${cost:.4f} (1,000회당 ${cs['cost_per_1000_calls_usd']:.2f})" if cost is not None else "- (단가 미지정)"),
              "", "놓친 글자·오답 목록은 scores.json의 missed_texts, fp_texts를 본다."]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n결과 폴더: {run_dir}")


if __name__ == "__main__":
    main()
