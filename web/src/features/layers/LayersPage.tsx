import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/adapter';
import { LAYER_ROLE_LABEL, type LayerRole } from '../../api/contracts';
import { Empty, ErrorBox, Info, Modal, Skeleton } from '../../components/ui';
import { Guide } from '../../components/Shell';
import { useCurrent } from '../../hooks/useCurrent';
import { qk } from '../../hooks/queries';
import { go } from '../../lib/router';
import { newRequestId } from '../../lib/util';
import { useUi } from '../../store/uiStore';

const ROLES = Object.keys(LAYER_ROLE_LABEL) as LayerRole[];

export function LayersPage() {
  const { projectId, project, analysis } = useCurrent();
  const qc = useQueryClient();
  const notify = useUi((s) => s.notify);
  const a = analysis.data;
  const [roles, setRoles] = useState<Record<string, LayerRole>>({});
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  useEffect(() => {
    if (a?.layers.length) setRoles(Object.fromEntries(a.layers.map((l) => [l.name, l.role])));
  }, [a?.analysisId, a?.layers]);

  if (!projectId) return <section className="view"><Empty title="열린 작업이 없습니다." /></section>;
  if (project.isLoading || analysis.isLoading) return <section className="view"><Skeleton rows={6} /></section>;
  if (!a) {
    return (
      <section className="view">
        <Empty title="아직 첫 분석이 없습니다.">
          작업 등록에서 도면을 올리고 판독을 시작하세요.
          <div><button className="btn b-pri sm" style={{ marginTop: 10 }} onClick={() => go('register', projectId)}>작업 등록으로</button></div>
        </Empty>
      </section>
    );
  }
  if (a.state !== 'REVIEW') {
    return (
      <section className="view">
        <Info kind={a.state === 'FAILED' ? 'err' : undefined}>
          {a.state === 'FAILED' ? '판독이 실패해서 레이어 목록이 없습니다. 작업 등록에서 원인을 확인하세요.' : '첫 분석이 진행 중입니다. 레이어 목록은 역할 지정 대기 단계에서 나타납니다.'}
        </Info>
        <button className="btn b-sec sm" onClick={() => go('register', projectId)}>작업 등록으로</button>
      </section>
    );
  }

  const unknown = Object.values(roles).filter((r) => r === 'UNKNOWN').length;
  const hasPipe = Object.values(roles).includes('REFRIGERANT_PIPE');

  const submit = async () => {
    const p = project.data;
    if (!p?.drawing) return;
    setBusy(true);
    setErr(null);
    try {
      // 역할 확정 · 수정은 항상 새 분석 (A03 + layerRoles). 이전 분석은 덮어쓰지 않음
      const r = await api.startAnalysis(projectId, { drawingId: p.drawing.documentId, documentIds: p.documents.map((d) => d.documentId), layerRoles: roles, requestId: newRequestId() });
      setConfirm(false);
      await qc.invalidateQueries({ queryKey: qk.project(projectId) });
      await qc.invalidateQueries({ queryKey: qk.projects });
      notify(`새 analysisId ${r.analysisId} · 계통 분석을 시작했습니다`);
      go('review', projectId);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="view">
      <Guide view="layers" />
      <div className="vh">
        <div>
          <h1>레이어 역할 지정</h1>
          <p>분석 <span className="num">{a.analysisId}</span> · REVIEW · {a.stage === 'LAYER_ROLES' ? 'LAYER_ROLES — 계통 분석 전 단계' : '역할 적용됨 · 수정하면 새 분석'}</p>
        </div>
        <span className="sp" />
        <button className="btn b-pri sm" onClick={() => (hasPipe ? setConfirm(true) : notify('냉매 배관 역할 레이어가 최소 1개 필요합니다'))}>
          역할 확정 · 새 분석 만들기
        </button>
      </div>
      <Info>레이어마다 역할을 지정하면 <b>layerRoles</b>를 포함해 A03으로 <b>새 분석</b>을 만듭니다. 이전 분석 결과는 덮어쓰지 않습니다. P0는 수동 지정이며, AI 자동 후보(L1)는 P1입니다.</Info>
      {err != null && <ErrorBox error={err} />}
      <div className="card hide-m" style={{ overflow: 'auto' }}>
        <table className="t">
          <thead><tr><th>레이어</th><th className="r">개체 수</th><th>글자 예시</th><th>미리보기</th><th style={{ width: 240 }}>역할</th></tr></thead>
          <tbody>
            {a.layers.map((l) => (
              <tr key={l.name}>
                <td><b className="num">{l.name}</b></td>
                <td className="r num">{l.entityCount.toLocaleString()}</td>
                <td className="mut13">“{l.textSample}”</td>
                <td><svg width="64" height="18"><line x1="2" y1="9" x2="62" y2="9" stroke={l.previewColor} strokeWidth="3" strokeDasharray={roles[l.name] === 'UNKNOWN' ? '4 3' : undefined} /></svg></td>
                <td><RoleSelect name={l.name} value={roles[l.name]} onChange={(v) => setRoles({ ...roles, [l.name]: v })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mcards show-m">
        {a.layers.map((l) => (
          <div key={l.name} className="mcard">
            <span className="mcard-h"><b className="num">{l.name}</b><span className="mut12 num">{l.entityCount.toLocaleString()}개</span></span>
            <span className="mut12">“{l.textSample}”</span>
            <RoleSelect name={l.name} value={roles[l.name]} onChange={(v) => setRoles({ ...roles, [l.name]: v })} />
          </div>
        ))}
      </div>
      <Modal open={confirm} onClose={() => setConfirm(false)} label="역할 확정">
        <h2>역할 확정 · 새 분석 만들기</h2>
        <p>layerRoles {a.layers.length}개를 포함해 A03으로 새 분석을 생성합니다. 이전 분석 <b className="num">{a.analysisId}</b>은 그대로 보존됩니다.{unknown ? ` 미지정 ${unknown}개 레이어는 판독에서 제외됩니다.` : ''}</p>
        <div className="mact">
          <button className="btn b-ghost sm" onClick={() => setConfirm(false)}>취소</button>
          <button className="btn b-pri sm" onClick={submit} disabled={busy}>새 분석 생성</button>
        </div>
      </Modal>
    </section>
  );
}

function RoleSelect({ name, value, onChange }: { name: string; value?: LayerRole; onChange: (v: LayerRole) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as LayerRole)} aria-label={`${name} 역할`} className={value === 'UNKNOWN' ? 'warnsel' : ''}>
      {ROLES.map((r) => <option key={r} value={r}>{LAYER_ROLE_LABEL[r]} · {r}</option>)}
    </select>
  );
}
