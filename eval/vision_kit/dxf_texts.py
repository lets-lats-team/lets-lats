"""DXF에서 화면에 출력되는 글자를 모두 뽑는다 (블록 안 글자 포함).

각 글자에 대해 원문, 레이어, 월드 좌표(삽입점), 글자 높이, 회전, 블록 경로를 남긴다.
이 목록이 Vision 시험 키트의 '벡터 정답'의 원천이다.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .ezdxf_loader import ezdxf

TEXT_TYPES = {"TEXT", "MTEXT", "ATTRIB"}


@dataclass
class TextItem:
    idx: int
    kind: str
    text: str
    layer: str
    x: float
    y: float
    height: float
    rotation: float
    block_path: str
    # 대략적인 글자 영역(월드 좌표). 렌더 범위·정답 포함 판정에 쓴다.
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


def _plain(e) -> str:
    t = e.dxftype()
    if t == "MTEXT":
        return e.plain_text().strip()
    if t in ("TEXT", "ATTRIB"):
        try:
            return e.plain_text().strip()
        except Exception:
            return (e.dxf.text or "").strip()
    return ""


def _approx_box(x, y, h, rot_deg, n_chars, halign_center=False):
    """글자 상자를 근사한다. 폭 = 글자 수 × 높이 × 0.8 (한글·숫자 평균)."""
    w = max(n_chars, 1) * h * 0.8
    r = math.radians(rot_deg or 0.0)
    ox = -w / 2 if halign_center else 0.0
    pts = [(ox, 0), (ox + w, 0), (ox + w, h), (ox, h)]
    xs, ys = [], []
    for px, py in pts:
        xs.append(x + px * math.cos(r) - py * math.sin(r))
        ys.append(y + px * math.sin(r) + py * math.cos(r))
    return min(xs), min(ys), max(xs), max(ys)


def _walk(entities, path, out, depth=0):
    for e in entities:
        t = e.dxftype()
        if t in TEXT_TYPES:
            s = _plain(e)
            if not s:
                continue
            ins = e.dxf.insert if e.dxf.hasattr("insert") else None
            if ins is None:
                continue
            if t == "MTEXT":
                h = float(e.dxf.get("char_height", 0) or 0)
                rot = float(e.get_rotation() if hasattr(e, "get_rotation") else e.dxf.get("rotation", 0))
                lines = s.splitlines() or [s]
                n = max(len(l) for l in lines)
                x0, y0, x1, y1 = _approx_box(ins.x, ins.y - h * len(lines) * 1.6 + h, h, rot, n)
                y1 = max(y1, ins.y)
            else:
                h = float(e.dxf.get("height", 0) or 0)
                rot = float(e.dxf.get("rotation", 0) or 0)
                halign = int(e.dxf.get("halign", 0) or 0)
                align_pt = e.dxf.get("align_point", None)
                px, py = ins.x, ins.y
                if halign in (1, 2, 4) and align_pt is not None:
                    px, py = align_pt.x, align_pt.y
                x0, y0, x1, y1 = _approx_box(px, py, h, rot, len(s), halign_center=halign in (1, 4))
            out.append(TextItem(len(out), t, s, e.dxf.layer, float(ins.x), float(ins.y), h, rot,
                                "/".join(path), x0, y0, x1, y1))
        elif t == "INSERT" and depth < 8:
            name = e.dxf.name
            try:
                if e.attribs:
                    _walk(e.attribs, path + [name], out, depth + 1)
                _walk(e.virtual_entities(), path + [name], out, depth + 1)
            except Exception:
                continue
        elif t == "DIMENSION":
            # 치수 글자는 익명 블록 안에 있다.
            try:
                _walk(e.virtual_entities(), path + ["*DIM"], out, depth + 1)
            except Exception:
                continue


def hidden_layers(doc) -> set[str]:
    """인쇄되지 않는 레이어(끔·동결·인쇄 안 함, Defpoints) 이름 (소문자)."""
    hidden = {"defpoints"}
    for layer in doc.layers:
        if layer.is_off() or layer.is_frozen() or not bool(layer.dxf.get("plot", 1)):
            hidden.add(layer.dxf.name.lower())
    return hidden


def is_dim(it: TextItem) -> bool:
    return "*DIM" in it.block_path.split("/")


def extract_from_doc(doc, printed_only: bool = True, include_dims: bool = False) -> list[TextItem]:
    """printed_only=True면 인쇄되지 않는 레이어의 글자를 뺀다.

    include_dims=False면 치수 글자도 뺀다. 고려대 행정관 DWG에서
    printed_only=True, include_dims=False 결과가 AI 설계 3장의 6,201개와 일치한다.
    시험 키트 정답은 이미지에 보이는 글자 전부여야 하므로 include_dims=True로 만든다.
    """
    out: list[TextItem] = []
    _walk(doc.modelspace(), [], out)
    hidden = hidden_layers(doc) if printed_only else set()
    kept = [it for it in out if it.layer.lower() not in hidden and (include_dims or not is_dim(it))]
    for i, it in enumerate(kept):
        it.idx = i
    return kept


def extract(dxf_path: Path, printed_only: bool = True, include_dims: bool = False) -> list[TextItem]:
    doc = ezdxf.readfile(str(dxf_path))
    return extract_from_doc(doc, printed_only, include_dims)


def save_csv(items: list[TextItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(items[0]).keys()))
        w.writeheader()
        for it in items:
            w.writerow(asdict(it))


def load_csv(path: Path) -> list[TextItem]:
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    items = []
    for r in rows:
        items.append(TextItem(int(r["idx"]), r["kind"], r["text"], r["layer"], float(r["x"]), float(r["y"]),
                              float(r["height"]), float(r["rotation"]), r["block_path"],
                              float(r["x0"]), float(r["y0"]), float(r["x1"]), float(r["y1"])))
    return items
