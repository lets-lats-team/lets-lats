import { useState } from 'react';
import type { ReviewStatus } from '../../api/contracts';
import { Badge } from '../../components/ui';
import { Guide } from '../../components/Shell';
import { Icon } from '../../components/Sprite';
import { go } from '../../lib/router';
import { useUi } from '../../store/uiStore';
import { counts, useReviewReady } from '../review/ReviewPage';

type Tab = 'seg' | 'eq' | 'log';

export function PipeTablePage() {
  const { projectId, a, block } = useReviewReady();
  const select = useUi((s) => s.select);
  const [tab, setTab] = useState<Tab>('seg');
  const [f, setF] = useState<'ALL' | ReviewStatus>('ALL');
  if (block || !a) return <section className="view"><Guide view="table" />{block}</section>;

  const nodes = Object.fromEntries(a.nodes.map((n) => [n.id, n]));
  const c = counts(a.reviewItems);
  const rows = a.reviewItems.filter((i) => f === 'ALL' || i.status === f);
  const open = (id: string) => {
    select(id);
    go('review', projectId);
  };
  const log = a.reviewItems.flatMap((it) => it.history.filter((h) => h.who !== 'Python Worker' && h.who !== 'Agent 검산').map((h) => ({ ...h, id: it.itemId }))).reverse();

  return (
    <section className="view">
      <Guide view="table" />
      <div className="vh">
        <div>
          <h1>배관 상세표</h1>
          <p>계통 {a.systems[0]?.name} · 행을 누르면 계통 · 도면에서 해당 구간으로 이동합니다{a.isDemo ? ' · T03 기준값 외 구간 상세는 가상 상세 데이터' : ''}</p>
        </div>
        <span className="sp" />
        <button className="btn b-sec sm" onClick={() => go('review', projectId)}><Icon name="i-branch" />도면으로 돌아가기</button>
      </div>
      <div className="card toolbar">
        <div className="chips">
          {([['seg', '배관'], ['eq', '장비'], ['log', '변경 이력']] as [Tab, string][]).map(([k, l]) => <button key={k} className="chip" aria-pressed={tab === k} onClick={() => setTab(k)}>{l}</button>)}
        </div>
        <span style={{ flex: 1 }} />
        {tab === 'seg' && (
          <div className="chips">
            {(['ALL', 'PENDING', 'HELD', 'CONFIRMED'] as const).map((k) => (
              <button key={k} className="chip" aria-pressed={f === k} onClick={() => setF(k)}>{{ ALL: '전체', PENDING: '미확인', HELD: '보류', CONFIRMED: '확정' }[k]} {k === 'ALL' ? a.reviewItems.length : c[k]}</button>
            ))}
          </div>
        )}
      </div>

      {tab === 'seg' && (
        <>
          <div className="card hide-m" style={{ overflow: 'auto' }}>
            <table className="t">
              <thead><tr><th>구간</th><th>시작 → 끝</th><th>관경 (mm)</th><th className="r">평면 (m)</th><th className="r">수직 보정 (m)</th><th className="r">채택값 (m)</th><th>길이 종류</th><th>원본</th><th>상태</th></tr></thead>
              <tbody>
                {rows.map((it) => (
                  <tr key={it.itemId} onClick={() => open(it.itemId)}>
                    <td className="num"><b>{it.itemId}</b></td>
                    <td>{nodes[it.from]?.label} → {nodes[it.to]?.label}</td>
                    <td className="num">Ø{it.diameterMm}</td>
                    <td className="r num">{it.planLengthM.toFixed(2)}</td>
                    <td className="r num">{it.verticalLengthM?.toFixed(2) ?? '—'}</td>
                    <td className="r num">{it.adoptedLengthM?.toFixed(2) ?? '—'}</td>
                    <td>{it.lengthType}</td>
                    <td className="num">{it.sourceRef.handle}</td>
                    <td><Badge s={it.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mcards show-m">
            {rows.map((it) => (
              <button key={it.itemId} className="mcard" onClick={() => open(it.itemId)}>
                <span className="mcard-h"><b className="num">{it.itemId} · {nodes[it.from]?.label} → {nodes[it.to]?.label}</b><Badge s={it.status} /></span>
                <span className="mkv">
                  <span>관경<b className="num">Ø{it.diameterMm}</b></span>
                  <span>평면<b className="num">{it.planLengthM.toFixed(2)} m</b></span>
                  <span>수직 보정<b className="num">{it.verticalLengthM?.toFixed(2) ?? '—'}</b></span>
                  <span>채택값<b className="num">{it.adoptedLengthM?.toFixed(2) ?? '—'}</b></span>
                </span>
                {it.status === 'HELD' && <span className="mut12" style={{ color: 'var(--warn)' }}>보류 · {it.holdReason}</span>}
              </button>
            ))}
          </div>
        </>
      )}
      {tab === 'eq' && (
        <div className="card" style={{ overflow: 'auto' }}>
          <table className="t">
            <thead><tr><th>태그</th><th>종류</th><th>모델</th><th className="r">수량</th><th>연결 구간</th></tr></thead>
            <tbody>
              {a.nodes.filter((n) => n.kind !== 'BRANCH').map((n) => (
                <tr key={n.id}>
                  <td className="num"><b>{n.label}</b></td><td>{n.kind === 'OU' ? '실외기' : '실내기'}</td>
                  <td className="mut13">{n.model ?? (n.kind === 'OU' ? '모델 확인 필요' : '4WAY 카세트 (가상)')}</td>
                  <td className="r num">1</td>
                  <td className="num">{a.reviewItems.filter((s) => s.from === n.id || s.to === n.id).map((s) => s.itemId).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === 'log' && (
        <div className="card" style={{ overflow: 'auto' }}>
          {log.length ? (
            <table className="t">
              <thead><tr><th>구간</th><th>행동</th><th>담당</th><th>시각</th></tr></thead>
              <tbody>{log.map((l, i) => <tr key={i} onClick={() => open(l.id)}><td className="num">{l.id}</td><td>{l.what}</td><td>{l.who}</td><td className="num">{l.at}</td></tr>)}</tbody>
            </table>
          ) : <div className="mut13" style={{ padding: 18 }}>아직 변경 이력이 없습니다. 구간을 수정 · 확정 · 보류하면 버전과 함께 기록됩니다.</div>}
        </div>
      )}
    </section>
  );
}
