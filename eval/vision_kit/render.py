"""DWG(DXF) 벡터를 직접 그림으로 그린다 (AI 설계 10장: 화면 캡처 금지, 흑백).

- 인쇄되지 않는 레이어는 끈다 (이미지와 정답이 같은 글자를 갖게).
- 한글이 깨지지 않도록 모든 글자 스타일의 글꼴을 맑은 고딕으로 바꾼다 (렌더용 사본 문서에서만).
- 큰 블록(층 배경 등)은 풀어서 영역에 걸치는 객체만 그린다.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .ezdxf_loader import ezdxf  # noqa: E402
from ezdxf import bbox  # noqa: E402
from ezdxf.addons.drawing import RenderContext  # noqa: E402
from ezdxf.addons.drawing.frontend import Frontend  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402
from ezdxf.addons.drawing.config import (  # noqa: E402
    BackgroundPolicy,
    ColorPolicy,
    Configuration,
    HatchPolicy,
)

from .dxf_texts import hidden_layers  # noqa: E402

RENDER_FONT = "malgun.ttf"


def prepare_doc_for_render(doc) -> None:
    hidden = hidden_layers(doc)
    for layer in doc.layers:
        if layer.dxf.name.lower() in hidden:
            layer.off()
    for style in doc.styles:
        style.dxf.font = RENDER_FONT  # 원래 글꼴(SHX 등)은 이 PC에 없어 대체
        if style.dxf.hasattr("bigfont"):
            style.dxf.bigfont = ""
    # WIPEOUT(아래를 가리는 배경색 사각형)은 흑백 설정에서 검정으로 칠해져 표 전체를 덮는다.
    # 렌더용 문서에서만 지운다 (원본 파일은 바뀌지 않음).
    for block in doc.blocks:
        for e in list(block.query("WIPEOUT")):
            block.delete_entity(e)


def _overlaps(ext, rect) -> bool:
    x0, y0, x1, y1 = rect
    return not (ext.extmax.x < x0 or ext.extmin.x > x1 or ext.extmax.y < y0 or ext.extmin.y > y1)


def _area(ext) -> float:
    return max(ext.size.x, 0) * max(ext.size.y, 0)


def select_entities(entities, rect, cache, depth=0) -> list:
    """rect에 걸치는 객체만 고른다. rect보다 훨씬 큰 블록은 풀어서 다시 고른다."""
    rect_area = (rect[2] - rect[0]) * (rect[3] - rect[1])
    out = []
    for e in entities:
        try:
            ext = bbox.extents([e], fast=True, cache=cache)
        except Exception:
            continue
        if not ext.has_data or not _overlaps(ext, rect):
            continue
        # rect보다 훨씬 큰 객체(층 배경 블록, 도곽 테두리 폴리선 등)는 풀어서 다시 고른다.
        # 폭이 있는 큰 닫힌 폴리선이 통째로 칠해져 영역 전체가 검게 나오는 것을 막는다.
        if depth < 6 and _area(ext) > 4 * rect_area and hasattr(e, "virtual_entities"):
            try:
                parts = list(e.virtual_entities())
            except Exception:
                parts = []
            if parts:
                out.extend(select_entities(parts, rect, None, depth + 1))
                continue
            if e.dxftype() not in ("INSERT",):
                continue  # 풀 수 없는 큰 객체는 영역 안에서 보이는 부분이 없다고 보고 뺀다
        out.append(e)
    return out


def render_rect(doc, rect, scale_px_per_unit: float, out_path: Path, cache=None, dpi: int = 100) -> tuple[int, int]:
    """rect(월드 좌표)를 scale(px/mm)로 그려 PNG로 저장한다. (폭, 높이) px를 돌려준다."""
    x0, y0, x1, y1 = rect
    w_px = int(round((x1 - x0) * scale_px_per_unit))
    h_px = int(round((y1 - y0) * scale_px_per_unit))
    ents = select_entities(doc.modelspace(), rect, cache)

    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    backend = MatplotlibBackend(ax, adjust_figure=False)
    cfg = Configuration(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE,
                        hatch_policy=HatchPolicy.SHOW_OUTLINE)  # 큰 해치가 글자를 덮지 않게
    ctx = RenderContext(doc)
    Frontend(ctx, backend, config=cfg).draw_entities(ents)
    backend.finalize()
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("auto")
    ax.set_axis_off()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return w_px, h_px
