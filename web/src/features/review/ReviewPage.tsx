import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/adapter';
import { ApiError, type Analysis, type ReviewAction, type ReviewItem, type ReviewStatus } from '../../api/contracts';
import { MockApiAdapter } from '../../api/mock/mockAdapter';
import { SAMPLE_DRAWING } from '../../api/mock/data';
import { Badge, Empty, ErrorBox, Info, Modal, Skeleton } from '../../components/ui';
import { Guide } from '../../components/Shell';
import { Icon } from '../../components/Sprite';
import { useCurrent } from '../../hooks/useCurrent';
import { useSaveReviews } from '../../hooks/queries';
import { go } from '../../lib/router';
import { fmtM } from '../../lib/util';
import { useUi } from '../../store/uiStore';
import { CadViewer } from './CadViewer';

type Filter = 'ALL' | ReviewStatus;
const FILTERS: [Filter, string][] = [['ALL', '전체'], ['PENDING', '미확인'], ['HELD', '보류'], ['CONFIRMED', '확정']];
const DOT: Record<ReviewStatus, string> = { CONFIRMED: 'var(--ok)', PENDING: 'var(--neu)', HELD: 'var(--warn)' };

export function counts(items: ReviewItem[]) {
  const c = { CONFIRMED: 0, PENDING: 0, HELD: 0 } as Record<ReviewStatus, number>;
  items.forEach((i) => c[i.status]++);
  return c;
}

/** 검토 화면 공통 준비 상태 (계통 · 도면, 배관 상세표, 산출물에서 재사용) */
export function useReviewReady() {
  const cur = useCurrent();
  const a = cur.analysis.data;
  const block =
    !cur.projectId ? <Empty title="열린 작업이 없습니다."><button className="btn b-pri sm" style={{ marginTop: 10 }} onClick={() => go('projects')}>작업 목록으로</button></Empty>
    : cur.project.isLoading || cur.analysis.isLoading ? <Skeleton rows={6} />
    : cur.project.error ? <ErrorBox error={cur.project.error} onRetry={() => cur.project.refetch()} />
    : !a ? <Empty title="아직 분석이 없습니다.">작업 등록에서 판독을 시작하세요.<div><button className="btn b-pri sm" style={{ marginTop: 10 }} onClick={() => go('register', cur.projectId)}>작업 등록으로</button></div></Empty>
    : a.state === 'FAILED' ? <Info kind="err">판독이 실패했습니다 ({a.errorCode}). 작업 등록에서 같은 개정본 DXF로 다시 시도하세요.</Info>
    : a.state !== 'REVIEW' ? <Info>분석이 진행 중입니다 ({a.state} · {a.stage}). 완료되면 자동으로 열립니다.</Info>
    : a.stage === 'LAYER_ROLES' ? <Info kind="warn">레이어 역할을 지정해야 계통 분석이 시작됩니다.<div><button className="btn b-sec sm" style={{ marginTop: 8 }} onClick={() => go('layers', cur.projectId)}>레이어 역할 지정으로 →</button></div></Info>
    : null;
  return { ...cur, a: block ? null : a!, block };
}

