import type { HoldCode, Layer, LayerRole, PlanNode, ReferenceTotals, ReviewItem } from '../contracts';
import { seeded } from '../../lib/util';

/**
 * MockApiAdapter 전용 시연 데이터.
 * - 기본 샘플: 기존 웹사이트의 '인하대 OAC-5-1' 가상 교육용 도면 (T03 기준값은 실도면 기준, 구간 상세는 가상)
 * - 다른 파일을 올리면 파일 이름 · 크기로 시드를 만들어 계통 · 구간 · 길이가 달라지는 가상 결과를 만듭니다.
 * 모든 결과는 isDemo: true 입니다.
 */

export const SAMPLE_DRAWING = 'INHA_M-501_B.dwg';

export const T03_REFERENCE: ReferenceTotals = {
  planCount: 24, planTotalM: 105.51532, treeSegments: 21, treeTotalM: 109.4, longestM: 53.6,
  label: 'T03 기준 · 인하대 OAC-5-1 실도면',
};

const SAMPLE_NODES: PlanNode[] = [
  { id: 'OU', label: 'OAC-5-1', kind: 'OU', x: 86, y: 365 },
  { id: 'B1', label: 'BR-1', kind: 'BRANCH', x: 150, y: 365 },
  { id: 'B2', label: 'BR-2', kind: 'BRANCH', x: 320, y: 365 },
  { id: 'B3', label: 'BR-3', kind: 'BRANCH', x: 510, y: 365 },
  { id: 'B4', label: 'BR-4', kind: 'BRANCH', x: 580, y: 365 },
  { id: 'B5', label: 'BR-5', kind: 'BRANCH', x: 690, y: 365 },
  { id: 'B6', label: 'BR-6', kind: 'BRANCH', x: 820, y: 365 },
  { id: 'I501', label: 'IDU-501', kind: 'IDU', x: 150, y: 190 },
  { id: 'I506', label: 'IDU-506', kind: 'IDU', x: 150, y: 520 },
  { id: 'I502', label: 'IDU-502', kind: 'IDU', x: 320, y: 190 },
  { id: 'I507', label: 'IDU-507', kind: 'IDU', x: 320, y: 520 },
  { id: 'I503', label: 'IDU-503', kind: 'IDU', x: 510, y: 190 },
  { id: 'I508', label: 'IDU-508', kind: 'IDU', x: 580, y: 530 },
  { id: 'I504', label: 'IDU-504', kind: 'IDU', x: 690, y: 190 },
  { id: 'I509', label: 'IDU-509', kind: 'IDU', x: 820, y: 530 },
  { id: 'I505', label: 'IDU-505', kind: 'IDU', x: 880, y: 190 },
];

type SegSpec = [string, string, string, string, number, ReviewItem['status'], HoldCode?, string?, string?, [number, number][]?];
const SAMPLE_SEG: SegSpec[] = [
  ['S01', 'OU', 'B1', '15.88/9.52', 1.6, 'CONFIRMED'], ['S02', 'B1', 'I501', '9.52/6.35', 4.4, 'CONFIRMED'],
  ['S03', 'B1', 'I506', '9.52/6.35', 3.9, 'CONFIRMED'], ['S04', 'B1', 'B2', '15.88/9.52', 4.25, 'CONFIRMED'],
  ['S05', 'B2', 'I502', '9.52/6.35', 4.4, 'PENDING'], ['S06', 'B2', 'I507', '9.52/6.35', 3.9, 'CONFIRMED'],
  ['S07', 'B2', 'B3', '15.88/9.52', 4.75, 'HELD', 'NO_VERTICAL_EVIDENCE', '수직 길이 근거 없음', '층간 입상 구간 · 층고표 등 근거 필요'],
  ['S08', 'B3', 'I503', '9.52/6.35', 4.4, 'PENDING'], ['S09', 'B3', 'B4', '12.70/6.35', 1.75, 'CONFIRMED'],
  ['S10', 'B4', 'I508', '9.52/6.35', 4.15, 'PENDING'], ['S11', 'B4', 'B5', '12.70/6.35', 2.75, 'PENDING'],
  ['S12', 'B5', 'I504', '9.52/6.35', 4.4, 'HELD', 'NO_SCALE_EVIDENCE', '축척 근거 없음', '도면 축척 표기 확인 필요'],
  ['S13', 'B5', 'B6', '12.70/6.35', 3.25, 'PENDING'], ['S14', 'B6', 'I509', '9.52/6.35', 4.15, 'PENDING'],
  ['S15', 'B6', 'I505', '9.52/6.35', 5.9, 'HELD', 'DIAMETER_UNCLEAR', '관경 표기 불명확', '지시선 연결이 불확실 · 원본 확인 필요', [[820, 365], [880, 365], [880, 190]]],
];
const HANDLES = ['1A07', '1A2C', '1B40', '2F31', '2F3A', '2F44', '2F52', '3C10', '3C18', '3D02', '3D11', '4A05', '4A19', '4B22', '4B30'];

