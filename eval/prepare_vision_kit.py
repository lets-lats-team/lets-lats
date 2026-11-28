"""Vision 시험 키트 v0.1 데이터를 만든다.

DWG → DXF(LibreDWG) → 글자 추출(ezdxf) → 영역별 crop PNG + 벡터 정답(JSON).

  python prepare_vision_kit.py --dwg "<고려대 도면.dwg 경로>"

결과: data/vision_v0.1/<영역>.png, <영역>.gt.json, manifest.json
중간 파일(DXF 등)은 work/에 둔다 (저장소에 올리지 않음).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vision_kit.ezdxf_loader import ezdxf  # noqa: E402
from vision_kit import dxf_texts, render  # noqa: E402
from vision_kit.regions import REGIONS  # noqa: E402

DEFAULT_DWG2DXF = Path(os.environ.get("LETS_DATA_ROOT") or HERE.parents[1]) / "04_도구_DWG변환" / "C_LibreDWG" / "dwg2dxf.exe"   # LETS_DATA_ROOT
TARGET_MIN_TEXT_PX = 40  # AI 설계 10장: 가장 작은 대상 글자 약 32~48px


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def convert(dwg: Path, work: Path, dwg2dxf: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    local = work / "source.dwg"
    dxf = work / "source.dxf"
    if dxf.exists() and local.exists() and sha256(local) == sha256(dwg):
        return dxf
    shutil.copyfile(dwg, local)  # 원본은 건드리지 않는다
    with open(work / "convert.log", "w", encoding="utf-8") as log:
        subprocess.run([str(dwg2dxf), "--as", "r2010", "-o", str(dxf), str(local)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    return dxf


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dwg", required=True, type=Path)
    ap.add_argument("--dwg2dxf", type=Path, default=DEFAULT_DWG2DXF)
    ap.add_argument("--work", type=Path, default=HERE / "work")
    ap.add_argument("--out", type=Path, default=HERE / "data" / "vision_v0.1")
    args = ap.parse_args()

    dxf = convert(args.dwg, args.work, args.dwg2dxf)
    print(f"DXF 읽는 중: {dxf} (1분 이상 걸림)")
    doc = ezdxf.readfile(str(dxf))

    printed = dxf_texts.extract_from_doc(doc, printed_only=True, include_dims=False)
    visible = dxf_texts.extract_from_doc(doc, printed_only=True, include_dims=True)
    print(f"출력 글자(치수 제외): {len(printed)}  /  이미지에 보이는 글자(치수 포함): {len(visible)}")

    render.prepare_doc_for_render(doc)
    from ezdxf import bbox as _bbox
    cache = _bbox.Cache()
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "kit": "vision_v0.1",
        "source_dwg": args.dwg.name,
        "source_sha256": sha256(args.dwg),
        "ezdxf": ezdxf.__version__,
        "render_font": render.RENDER_FONT,
        "printed_text_count": len(printed),
        "visible_text_count": len(visible),
        "regions": [],
    }

    for reg in REGIONS:
        seed = [t for t in visible if reg.x0 <= t.x <= reg.x1 and reg.y0 <= t.y <= reg.y1]
        if not seed:
            print(f"[{reg.key}] 글자 없음 — 영역 확인 필요")
            continue
        pad = 2 * max(t.height for t in seed)
        rect = (min(t.x0 for t in seed) - pad, min(t.y0 for t in seed) - pad,
                max(t.x1 for t in seed) + pad, max(t.y1 for t in seed) + pad)
        # 정답 = 렌더 범위 안에 상자 중심이 있는 글자 전부 (이미지에 보이는 것)
        gt = [t for t in visible
              if rect[0] <= (t.x0 + t.x1) / 2 <= rect[2] and rect[1] <= (t.y0 + t.y1) / 2 <= rect[3]]
        min_h = min(t.height for t in gt if t.height > 0)
        scale = TARGET_MIN_TEXT_PX / min_h
        png = args.out / f"{reg.key}.png"
        w, h = render.render_rect(doc, rect, scale, png, cache=cache)

        def to_px(t):
            return [round((t.x0 - rect[0]) * scale, 1), round((rect[3] - t.y1) * scale, 1),
                    round((t.x1 - rect[0]) * scale, 1), round((rect[3] - t.y0) * scale, 1)]

        items = []
        for t in gt:
            lines = [ln for ln in t.text.splitlines() if ln.strip()] or [t.text]
            for li, ln in enumerate(lines):
                items.append({
                    "id": f"{t.idx}" if len(lines) == 1 else f"{t.idx}.{li}",
                    "text": ln.strip(),
                    "kind": t.kind,
                    "is_dim": dxf_texts.is_dim(t),
                    "layer": t.layer,
                    "block_path": t.block_path,
                    "world_insert": [round(t.x, 1), round(t.y, 1)],
                    "height_mm": round(t.height, 1),
                    "px_box": to_px(t),  # 근사 상자 (글자 수 × 높이 × 0.8)
                })
        with open(args.out / f"{reg.key}.gt.json", "w", encoding="utf-8") as f:
            json.dump({"region": reg.key, "title": reg.title, "world_rect": rect, "scale_px_per_mm": scale,
                       "image": png.name, "image_size": [w, h], "items": items}, f, ensure_ascii=False, indent=1)
        n_dim = sum(1 for t in gt if dxf_texts.is_dim(t))
        info = {"key": reg.key, "title": reg.title, "note": reg.note, "seed_rect": [reg.x0, reg.y0, reg.x1, reg.y1],
                "render_rect": [round(v, 1) for v in rect], "scale_px_per_mm": round(scale, 4),
                "image_size": [w, h], "min_text_height_mm": min_h,
                "seed_texts": len(seed), "gt_texts": len(gt), "gt_dim_texts": n_dim, "gt_units": len(items)}
        manifest["regions"].append(info)
        print(f"[{reg.key}] 글자 {len(seed)}(영역) → 정답 {len(gt)} (치수 {n_dim}), 판정 단위 {len(items)}, 이미지 {w}x{h}px")

    with open(args.out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"완료: {args.out}")


if __name__ == "__main__":
    main()
