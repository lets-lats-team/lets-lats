import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/adapter';
import { ApiError, type ExportFormat, type MissingRequiredItem } from '../../api/contracts';
import { Badge, Info, Modal } from '../../components/ui';
import { Guide } from '../../components/Shell';
import { Icon } from '../../components/Sprite';
import { useExportJob } from '../../hooks/queries';
import { go } from '../../lib/router';
import { newRequestId, safeStorage } from '../../lib/util';
import { useUi } from '../../store/uiStore';
import { useReviewReady } from '../review/ReviewPage';

const FMT: [ExportFormat, string, boolean][] = [['SHD', 'P0 · 시험', true], ['SHDX', 'P0 · 실물 확인 전', true], ['CSV', 'P1 · 준비 중', false], ['PDF', 'P2 · 준비 중', false]];
/** 작업별 마지막 exportId (새로고침 후 출력 상태 복원) */
const lastExport = safeStorage<Record<string, string>>('letslats-last-export', {});

export function ExportsPage() {
  const { projectId, a, block } = useReviewReady();
  const { role, setRole, select, notify } = useUi();
  const [fmt, setFmt] = useState<ExportFormat>('SHD');
  const [tv, setTv] = useState('1.9.13.23');
  const [exportId, setExportId] = useState<string | null>(() => (projectId ? lastExport.get()[projectId] ?? null : null));
  const [missing422, setMissing422] = useState<MissingRequiredItem[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [verOpen, setVerOpen] = useState<string | null>(null);
  const job = useExportJob(exportId);
  const verifierList = useQuery({ queryKey: ['verifier-exports'], queryFn: () => api.listVerifierExports(), enabled: role === 'VERIFIER' });

  if (block || !a) return <section className="view"><Guide view="exports" />{block}</section>;

  const sys = a.systems[0];
  const missing = a.reviewItems.filter((i) => i.systemId === sys?.systemId && i.shdRequired && i.status !== 'CONFIRMED');
  const e = job.data;

  const gen = async () => {
    if (!tv.trim()) return notify('targetVersion이 필요합니다 (400)');
    setBusy(true);
    setMissing422(null);
    try {
      const r = await api.createExport(a.analysisId, { systemId: sys.systemId, reviewVersion: a.reviewVersion, format: fmt, targetVersion: tv.trim(), requestId: newRequestId() });
      setExportId(r.exportId);
      lastExport.set({ ...lastExport.get(), [projectId!]: r.exportId });
      void api.sendEvent({ name: 'export_requested', projectId: projectId!, analysisId: a.analysisId, at: new Date().toISOString(), props: { format: fmt } });
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && err.details?.missing) setMissing422(err.details.missing);
      else notify((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const goItem = (id: string) => {
    select(id);
    go('review', projectId);
  };
  const download = () => {
    if (e?.downloadUrl) window.open(e.downloadUrl, '_blank', 'noopener');
    else notify('Mock 모드라 실제 파일이 없습니다. 연동 시 A07 READY의 서명 GET URL로 다운로드됩니다.');
  };
  const list = missing422 ?? (fmt === 'SHD' || fmt === 'SHDX' ? missing.map((i) => ({ itemId: i.itemId, status: i.status, reason: i.holdReason || '확인 필요' })) : []);

  return (
    <section className="view">
      <Guide view="exports" />
      <div className="vh">
        <div>
          <h1>산출물 · LATS 실물 검증</h1>
          <p>UI-04 · A06 → A07 폴링 · A07A / A08A / A08 (VERIFIER)</p>
        </div>
        <span className="sp" />
        <label className="row mut13">역할
          <select style={{ width: 'auto' }} value={role} onChange={(ev) => setRole(ev.target.value as 'USER' | 'VERIFIER')}>
            <option value="USER">USER</option><option value="VERIFIER">VERIFIER</option>
          </select>
        </label>
      </div>
      <div className="grid2">
        <div className="card pad20 stack16">
          <label className="f">계통<select>{a.systems.map((s) => <option key={s.systemId}>{s.name}</option>)}</select></label>
          <div>
            <div className="fs13 b700" style={{ marginBottom: 6 }}>출력 형식</div>
            <div className="fmt">
              {FMT.map(([f, l, ok]) => <button key={f} aria-pressed={fmt === f} disabled={!ok} onClick={() => setFmt(f)}><b>{f}</b><small>{l}</small></button>)}
            </div>
          </div>
          <div className="grid2 g12">
            <label className="f">targetVersion<input type="text" value={tv} onChange={(ev) => setTv(ev.target.value)} /><small>Windows 북미판 LATS HVAC</small></label>
            <label className="f">검토 버전<input type="text" value={`v${a.reviewVersion}`} readOnly /></label>
          </div>
          {list.length ? (
            <div className="info err" style={{ margin: 0, display: 'block' }}>
              <div className="row" style={{ marginBottom: 8 }}><Icon name="i-alert" /><b>422 · 미확정 필수 항목 {list.length}개 — SHD/SHDX를 만들 수 없어요</b></div>
              <div className="stack4">
                {list.map((m) => (
                  <div key={m.itemId} className="row fs13">
                    <b className="num">{m.itemId}</b><Badge s={m.status} /><span className="mut13" style={{ flex: 1 }}>{m.reason}</span>
                    <button className="btn b-ghost sm" style={{ minHeight: 30 }} onClick={() => goItem(m.itemId)}>구간으로 이동</button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <Info kind="ok" style={{ margin: 0 }}>shd_required 항목이 모두 확정되었습니다. 출력할 수 있어요.</Info>
          )}
          <button className="btn b-pri" onClick={gen} disabled={busy || (!!e && ['QUEUED', 'RUNNING'].includes(e.state))}>출력 생성 (A06)</button>
        </div>
        <div className="stack14">
          <div className="card pad20">
            <div className="row" style={{ marginBottom: 12 }}><b style={{ flex: 1 }}>출력 상태</b>{e ? <Badge s={e.state} /> : <span className="mut13">아직 없음</span>}</div>
            {e ? (
              <>
                <dl className="kv">
                  <dt>exportId</dt><dd>{e.exportId}</dd>
                  <dt>형식 · targetVersion</dt><dd>{e.format} · {e.targetVersion}</dd>
                  <dt>출력 시점 검토 버전</dt><dd>v{e.reviewVersion}</dd>
                  <dt>SHA-256</dt><dd>{e.sha256 ? e.sha256.slice(0, 12) + '…' : '—'}</dd>
                </dl>
                {e.state === 'READY' && e.reviewVersion !== a.reviewVersion && <Info kind="warn" style={{ margin: '12px 0 0' }}>출력 시점 v{e.reviewVersion} · 이후 v{a.reviewVersion}로 수정됨 — 재생성 권장</Info>}
                <button className="btn b-sec sm" style={{ marginTop: 12, width: '100%' }} disabled={e.state !== 'READY'} onClick={download}><Icon name="i-down" />다운로드 (A07 서명 GET URL)</button>
                {e.isDemo && <div className="mut12" style={{ marginTop: 8 }}>Mock 모드: 실제 SHD 파일은 생성하지 않습니다.</div>}
              </>
            ) : <div className="mut13">분석 상태와 출력 상태(QUEUED · RUNNING · READY · FAILED)는 따로 표시됩니다.</div>}
          </div>
          <div className="card pad20">
            <div className="row" style={{ marginBottom: 10 }}><b style={{ flex: 1 }}>LATS 실물 검증</b><Badge s={e?.latsCheck.status ?? 'UNVERIFIED'} /></div>
            <div className="mut13" style={{ marginBottom: 12 }}>대상: Windows 북미판 LATS HVAC 1.9.13.23 · SHDX 지원과 국내판 적용은 실물 확인 전입니다. PASS는 서버에 등록된 검증 기록이 있을 때만 표시되고, 해시가 다른 파일에는 적용되지 않습니다.</div>
            <div className="vstep">
              <div><b>Import CAD</b>{fmtStep(e?.latsCheck.steps?.importCad)}</div>
              <div><b>LATS HVAC 저장 · 재열기</b>{fmtStep(e?.latsCheck.steps?.saveReopen)}</div>
              <div><b>System Check</b>{fmtStep(e?.latsCheck.steps?.systemCheck)}</div>
            </div>
            {role === 'VERIFIER' ? (
              <div className="verbox">
                <b className="fs13">VERIFIER · 검증 대상 (A07A)</b>
                {verifierList.data?.length ? verifierList.data.map((x) => (
                  <div key={x.exportId} className="row fs13"><span className="num" style={{ flex: 1 }}>{x.exportId} · {x.format} · v{x.reviewVersion}</span><Badge s={x.state} /><button className="btn b-ghost sm" style={{ minHeight: 30 }} disabled={x.state !== 'READY'} onClick={() => setVerOpen(x.exportId)}>결과 등록</button></div>
                )) : <div className="mut12">검증할 SHD/SHDX 출력이 없습니다.</div>}
                <div className="mut12">권한 판단은 서버가 합니다. 이 화면의 역할 전환은 확인용입니다.</div>
              </div>
            ) : <div className="mut12" style={{ marginTop: 12 }}>검증 등록은 VERIFIER 전용입니다.</div>}
          </div>
        </div>
      </div>
      <VerifyModal exportId={verOpen} sha={verifierList.data?.find((x) => x.exportId === verOpen)?.sha256 ?? ''} onClose={() => setVerOpen(null)} />
    </section>
  );
}

const fmtStep = (v: boolean | null | undefined) => (v == null ? '미실행' : v ? '통과' : '실패');

function VerifyModal({ exportId, sha, onClose }: { exportId: string | null; sha: string; onClose: () => void }) {
  const notify = useUi((s) => s.notify);
  const [app, setApp] = useState('1.9.13.23');
  const [file, setFile] = useState<File | null>(null);
  const [steps, setSteps] = useState({ importCad: true, saveReopen: true, systemCheck: true });
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    if (!exportId) return;
    setErr(null);
    try {
      let evidenceKey: string | undefined;
      if (file) {
        const t = await api.requestEvidenceUpload(exportId, file.name); // A08A
        await api.putFile(t, file, () => undefined);
        evidenceKey = t.objectKey;
      }
      await api.submitLatsCheck(exportId, { appVersion: app, sha256: sha, steps, evidenceKey }); // A08
      notify('검증 결과를 등록했습니다');
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  return (
    <Modal open={!!exportId} onClose={onClose} label="검증 결과 등록">
      <h2>LATS 실물 검증 결과 등록</h2>
      <p>Windows LATS HVAC에서 직접 시험한 결과만 등록하세요. 등록된 기록은 같은 SHA-256 파일에만 적용됩니다.</p>
      <div className="stack14">
        <div className="grid2 g12">
          <label className="f">앱 버전<input type="text" value={app} onChange={(e) => setApp(e.target.value)} /></label>
          <label className="f">SHA-256<input type="text" value={sha ? sha.slice(0, 16) + '…' : ''} readOnly /></label>
        </div>
        {(['importCad', 'saveReopen', 'systemCheck'] as const).map((k) => (
          <label key={k} className="row fs13"><input type="checkbox" checked={steps[k]} onChange={(e) => setSteps({ ...steps, [k]: e.target.checked })} />{{ importCad: 'Import CAD 통과', saveReopen: 'LATS HVAC 저장 · 재열기 통과', systemCheck: 'System Check 통과' }[k]}</label>
        ))}
        <label className="f">근거 파일<input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        {err && <Info kind="err" style={{ margin: 0 }}>{err}</Info>}
      </div>
      <div className="mact">
        <button className="btn b-ghost sm" onClick={onClose}>취소</button>
        <button className="btn b-pri sm" onClick={submit}>등록 (A08A → A08)</button>
      </div>
    </Modal>
  );
}