export function ReviewPage() {
  const { projectId, project, a, block } = useReviewReady();
  const { selectedItemId, select, actorName, notify } = useUi();
  const save = useSaveReviews(a?.analysisId ?? null);
  const [filter, setFilter] = useState<Filter>('ALL');
  const [q, setQ] = useState('');
  const [focusKey, setFocusKey] = useState(0);
  const [mtab, setMtab] = useState<'list' | 'draw' | 'detail'>('draw');
  const [bulk, setBulk] = useState(false);
  const [conflict, setConflict] = useState<{ ops: ReviewAction[]; label: string; latest: Analysis } | null>(null);
  const [cfx, setCfx] = useState(false);

  const nodes = useMemo(() => Object.fromEntries((a?.nodes ?? []).map((n) => [n.id, n])), [a?.nodes]);
  const sel = a?.reviewItems.find((i) => i.itemId === selectedItemId) ?? null;

  useEffect(() => {
    if (a && (!selectedItemId || !a.reviewItems.some((i) => i.itemId === selectedItemId))) {
      select(a.reviewItems.find((i) => i.status === 'HELD')?.itemId ?? a.reviewItems[0]?.itemId ?? null);
    }
  }, [a, selectedItemId, select]);

  if (block || !a) return <section className="view"><Guide view="review" />{block}</section>;

  const c = counts(a.reviewItems);
  const items = a.reviewItems.filter((it) => (filter === 'ALL' || it.status === filter) && (!q || `${it.itemId}${nodes[it.from]?.label}${nodes[it.to]?.label}`.toUpperCase().includes(q.toUpperCase())));
  const pick = (id: string, move: boolean) => {
    select(id);
    if (move) setFocusKey((k) => k + 1);
  };

  const submit = async (ops: ReviewAction[], label: string, version = a.reviewVersion) => {
    if (cfx && api instanceof MockApiAdapter) {
      api.conflictNext = true;
      setCfx(false);
    }
    try {
      const next = await save.mutateAsync({ reviewVersion: version, items: ops, actor: actorName });
      notify(`${label} 저장 · review_version v${next.reviewVersion}`);
      void api.sendEvent({ name: 'review_saved', projectId: projectId!, analysisId: a.analysisId, at: new Date().toISOString(), props: { count: ops.length } });
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.details?.latest) setConflict({ ops, label, latest: e.details.latest });
      else notify(e instanceof Error ? e.message : '저장 실패');
      return false;
    }
  };

  const ref = a.reference;
  const sysName = a.systems[0]?.name ?? '-';
  const sample = project.data?.drawing?.fileName === SAMPLE_DRAWING;

  return (
    <section className="view" id="v-review">
      <div className="rv3" data-m={mtab}>
        <div className="rbar">
          <label className="row mut12">계통
            <select style={{ width: 'auto', padding: '6px 10px', fontWeight: 700 }} aria-label="계통 선택">
              {a.systems.map((s) => <option key={s.systemId}>{s.name} · {s.segmentCount}구간 · 실내기 {s.indoorCount}</option>)}
            </select>
          </label>
          <div className="prog">
            <div className="pbar">{(['CONFIRMED', 'PENDING', 'HELD'] as ReviewStatus[]).map((k) => <i key={k} style={{ flex: c[k] || 0.0001, background: DOT[k] }} />)}</div>
            <span className="num">확정 <b>{c.CONFIRMED}</b> · 미확인 {c.PENDING} · 보류 {c.HELD} / {a.reviewItems.length}</span>
          </div>
          {ref && (
            <div className="t03" title={ref.label}>
              <div>T03 기준</div>
              <div>평면 {ref.planCount}개<b>{ref.planTotalM} m</b></div>
              <div>선정 트리 {ref.treeSegments}구간<b>{ref.treeTotalM} m</b></div>
              <div>최장 실장<b>{ref.longestM} m</b></div>
            </div>
          )}
          <span style={{ flex: 1 }} />
          <button className="btn b-ghost sm" onClick={() => setBulk(true)}>계통 일괄 확정</button>
          <button className="btn b-ghost sm" onClick={() => go('table', projectId)}><Icon name="i-table" />배관 상세표</button>
          <button className="btn b-sec sm" onClick={() => go('exports', projectId)}>산출물 →</button>
        </div>
        <div className="mtabs">
          {(['list', 'draw', 'detail'] as const).map((m) => (
            <button key={m} className="chip" aria-pressed={mtab === m} onClick={() => setMtab(m)}>{{ list: '목록', draw: '도면', detail: '상세' }[m]}</button>
          ))}
        </div>
        <aside className="lp" aria-label="계통 트리">
          <div className="h">
            <input type="text" placeholder="구간 · 노드 · 장비 태그" value={q} onChange={(e) => setQ(e.target.value)} aria-label="트리 검색" />
            <div className="chips">
              {FILTERS.map(([k, l]) => <button key={k} className="chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>{l}{k === 'ALL' ? '' : ` ${c[k]}`}</button>)}
            </div>
          </div>
          <div className="tree">
            <div className="grp">실외기 계통 · {sysName}</div>
            {items.length ? items.map((it) => (
              <button key={it.itemId} className={`ti ${selectedItemId === it.itemId ? 'sel' : ''}`} onClick={() => { pick(it.itemId, true); if (innerWidth < 980) setMtab('detail'); }}>
                <span>
                  <b>{it.itemId}</b> <span style={{ display: 'inline', color: 'var(--t2)' }}>{nodes[it.from]?.label} → {nodes[it.to]?.label}</span>
                  <span>Ø{it.diameterMm} · {(it.adoptedLengthM ?? it.planLengthM).toFixed(2)} m · {it.lengthType}</span>
                </span>
                <span title={it.status}><i className="dot" style={{ background: DOT[it.status] }} /></span>
              </button>
            )) : <div className="mut13" style={{ padding: 20 }}>조건에 맞는 구간이 없습니다.</div>}
            <div className="grp">장비</div>
            {a.nodes.filter((n) => n.kind !== 'BRANCH').map((n) => (
              <button key={n.id} className="ti" onClick={() => { const s = a.reviewItems.find((i) => i.to === n.id); if (s) pick(s.itemId, true); }}>
                <span><b>{n.label}</b><span>{n.kind === 'OU' ? '실외기 · 모델 확인 필요' : '실내기 · 4WAY 카세트 (가상)'} · 수량 1</span></span><span />
              </button>
            ))}
          </div>
        </aside>
        <CadViewer analysis={a} selected={selectedItemId} onSelect={(id) => { pick(id, false); }} focusKey={focusKey} sample={sample}>
          <Guide view="review" float />
        </CadViewer>
        <aside className="rp" aria-label="상세 검토" aria-live="polite">
          {sel ? <Detail key={sel.itemId + a.reviewVersion} it={sel} a={a} nodes={nodes} onSave={submit} busy={save.isPending} cfx={cfx} setCfx={setCfx} onLocate={() => { setFocusKey((k) => k + 1); setMtab('draw'); }} /> : <div className="sec mut13">도면이나 목록에서 구간을 선택하세요.</div>}
        </aside>
      </div>

      <BulkModal open={bulk} onClose={() => setBulk(false)} a={a} nodes={nodes} onConfirm={async (ops) => { setBulk(false); await submit(ops, `${ops.length}개 일괄 확정`); }} />
      <Modal open={!!conflict} onClose={() => setConflict(null)} label="버전 충돌">
        {conflict && (
          <>
            <h2>다른 담당자가 먼저 저장했어요 (409)</h2>
            <p>서버 최신 버전은 <b className="num">v{conflict.latest.reviewVersion}</b>입니다. 최신값을 다시 불러왔고, 내 미저장 수정은 그대로 남아 있어요.</p>
            <div className="cmp">
              <div><small>서버 최신 · v{conflict.latest.reviewVersion}</small><b>{conflict.latest.reviewItems.find((i) => i.itemId === conflict.ops[0].itemId)?.history.slice(-1)[0]?.what ?? '—'}</b></div>
              <div className="ad"><small>내 변경 · 미저장</small><b>{conflict.label}</b><div className="mut12">{conflict.ops.map((o) => o.itemId).join(', ')}</div></div>
            </div>
            <div className="mact">
              <button className="btn b-ghost sm" onClick={() => { setConflict(null); notify('최신값 유지 · 내 변경은 취소했습니다'); }}>최신값 유지</button>
              <button className="btn b-pri sm" onClick={async () => { const c2 = conflict; setConflict(null); await submit(c2.ops, c2.label, c2.latest.reviewVersion); }}>최신 버전에 내 변경 반영</button>
            </div>
          </>
        )}
      </Modal>
    </section>
  );
}

function Detail({ it, a, nodes, onSave, busy, cfx, setCfx, onLocate }: {
  it: ReviewItem; a: Analysis; nodes: Record<string, { label: string }>; busy: boolean; cfx: boolean; setCfx: (v: boolean) => void; onLocate: () => void;
  onSave: (ops: ReviewAction[], label: string) => Promise<boolean>;
}) {
  const [mode, setMode] = useState<'EDIT' | 'HOLD' | null>(null);
  const [kind, setKind] = useState<'VERTICAL' | 'ADOPTED'>(it.holdCode === 'NO_VERTICAL_EVIDENCE' ? 'VERTICAL' : 'ADOPTED');
  const [val, setVal] = useState(it.holdCode === 'NO_VERTICAL_EVIDENCE' ? '7.60' : it.planLengthM.toFixed(2));
  const [ev, setEv] = useState('층고표 S-01 · 3.8 m × 2개 층');
  const [reason, setReason] = useState('');
  const canConfirm = !(it.status === 'HELD' && it.adoptedLengthM == null && it.verticalLengthM == null);
  const vert = it.verticalLengthM != null ? fmtM(it.verticalLengthM) : it.holdCode === 'NO_VERTICAL_EVIDENCE' ? '근거 필요' : '—';

  const submitForm = async () => {
    if (mode === 'EDIT') {
      const v = parseFloat(val);
      if (!(v > 0)) return alertMsg('0보다 큰 값을 입력하세요 (400)');
      if (!reason.trim()) return alertMsg('수정 근거를 입력해 주세요');
      if (await onSave([{ itemId: it.itemId, action: 'EDIT', valueKind: kind, value: v, evidence: ev, reason }], '수정')) setMode(null);
    } else if (mode === 'HOLD') {
      if (await onSave([{ itemId: it.itemId, action: 'HOLD', reason: ev, evidence: reason }], '보류')) setMode(null);
    }
  };
  const alertMsg = (m: string) => useUi.getState().notify(m);

  return (
    <>
      <div className="sec">
        <div className="row" style={{ marginBottom: 6 }}>
          <b className="num" style={{ fontSize: 18, flex: 1 }}>{it.itemId} · {nodes[it.from]?.label} → {nodes[it.to]?.label}</b>
          <Badge s={it.status} />
        </div>
        <div className="mut12">계통 {a.systems[0]?.name} · review_version v{a.reviewVersion} · shd_required {String(it.shdRequired)}</div>
      </div>
      {it.status === 'HELD' && (
        <div className="sec" style={{ background: 'var(--warnt)' }}>
          <b style={{ color: 'var(--warn)', fontSize: 13, display: 'flex', gap: 6, alignItems: 'center' }}><Icon name="i-hold" style={{ width: 15 }} />보류 사유 · {it.holdReason}</b>
          <div style={{ fontSize: 13, marginTop: 4 }}>{it.holdNote}</div>
        </div>
      )}
      <div className="sec">
        <h3>길이 종류별 값 · 합산하지 않음</h3>
        <dl className="kv">
          <dt>평면 계산값</dt><dd>{fmtM(it.planLengthM)}</dd>
          <dt>수직 보정값</dt><dd className={it.verticalLengthM == null ? 'mut' : ''}>{vert}</dd>
          <dt>설계 실장</dt><dd className="mut">—</dd>
          <dt>상당장</dt><dd className="mut">—</dd>
          <dt>현장 입력값</dt><dd className="mut">—</dd>
        </dl>
      </div>
      <div className="sec">
        <h3>원본값 · 채택값</h3>
        <div className="cmp">
          <div><small>원본값 (판독)</small><b>{fmtM(it.planLengthM)}</b></div>
          <div className="ad"><small>채택값</small><b>{it.adoptedLengthM != null ? fmtM(it.adoptedLengthM) : '미정'}</b></div>
        </div>
        {it.updatedBy && <div className="mut12" style={{ marginTop: 6 }}>수정 {it.updatedBy} · {it.updatedAt}</div>}
      </div>
      <div className="sec">
        <h3>배관 · 원본 근거</h3>
        <dl className="kv">
          <dt>관경 (mm)</dt><dd>Ø{it.diameterMm}</dd>
          <dt>원본 핸들</dt><dd>{it.sourceRef.handle}</dd>
          <dt>레이어</dt><dd>{it.sourceRef.layer}</dd>
        </dl>
        <button className="btn b-ghost sm" style={{ marginTop: 10, width: '100%' }} onClick={onLocate}><Icon name="i-pin" />도면에서 원본 위치 보기</button>
      </div>
      <div className="sec">
        <div className="acts">
          <button className="btn b-ghost sm" onClick={() => setMode(mode === 'EDIT' ? null : 'EDIT')}>수정</button>
          <button className="btn b-sec sm" onClick={() => setMode(mode === 'HOLD' ? null : 'HOLD')}>{it.status === 'HELD' ? '보류 유지' : '보류'}</button>
          <button className="btn b-pri sm" disabled={!canConfirm || it.status === 'CONFIRMED' || busy} title={canConfirm ? '' : '근거 입력 후 확정 가능'} onClick={() => onSave([{ itemId: it.itemId, action: 'CONFIRM' }], '확정')}>확정</button>
        </div>
        {!canConfirm && <div className="mut12" style={{ marginTop: 8 }}>근거가 없어 확정할 수 없습니다. [수정]에서 값과 근거를 입력하세요.</div>}
        {mode && (
          <div className="editbox">
            {mode === 'EDIT' ? (
              <>
                <label className="f">값 종류<select value={kind} onChange={(e) => setKind(e.target.value as 'VERTICAL' | 'ADOPTED')}><option value="VERTICAL">수직 보정값</option><option value="ADOPTED">채택값 (평면)</option></select></label>
                <label className="f">값 (m)<input type="number" step="0.01" value={val} onChange={(e) => setVal(e.target.value)} inputMode="decimal" /></label>
                <label className="f">근거<select value={ev} onChange={(e) => setEv(e.target.value)}><option>층고표 S-01 · 3.8 m × 2개 층</option><option>장비표 · 현장 확인</option><option>도면 치수 표기</option></select></label>
              </>
            ) : (
              <label className="f">보류 사유<select value={ev} onChange={(e) => setEv(e.target.value)}><option>{it.holdReason || '근거 부족'}</option><option>축척 근거 없음</option><option>현장 확인 필요</option></select></label>
            )}
            <label className="f">사유 메모<textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="수정 근거를 남겨 주세요" /></label>
            <div className="row">
              <button className="btn b-ghost sm" style={{ flex: 1 }} onClick={() => setMode(null)}>취소</button>
              <button className="btn b-pri sm" style={{ flex: 2 }} onClick={submitForm} disabled={busy}>저장 · v{a.reviewVersion} 기준</button>
            </div>
          </div>
        )}
      </div>
      <div className="sec">
        <h3>변경 이력</h3>
        <ul className="hist">{it.history.slice().reverse().map((h, i) => <li key={i}><span><b>{h.what}</b><span>{h.who} · {h.at}</span></span></li>)}</ul>
      </div>
      {api instanceof MockApiAdapter && (
        <div className="sec mut12"><label className="row"><input type="checkbox" checked={cfx} onChange={(e) => setCfx(e.target.checked)} />다음 저장 시 409 버전 충돌 시연 (Mock)</label></div>
      )}
    </>
  );
}

function BulkModal({ open, onClose, a, nodes, onConfirm }: { open: boolean; onClose: () => void; a: Analysis; nodes: Record<string, { label: string }>; onConfirm: (ops: ReviewAction[]) => void }) {
  const tgt = a.reviewItems.filter((i) => i.status === 'PENDING');
  const held = a.reviewItems.filter((i) => i.status === 'HELD');
  return (
    <Modal open={open} onClose={onClose} label="일괄 확정">
      <h2>{a.systems[0]?.name} 계통 일괄 확정</h2>
      <p>미확인 항목을 확정합니다. 보류 항목은 제외되며, 확정 전 대상과 제외 목록을 확인하세요.</p>
      <div className="grid3" style={{ marginBottom: 12 }}>
        <div className="kpi ok"><small>확정 대상</small><b className="num">{tgt.length}</b></div>
        <div className="kpi warn"><small>제외 · 보류</small><b className="num">{held.length}</b></div>
        <div className="kpi neu"><small>이미 확정</small><b className="num">{a.reviewItems.length - tgt.length - held.length}</b></div>
      </div>
      <div className="bulklist">
        {tgt.map((i) => <div key={i.itemId}><b className="num">{i.itemId}</b><span>{nodes[i.from]?.label} → {nodes[i.to]?.label}</span><em className="okc">확정 예정</em></div>)}
        {held.map((i) => <div key={i.itemId}><b className="num">{i.itemId}</b><span>{i.holdReason}</span><em className="warnc">제외</em></div>)}
      </div>
      <div className="mact">
        <button className="btn b-ghost sm" onClick={onClose}>취소</button>
        <button className="btn b-pri sm" disabled={!tgt.length} onClick={() => onConfirm(tgt.map((i) => ({ itemId: i.itemId, action: 'CONFIRM' })))}>{tgt.length}개 확정 (A05)</button>
      </div>
    </Modal>
  );
}
