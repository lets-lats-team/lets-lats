"""이미지를 N×N 조각으로 나누고, 조각마다 정답을 정한다 (AI 설계 10장: 2×2, 12% 겹침).

조각 안에 상자가 다 들어가는 글자 = 그 조각의 정답(full).
조각 경계에 걸린 글자 = 부분(partial). 모델이 그 일부를 읽어도 오답으로 세지 않는다.
어느 조각에도 온전히 들어가지 않는 글자는 채점에서 빼고 수를 보고한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

OVERLAP = 0.12
TOL_PX = 1.0


@dataclass
class Tile:
    key: str
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 (px)
    full: list[dict] = field(default_factory=list)
    partial: list[dict] = field(default_factory=list)


def _inside(b, t) -> bool:
    return b[0] >= t[0] - TOL_PX and b[1] >= t[1] - TOL_PX and b[2] <= t[2] + TOL_PX and b[3] <= t[3] + TOL_PX


def _intersects(b, t) -> bool:
    return not (b[2] <= t[0] or b[0] >= t[2] or b[3] <= t[1] or b[1] >= t[3])


def make_tiles(width: int, height: int, n: int, items: list[dict]) -> list[Tile]:
    if n <= 1:
        boxes = [(0, 0, width, height)]
    else:
        tw = width / (n - (n - 1) * OVERLAP)
        th = height / (n - (n - 1) * OVERLAP)
        boxes = []
        for r in range(n):
            for c in range(n):
                x0 = int(round(c * tw * (1 - OVERLAP)))
                y0 = int(round(r * th * (1 - OVERLAP)))
                boxes.append((x0, y0, min(width, int(round(x0 + tw))), min(height, int(round(y0 + th)))))
    image_box = (0, 0, width, height)
    tiles = []
    for i, tb in enumerate(boxes):
        t = Tile(key=f"t{i}", box=tb)
        for it in items:
            b = it["px_box"]
            if not _intersects(b, tb):
                continue
            if _inside(b, tb) and _inside(b, image_box):
                t.full.append(it)
            else:
                t.partial.append(it)
        tiles.append(t)
    return tiles
