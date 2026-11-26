import { useCallback, useEffect, useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from 'react';
import type { Analysis, PlanNode, ReviewItem } from '../../api/contracts';
import { Icon } from '../../components/Sprite';

/**
 * 도면 뷰어 (SVG 좌표 기반 벡터 렌더링).
 * - 2D 미리보기 형식(SVG · 이미지 · 좌표)은 백엔드 미정 → 지금은 A04의 nodes · reviewItems 좌표로 그립니다.
 *   형식이 확정되면 `PlanLayer`만 교체하면 됩니다 (어댑터 구조).
 * - 휠 · 핀치 확대, 드래그 이동, 맞춤 보기, 전체 화면, 레이어 토글, 선택 구간 강조.
 */

export type LayerKey = 'arch' | 'pipe' | 'br' | 'unit' | 'lbl' | 'other';
const LAYER_NAMES: [LayerKey, string, string][] = [
  ['arch', '건축 배경 · ARCH_BACKGROUND', '#BDB6B0'], ['pipe', '냉매 배관 · REFRIGERANT_PIPE', '#0E7490'], ['br', '분기 · BRANCH_FITTING', '#C2410C'],
  ['unit', '장비 · UNIT', '#1D4ED8'], ['lbl', '라벨 · UNIT_LABEL/PIPE_TAG', '#4b4650'], ['other', '타 계통 선 (교차 확인)', '#9CA3AF'],
];
interface VB { x: number; y: number; w: number; h: number }
const FULL: VB = { x: 0, y: 0, w: 1000, h: 700 };

export const segPoints = (it: ReviewItem, nodes: Record<string, PlanNode>): [number, number][] =>
  it.points ?? [[nodes[it.from].x, nodes[it.from].y], [nodes[it.to].x, nodes[it.to].y]];

export function CadViewer({ analysis, selected, onSelect, focusKey, sample, children }: {
  analysis: Analysis; selected: string | null; onSelect: (id: string) => void; focusKey: number; sample: boolean; children?: ReactNode;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [vb, setVb] = useState<VB>(FULL);
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({ arch: true, pipe: true, br: true, unit: true, lbl: true, other: true });
  const [lyrOpen, setLyrOpen] = useState(false);
  const [bg, setBg] = useState(0);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const drag = useRef<{ x: number; y: number; vb: VB; moved: boolean; pinch?: number } | null>(null);
  const nodes = Object.fromEntries(analysis.nodes.map((n) => [n.id, n]));

  const zoom = useCallback((f: number, cx?: number, cy?: number) => {
    setVb((v) => {
      const w = Math.min(1600, Math.max(160, v.w * f));
      const k = w / v.w;
      const px = cx ?? v.x + v.w / 2;
      const py = cy ?? v.y + v.h / 2;
      return { x: px - (px - v.x) * k, y: py - (py - v.y) * k, w, h: w * 0.7 };
    });
  }, []);

  // 선택 구간으로 이동
  useEffect(() => {
    if (!selected || !focusKey) return;
    const it = analysis.reviewItems.find((i) => i.itemId === selected);
    if (!it) return;
    const p = segPoints(it, nodes);
    const xs = p.map((a) => a[0]);
    const ys = p.map((a) => a[1]);
    const w = Math.max(420, (Math.max(...xs) - Math.min(...xs)) * 2.4);
    const mx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const my = (Math.min(...ys) + Math.max(...ys)) / 2;
    setVb({ x: mx - w / 2, y: my - (w * 0.7) / 2, w, h: w * 0.7 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusKey]);

  // 휠 확대 (passive: false 필요)
  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      setVb((v) => {
        const px = v.x + ((e.clientX - r.left) / r.width) * v.w;
        const py = v.y + ((e.clientY - r.top) / r.height) * v.h;
        const f = e.deltaY > 0 ? 1.15 : 0.87;
        const w = Math.min(1600, Math.max(160, v.w * f));
        const k = w / v.w;
        return { x: px - (px - v.x) * k, y: py - (py - v.y) * k, w, h: w * 0.7 };
      });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const onDown = (e: RPointerEvent) => {
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const pts = [...pointers.current.values()];
    drag.current = { x: e.clientX, y: e.clientY, vb, moved: false, pinch: pts.length === 2 ? Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) : undefined };
  };
  const onMove = (e: RPointerEvent) => {
    if (!drag.current || !svg.current) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const r = svg.current.getBoundingClientRect();
    const pts = [...pointers.current.values()];
    if (pts.length === 2 && drag.current.pinch) {
      const d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      const f = drag.current.pinch / d;
      const s = drag.current.vb;
      const cx = s.x + (((pts[0].x + pts[1].x) / 2 - r.left) / r.width) * s.w;
      const cy = s.y + (((pts[0].y + pts[1].y) / 2 - r.top) / r.height) * s.h;
      const w = Math.min(1600, Math.max(160, s.w * f));
      const k = w / s.w;
      setVb({ x: cx - (cx - s.x) * k, y: cy - (cy - s.y) * k, w, h: w * 0.7 });
      drag.current.moved = true;
      return;
    }
    const dx = e.clientX - drag.current.x;
    const dy = e.clientY - drag.current.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.current.moved = true;
    const k = drag.current.vb.w / r.width;
    setVb({ ...drag.current.vb, x: drag.current.vb.x - dx * k, y: drag.current.vb.y - dy * k });
  };
  const onUp = (e: RPointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (drag.current && !drag.current.moved) {
      const hit = (e.target as Element).closest?.('[data-id]') as SVGElement | null;
      if (hit?.dataset.id) onSelect(hit.dataset.id);
    }
    drag.current = pointers.current.size ? { ...drag.current!, vb, x: e.clientX, y: e.clientY, pinch: undefined } : null;
  };

  const fullscreen = () => {
    const el = wrap.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  };

  const sel = analysis.reviewItems.find((i) => i.itemId === selected);
  const selU = sel?.to;

  return (
    <div className={`viewer ${['', 'warm', 'dim'][bg]}`} ref={wrap}>
      <svg
        id="cad"
        ref={svg}
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
        role="img"
        aria-label={`계통 도면 뷰어${analysis.isDemo ? ' (가상 교육용 도면)' : ''}`}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        onDoubleClick={() => setVb(FULL)}
      >
        <rect x={-2000} y={-2000} width={5000} height={5000} fill="var(--cad-bg)" />
        {layers.arch && <Arch sample={sample} />}
        {layers.other && <g className="other"><line x1="760" y1="60" x2="760" y2="640" /></g>}
        {layers.pipe && analysis.reviewItems.map((it) => {
          const p = segPoints(it, nodes).map((a) => a.join(',')).join(' ');
          const on = it.itemId === selected;
          return (
            <g key={it.itemId}>
              {on && <polyline className="halo" points={p} />}
              <polyline className={`seg ${it.status} ${on ? 'on' : ''}`} points={p} />
              <polyline className="flow" points={p} />
              <polyline className="hit" data-id={it.itemId} points={p}><title>{`${it.itemId} · ${nodes[it.from]?.label} → ${nodes[it.to]?.label}`}</title></polyline>
            </g>
          );
        })}
        {layers.other && layers.pipe && <circle className="xing" cx="760" cy="365" r="9" />}
        {layers.br && analysis.nodes.filter((n) => n.kind === 'BRANCH').map((n) => (
          <rect key={n.id} className="br" x={n.x - 9} y={n.y - 9} width="18" height="18" transform={`rotate(45 ${n.x} ${n.y})`} />
        ))}
        {layers.unit && analysis.nodes.map((n) =>
          n.kind === 'IDU' ? (
            <g key={n.id} className={`unit ${selU === n.id ? 'on' : ''}`}>
              <rect className="o" x={n.x - 26} y={n.y - 26} width="52" height="52" rx="6" />
              <rect className="i" x={n.x - 12} y={n.y - 12} width="24" height="24" rx="3" />
            </g>
          ) : n.kind === 'OU' ? (
            <g key={n.id} className="ou"><rect x={n.x - 30} y={n.y - 30} width="60" height="60" rx="6" /><circle cx={n.x} cy={n.y} r="18" fill="none" stroke="#fff" strokeWidth="4" /></g>
          ) : null,
        )}
        {layers.lbl && analysis.nodes.map((n) => (
          <text key={n.id} className="lbl" x={n.kind === 'BRANCH' ? n.x + 12 : n.x} y={n.kind === 'OU' ? n.y + 55 : n.kind === 'IDU' ? (n.y < 365 ? n.y - 36 : n.y + 48) : n.y - 14} textAnchor={n.kind === 'BRANCH' ? 'start' : 'middle'} style={n.kind === 'BRANCH' ? { fontSize: 12 } : undefined}>{n.label}</text>
        ))}
        {layers.lbl && sel && (() => {
          const p = segPoints(sel, nodes);
          const m = Math.floor((p.length - 1) / 2);
          const x = (p[m][0] + p[m + 1][0]) / 2;
          const y = (p[m][1] + p[m + 1][1]) / 2;
          return (
            <g transform={`translate(${x} ${y - 34})`}>
              <rect x="-58" y="-16" width="116" height="28" rx="7" fill="var(--cad-sel)" />
              <text x="0" y="3" textAnchor="middle" style={{ font: '700 14px Inter', fill: '#fff' }}>{sel.itemId} · {(sel.adoptedLengthM ?? sel.planLengthM).toFixed(2)} m</text>
            </g>
          );
        })()}
      </svg>
      <div className="vtag">
        {analysis.isDemo && <span className="badge s-DEMO"><Icon name="i-info" />Mock · 가상 교육용 도면</span>}
        <span className="zoomv">{Math.round((1000 / vb.w) * 100)}%</span>
      </div>
      <div className="vt">
        <button onClick={() => zoom(0.8)} aria-label="확대"><Icon name="i-zin" /></button>
        <button onClick={() => zoom(1.25)} aria-label="축소"><Icon name="i-zout" /></button>
        <button onClick={() => setVb(FULL)} aria-label="맞춤 보기"><Icon name="i-fit" /></button>
        <button onClick={() => setLyrOpen(!lyrOpen)} aria-label="레이어" aria-pressed={lyrOpen}><Icon name="i-layers" /></button>
        <button onClick={() => setBg((bg + 1) % 3)} aria-label="캔버스 밝기"><Icon name="i-sun" /></button>
        <button onClick={fullscreen} aria-label="전체 화면"><Icon name="i-expand" /></button>
      </div>
      {lyrOpen && (
        <div className="lyr">
          <b style={{ fontSize: 12, color: 'var(--t2)' }}>원본 레이어</b>
          {LAYER_NAMES.map(([k, n, c]) => (
            <label key={k}><input type="checkbox" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} /><i style={{ background: c }} />{n}</label>
          ))}
          <label style={{ opacity: 0.55 }}><input type="checkbox" disabled /><i style={{ background: '#7C3AED' }} />AI 후보 오버레이 · P1</label>
        </div>
      )}
      <div className="legend">
        <span><i className="dot" style={{ background: 'var(--cad-pipe)' }} />냉매 배관</span>
        <span><svg width="10" height="10"><rect x="1.5" y="1.5" width="7" height="7" transform="rotate(45 5 5)" fill="var(--cad-br)" /></svg>분기</span>
        <span><svg width="12" height="12"><circle cx="6" cy="6" r="4" fill="#fff" stroke="var(--cad-pipe)" strokeWidth="2" /></svg>단순 교차</span>
        <span><i className="dot" style={{ background: 'var(--cad-unit)', borderRadius: 2 }} />실내기</span>
        <span><i className="dot" style={{ background: 'var(--cad-sel)' }} />선택</span>
        <span style={{ color: 'var(--t2)' }}>점선 = 보류</span>
      </div>
      {children}
    </div>
  );
}

function Arch({ sample }: { sample: boolean }) {
  const L = (k: string, a: number, b: number, c: number, d: number) => <line key={k} x1={a} y1={b} x2={c} y2={d} stroke="#BDB6B0" strokeWidth="3" />;
  const rooms: [number, number, string][] = sample
    ? [[135, 90, '강의실 501'], [325, 90, '강의실 502'], [515, 90, '강의실 503'], [695, 90, '연구실 504'], [870, 90, '연구실 505'], [150, 620, '강의실 506'], [365, 620, '세미나실'], [585, 620, '강의실 508'], [830, 620, '강의실 509']]
    : [];
  return (
    <g className="arch">
      <rect className="w" x="40" y="40" width="920" height="620" fill="none" stroke="#BDB6B0" strokeWidth="6" />
      {L('c1', 40, 330, 960, 330)}
      {L('c2', 40, 400, 960, 400)}
      {[230, 420, 610, 780].map((x) => L(`u${x}`, x, 40, x, 330))}
      {[260, 470, 700].map((x) => L(`d${x}`, x, 400, x, 660))}
      {[120, 320, 510, 690, 860].map((x) => <rect key={`a${x}`} className="d" x={x} y="326" width="40" height="8" />)}
      {[140, 360, 580, 820].map((x) => <rect key={`b${x}`} className="d" x={x} y="396" width="40" height="8" />)}
      {rooms.map(([x, y, t]) => <text key={t} className="lbl" x={x} y={y} textAnchor="middle" style={{ fontWeight: 500, fill: '#8b848a' }}>{t}</text>)}
    </g>
  );
}
