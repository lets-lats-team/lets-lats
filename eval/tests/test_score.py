import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vision_kit.normalize import norm  # noqa: E402
from vision_kit.score import score_region, score_tile  # noqa: E402
from vision_kit.tiles import make_tiles  # noqa: E402


def item(i, text, box):
    return {"id": str(i), "text": text, "px_box": box}


ITEMS = [
    item(1, "Ø19.05", (10, 10, 60, 30)),
    item(2, "1, 2, 220, 60", (10, 50, 120, 70)),
    item(3, "세종병무행정팀", (180, 10, 260, 30)),   # 오른쪽 경계에 걸림 (이미지 폭 200)
    item(4, "EHP", (10, 90, 40, 110)),
]


def test_normalize():
    assert norm("φ 19.05") == "Ø19.05"
    assert norm("ø19.05") == "Ø19.05"
    assert norm("１２．７") == "12.7"
    assert norm("5.5㎟") == "5.5mm2"


def test_tile_scoring_counts_fp_partial_and_split():
    tiles = make_tiles(200, 200, 1, ITEMS)
    t = tiles[0]
    assert {it["id"] for it in t.full} == {"1", "2", "4"}
    assert {it["id"] for it in t.partial} == {"3"}
    r = score_tile(t, ["φ19.05", "1, 2,", "220, 60", "세종병무", "EHP", "EHP"])
    assert sorted(r["hit_ids"]) == ["1", "4"]      # 표기 달라도 정규화 후 맞음
    assert r["ignored"] == ["세종병무"]             # 잘린 글자의 일부는 무시
    assert r["fp"] == ["1, 2,", "220, 60", "EHP"]  # 쪼개 읽기와 중복은 오답


def test_region_recall_and_numeric():
    tiles = make_tiles(200, 200, 1, ITEMS)
    r = score_tile(tiles[0], ["Ø19.05", "EHP", "잘못읽음"])
    s = score_region(ITEMS, tiles, {tiles[0].key: r})
    assert s["scorable"] == 3 and s["excluded_never_whole_in_a_tile"] == 1
    assert s["hits"] == 2 and abs(s["recall"] - 2 / 3) < 1e-9
    assert s["numeric_total"] == 2 and s["numeric_hits"] == 1
    assert s["tp"] == 2 and s["fp"] == 1


def test_failed_call_counts_as_miss():
    tiles = make_tiles(200, 200, 1, ITEMS)
    s = score_region(ITEMS, tiles, {tiles[0].key: None})
    assert s["hits"] == 0 and s["failed_tiles"] == 1


def test_tiles_overlap_and_cover():
    tiles = make_tiles(1000, 500, 2, [])
    assert len(tiles) == 4
    assert tiles[0].box[0] == 0 and tiles[-1].box[2] == 1000 and tiles[-1].box[3] == 500
    assert tiles[1].box[0] < tiles[0].box[2]  # 겹침