export const DEFAULT_LAYERS: Layer[] = [
  { name: 'M-REF-PIPE', entityCount: 412, textSample: 'Ø15.88/9.52', role: 'REFRIGERANT_PIPE', previewColor: '#0E7490' },
  { name: 'M-REF-BR', entityCount: 38, textSample: 'Y-BRANCH', role: 'BRANCH_FITTING', previewColor: '#C2410C' },
  { name: 'M-UNIT-TAG', entityCount: 26, textSample: 'OAC-5-1, IDU-501', role: 'UNIT_LABEL', previewColor: '#1D4ED8' },
  { name: 'M-PIPE-TXT', entityCount: 64, textSample: 'L=4.2m', role: 'PIPE_TAG', previewColor: '#4b4650' },
  { name: 'A-ROOM', entityCount: 18, textSample: '강의실 501', role: 'ROOM_NAME', previewColor: '#8b848a' },
  { name: 'A-WALL', entityCount: 1204, textSample: '—', role: 'ARCH_BACKGROUND', previewColor: '#BDB6B0' },
  { name: 'A-DIM', entityCount: 140, textSample: '3800', role: 'ANNOTATION', previewColor: '#9ca3af' },
  { name: 'TB-SHEET', entityCount: 22, textSample: '인하대학교 M-501', role: 'TITLE_BLOCK', previewColor: '#9ca3af' },
  { name: '0', entityCount: 73, textSample: '참조', role: 'UNKNOWN', previewColor: '#d4a017' },
];

export interface MockPlan { systemName: string; nodes: PlanNode[]; items: ReviewItem[]; layers: Layer[]; reference: ReferenceTotals | null }

function item(spec: SegSpec, i: number, systemId: string): ReviewItem {
  const [itemId, from, to, dia, len, status, holdCode, holdReason, holdNote, points] = spec;
  return {
    itemId, systemId, from, to, diameterMm: dia, planLengthM: len, verticalLengthM: null, adoptedLengthM: status === 'CONFIRMED' ? len : null,
    lengthType: '평면 계산값', status, holdCode: holdCode ?? null, holdReason: holdReason ?? '', holdNote: holdNote ?? '', shdRequired: true,
    sourceRef: { handle: HANDLES[i % HANDLES.length], layer: 'M-REF-PIPE', x: 0, y: 0 }, points,
    history: [{ who: 'Python Worker', what: '판독 · 평면 계산값 산출', at: '판독 시' }, ...(status === 'HELD' ? [{ who: 'Agent 검산', what: `보류 · ${holdReason}`, at: '판독 시' }] : [])],
  };
}

/** 파일마다 다른 가상 계통을 만듭니다. 기본 샘플 파일이면 기존 사이트 데이터 그대로. */
export function buildPlan(drawingName: string, sizeBytes: number, roles?: Record<string, LayerRole>): MockPlan {
  const isSample = drawingName === SAMPLE_DRAWING;
  const layers = DEFAULT_LAYERS.map((l) => ({ ...l, role: roles?.[l.name] ?? l.role }));
  if (isSample) {
    return { systemName: 'OAC-5-1', nodes: SAMPLE_NODES, items: SAMPLE_SEG.map((s, i) => item(s, i, 'SYS-1')), layers, reference: T03_REFERENCE };
  }
  const r = seeded(drawingName + ':' + sizeBytes);
  const branches = 4 + Math.floor(r() * 3); // 4~6
  const tag = (drawingName.replace(/\.[^.]+$/, '').replace(/[^A-Za-z0-9]/g, '').slice(0, 4).toUpperCase() || 'NEW') + '-1';
  const nodes: PlanNode[] = [{ id: 'OU', label: `OAC-${tag}`, kind: 'OU', x: 86, y: 365 }];
  const specs: SegSpec[] = [];
  let prev = 'OU';
  let x = 150;
  let n = 1;
  const scale = 0.022 + r() * 0.008; // m per px (가상)
  for (let b = 1; b <= branches; b++) {
    const id = `B${b}`;
    nodes.push({ id, label: `BR-${b}`, kind: 'BRANCH', x, y: 365 });
    const prevNode = nodes.find((p) => p.id === prev)!;
    specs.push([`S${String(n++).padStart(2, '0')}`, prev, id, b < 3 ? '15.88/9.52' : '12.70/6.35', +((x - prevNode.x) * scale).toFixed(2), 'PENDING']);
    const up = r() > 0.15;
    const down = r() > 0.35 || !up;
    if (up) {
      const iid = `I${b}U`;
      nodes.push({ id: iid, label: `IDU-${100 + b * 2 - 1}`, kind: 'IDU', x, y: 190 });
      specs.push([`S${String(n++).padStart(2, '0')}`, id, iid, '9.52/6.35', +(175 * scale).toFixed(2), 'PENDING']);
    }
    if (down) {
      const iid = `I${b}D`;
      const y = 515 + Math.round(r() * 20);
      nodes.push({ id: iid, label: `IDU-${100 + b * 2}`, kind: 'IDU', x, y });
      specs.push([`S${String(n++).padStart(2, '0')}`, id, iid, '9.52/6.35', +((y - 365) * scale).toFixed(2), 'PENDING']);
    }
    prev = id;
    x += Math.round((820 - 150) / Math.max(1, branches - 1) * (0.85 + r() * 0.3));
    x = Math.min(x, 860);
  }
  // 근거 부족 항목은 보류로 남김 (설계서: 단위 · 축척 · 수직 근거가 없으면 보류 유지)
  const heldIdx = [1 + Math.floor(r() * (specs.length - 1)), Math.floor(r() * specs.length)];
  heldIdx.forEach((hi, k) => {
    const s = specs[hi];
    if (!s) return;
    s[5] = 'HELD';
    s[6] = k === 0 ? 'NO_VERTICAL_EVIDENCE' : 'NO_SCALE_EVIDENCE';
    s[7] = k === 0 ? '수직 길이 근거 없음' : '축척 근거 없음';
    s[8] = k === 0 ? '층간 입상 구간 · 층고표 등 근거 필요' : '도면 축척 표기 확인 필요';
  });
  return { systemName: `OAC-${tag}`, nodes, items: specs.map((s, i) => item(s, i, 'SYS-1')), layers, reference: null };
}
