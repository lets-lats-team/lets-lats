"""채점. 정규화 후 글자 덩어리 단위로 정확히 같으면 맞음.

- 맞음(TP): 조각의 정답(full) 중 하나와 같음. 같은 정답은 한 번만 짝지음.
- 무시: 조각 경계에서 잘린 글자(partial)의 일부와 같음 (모델이 잘린 글자를 읽은 경우).
- 오답(FP): 그 외. 정답을 둘로 쪼개 읽은 것도 오답이다.
- 놓침: 짝을 못 찾은 정답.
영역 재현율은 '정답 글자가 들어 있는 조각 중 하나에서라도 맞았는가'로 센다.
"""
from __future__ import annotations

from collections import defaultdict

from .normalize import has_digit, norm


def score_tile(tile, readings: list[str]) -> dict:
    pool: dict[str, list[str]] = defaultdict(list)
    for it in tile.full:
        pool[norm(it["text"])].append(it["id"])
    partial = [norm(it["text"]) for it in tile.partial]
    hit_ids, fp, ignored = [], [], []
    for r in readings:
        n = norm(r)
        if not n:
            continue
        if pool.get(n):
            hit_ids.append(pool[n].pop())
        elif any(n in p for p in partial):
            ignored.append(r)
        else:
            fp.append(r)
    return {"hit_ids": hit_ids, "fp": fp, "ignored": ignored}


def score_region(items: list[dict], tiles, tile_results: dict[str, dict | None]) -> dict:
    """tile_results: tile key → score_tile 결과 (호출 실패면 None)."""
    by_id = {it["id"]: it for it in items}
    scorable = set()
    for t in tiles:
        scorable.update(it["id"] for it in t.full)
    excluded = [i for i in by_id if i not in scorable]
    hits, tp, fp_total, fps, failed = set(), 0, 0, [], 0
    for t in tiles:
        r = tile_results.get(t.key)
        if r is None:
            failed += 1
            continue
        hits.update(r["hit_ids"])
        tp += len(r["hit_ids"])
        fp_total += len(r["fp"])
        fps.extend(r["fp"])
    num_ids = [i for i in scorable if has_digit(by_id[i]["text"])]
    missed = sorted(scorable - hits)
    return {
        "scorable": len(scorable),
        "excluded_never_whole_in_a_tile": len(excluded),
        "hits": len(hits),
        "recall": len(hits) / len(scorable) if scorable else None,
        "numeric_total": len(num_ids),
        "numeric_hits": sum(1 for i in num_ids if i in hits),
        "numeric_recall": (sum(1 for i in num_ids if i in hits) / len(num_ids)) if num_ids else None,
        "tp": tp,
        "fp": fp_total,
        "precision": tp / (tp + fp_total) if (tp + fp_total) else None,
        "failed_tiles": failed,
        "missed_texts": [by_id[i]["text"] for i in missed][:200],
        "fp_texts": fps[:200],
    }
