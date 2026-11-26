import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/adapter';
import { ApiError, HTTP_GUIDE, type DocumentMeta, type DocumentRole, type Project } from '../../api/contracts';
import { MockApiAdapter } from '../../api/mock/mockAdapter';
import { Badge, Empty, ErrorBox, Info, Skeleton } from '../../components/ui';
import { Guide } from '../../components/Shell';
import { Icon } from '../../components/Sprite';
import { useCurrent } from '../../hooks/useCurrent';
import { qk } from '../../hooks/queries';
import { go } from '../../lib/router';
import { fmtMB, newRequestId } from '../../lib/util';
import { useUi } from '../../store/uiStore';

interface UploadRow { key: string; fileName: string; sizeBytes: number; role: DocumentRole; pct: number; error?: string; doc?: DocumentMeta }

const STAGES: [string, string][] = [['QUEUED', '작업 대기열 등록'], ['CONVERTING', 'DWG → DXF 변환'], ['EXTRACTING', '레이어 · 개체 추출'], ['LAYER_ROLES', 'LAYER_ROLES · 역할 지정 대기']];

export function RegisterPage() {
  const { projectId, project, analysis } = useCurrent();
  const qc = useQueryClient();
  const { setDirty, dirty, notify } = useUi();
  const p = project.data;
  const [form, setForm] = useState<Pick<Project, 'name' | 'siteKey' | 'revision' | 'floor' | 'scope' | 'unit' | 'aiEnabled'> | null>(null);
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const formFor = useRef<string | null>(null);

  // 작업이 바뀌면 폼을 서버 값으로 다시 채움 (입력 중에는 덮어쓰지 않음)
  useEffect(() => {
    if (p && formFor.current !== p.projectId) {
      formFor.current = p.projectId;
      setForm({ name: p.name, siteKey: p.siteKey, revision: p.revision, floor: p.floor, scope: p.scope, unit: p.unit, aiEnabled: p.aiEnabled });
      setUploads([]);
      setDirty(false);
    }
  }, [p, setDirty]);

  // 저장 안 한 상태로 창을 닫으려 하면 확인
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => {
      if (useUi.getState().dirty) e.preventDefault();
    };
    addEventListener('beforeunload', h);
    return () => removeEventListener('beforeunload', h);
  }, []);

  const set = <K extends keyof NonNullable<typeof form>>(k: K, v: NonNullable<typeof form>[K]) => {
    setForm((f) => (f ? { ...f, [k]: v } : f));
    setDirty(true);
  };

  const refresh = async () => {
    await Promise.all([qc.invalidateQueries({ queryKey: qk.project(projectId!) }), qc.invalidateQueries({ queryKey: qk.projects })]);
  };

  const save = async () => {
    if (!form || !projectId) return false;
    if (!form.name.trim()) {
      notify('작업명을 입력해 주세요');
      return false;
    }
    if (uploads.some((u) => !u.error && u.pct < 100)) {
      notify('업로드가 끝난 뒤 저장해 주세요');
      return false;
    }
    setSaving(true);
    try {
      await api.updateProject(projectId, { ...form, name: form.name.trim() });
      await refresh();
      setDirty(false);
      notify('저장했어요 · 상단 작업명과 작업 목록에 반영했습니다');
      return true;
    } catch (e) {
      setErr(e);
      return false;
    } finally {
      setSaving(false);
    }
  };

  // Ctrl+S
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        void save();
      }
    };
    addEventListener('keydown', k);
    return () => removeEventListener('keydown', k);
  });

  const upload = async (file: File, role: DocumentRole) => {
    if (!projectId) return;
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (role === 'DRAWING' && !['dwg', 'dxf'].includes(ext)) {
      notify('설비 도면은 DWG 또는 DXF만 등록할 수 있습니다 (415)');
      return;
    }
    const row: UploadRow = { key: `${role}:${file.name}:${Date.now()}`, fileName: file.name, sizeBytes: file.size, role, pct: 0 };
    setUploads((u) => [...u.filter((x) => !(role === 'DRAWING' && x.role === 'DRAWING')), row]);
    const patch = (r: Partial<UploadRow>) => setUploads((u) => u.map((x) => (x.key === row.key ? { ...x, ...r } : x)));
    const requestId = newRequestId(); // 재전송 시 같은 ID 유지
    try {
      const ticket = await api.requestUpload(projectId, { fileName: file.name, contentType: file.type || 'application/octet-stream', sizeBytes: file.size, role });
      await api.putFile(ticket, file, (pct) => patch({ pct }));
      const doc = await api.registerDocument(projectId, { objectKey: ticket.objectKey, fileName: file.name, role, sizeBytes: file.size, revision: form?.revision, scope: form?.scope, requestId });
      patch({ pct: 100, doc, error: doc.conversionHint });
      await refresh();
    } catch (e) {
      patch({ error: e instanceof ApiError ? `${e.message}${HTTP_GUIDE[e.status] ? ' · ' + HTTP_GUIDE[e.status] : ''}` : (e as Error).message });
    }
  };

  const start = async (fail = false) => {
    if (!p || !projectId) return;
    if (dirty && !(await save())) return;
    if (!p.drawing) {
      notify('설비 도면(DWG/DXF)을 먼저 등록해 주세요');
      return;
    }
    if (fail && api instanceof MockApiAdapter) api.failNext = true;
    setStarting(true);
    setErr(null);
    try {
      // 사용자의 명시적 재실행 → 새 requestId (원본 · 이전 분석 · 검토 이력은 서버에 보존)
      await api.startAnalysis(projectId, { drawingId: p.drawing.documentId, documentIds: p.documents.map((d) => d.documentId), floor: form?.floor, unit: form?.unit, requestId: newRequestId() });
      await refresh();
      void api.sendEvent({ name: 'analysis_started', projectId, at: new Date().toISOString() });
    } catch (e) {
      setErr(e);
    } finally {
      setStarting(false);
    }
  };

  if (!projectId) {
    return (
      <section className="view">
        <Empty title="열린 작업이 없습니다.">
          <button className="btn b-pri sm" style={{ marginTop: 10 }} onClick={() => go('projects')}>작업 목록으로</button>
        </Empty>
      </section>
    );
  }
  if (project.isLoading || !form) return <section className="view"><Skeleton rows={6} /></section>;
  if (project.error) return <section className="view"><ErrorBox error={project.error} onRetry={() => project.refetch()} /></section>;

  const a = analysis.data;
  const stageIdx = !a ? -1 : a.state === 'QUEUED' ? 0 : a.stage === 'CONVERTING' ? 1 : a.stage === 'EXTRACTING' ? 2 : 3;
  const running = a && (a.state === 'QUEUED' || a.state === 'RUNNING');
  const drawingRows = uploads.filter((u) => u.role === 'DRAWING');
  const docRows = uploads.filter((u) => u.role !== 'DRAWING');

  const saveBar = (
    <>
      <span className={`savest ${dirty ? 'dirty' : ''}`}><Icon name={dirty ? 'i-alert' : 'i-ok'} />{dirty ? '저장 안 됨' : '저장됨'}</span>
      <button className="btn b-pri sm" onClick={() => void save()} disabled={saving}><Icon name="i-check" />저장</button>
    </>
  );

  return (
    <section className="view">
      <Guide view="register" />
      <div className="vh">
        <div>
          <h1>작업 등록</h1>
          <p>UI-01 · A01 → A02A → S3 PUT → A02 → A03 → A04 · Ctrl+S로 저장</p>
        </div>
        <span className="sp" />
        {saveBar}
      </div>
      {err != null && <ErrorBox error={err} />}
      <div className="grid2">
        <div className="card pad20 stack14">
          <label className="f"><span>작업명<em>필수</em></span><input type="text" value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="예: 인하대 공조 교체 · OAC-5-1" /></label>
          <div className="grid2 g12">
            <label className="f">현장 식별값<input type="text" value={form.siteKey} onChange={(e) => set('siteKey', e.target.value)} placeholder="예: INHA-2026" /></label>
            <label className="f">개정본<input type="text" value={form.revision} onChange={(e) => set('revision', e.target.value)} placeholder="예: B" /></label>
          </div>
          <div className="grid2 g12">
            <label className="f">건물 · 층<input type="text" value={form.floor} onChange={(e) => set('floor', e.target.value)} placeholder="예: 5F" /></label>
            <label className="f">설치 / 철거
              <select value={form.scope} onChange={(e) => set('scope', e.target.value as Project['scope'])}>
                <option>설치</option><option>철거</option><option>설치 + 철거</option>
              </select>
            </label>
          </div>
          <label className="f">단위 · 축척
            <select value={form.unit} onChange={(e) => set('unit', e.target.value)}>
              <option>mm · 1:100</option><option>mm · 1:50</option><option>미확인 (길이 항목 보류)</option>
            </select>
            <small>근거가 없으면 길이 항목은 보류 상태로 유지됩니다.</small>
          </label>
          <div className="aibox">
            <div style={{ flex: 1 }}>
              <b>AI 외부 전송 동의</b>
              <div className="mut12">기본 OFF · A01 aiEnabled. 꺼도 P0 판독은 모두 사용할 수 있습니다. 동의 시 필요한 crop만 서버 워커가 외부 AI로 보냅니다.</div>
            </div>
            <button className="switch" role="switch" aria-checked={form.aiEnabled} aria-label="AI 외부 전송 동의" onClick={() => set('aiEnabled', !form.aiEnabled)} />
          </div>
          <div className="row-end">{saveBar}</div>
        </div>

        <div className="stack14">
          <div className="card pad20">
            <b>설비 도면</b> <span className="req">필수 · DWG/DXF 1개</span>
            <Drop icon="i-up" title="파일을 끌어 놓거나 선택" hint=".dwg · .dxf · 원본은 S3에 저장되고 서버 워커가 판독" accept=".dwg,.dxf" onFiles={(fs) => fs[0] && upload(fs[0], 'DRAWING')} />
            <div className="files">
              {drawingRows.length
                ? drawingRows.map((u) => <FileRow key={u.key} u={u} />)
                : p?.drawing
                  ? <FileRow u={{ key: 'saved', fileName: p.drawing.fileName, sizeBytes: p.drawing.sizeBytes, role: 'DRAWING', pct: 100, doc: p.drawing }} />
                  : <Info kind="warn" style={{ margin: 0 }}>설비 도면(DWG/DXF)을 추가해야 판독할 수 있습니다.</Info>}
            </div>
          </div>
          <div className="card pad20">
            <b>선택 문서</b> <span className="mut12">공내역서(XLSX/텍스트 PDF) · 시방서(텍스트 PDF/HWP/HWPX)</span>
            <Drop icon="i-file" title="문서 추가" hint="P2 문서 대조에 사용됩니다" accept=".xlsx,.xls,.pdf,.hwp,.hwpx" multiple onFiles={(fs) => fs.forEach((f) => upload(f, /xlsx?$/i.test(f.name) ? 'BOQ' : 'SPEC'))} />
            <div className="files">
              {docRows.map((u) => <FileRow key={u.key} u={u} />)}
              {!docRows.length && p?.documents.map((d) => <FileRow key={d.documentId} u={{ key: d.documentId, fileName: d.fileName, sizeBytes: d.sizeBytes, role: d.role, pct: 100, doc: d, error: d.conversionHint }} />)}
            </div>
          </div>
          <div className="card pad20">
            <div className="row" style={{ marginBottom: 8 }}>
              <b style={{ flex: 1 }}>판독</b>
              {a && (a.state === 'FAILED' ? <Badge s="FAILED" /> : <Badge s={a.state} text={a.stage === 'LAYER_ROLES' ? '역할 지정 대기' : a.stage === 'SYSTEM_REVIEW' ? '검토 대기' : undefined} />)}
              {a?.isDemo && <Badge s="DEMO" text="Mock 결과" />}
            </div>
            <ol className="stagel">
              {STAGES.map(([code, label], i) => {
                const failed = a?.state === 'FAILED' && i === 1;
                const st = !a ? '' : failed ? '' : i < stageIdx || a.stage === 'SYSTEM_REVIEW' ? 'done' : i === stageIdx ? 'now' : '';
                return (
                  <li key={code} className={st}>
                    <i>{st === 'done' ? <Icon name="i-check" style={{ width: 14 }} /> : failed ? <Icon name="i-xc" style={{ width: 14, color: 'var(--err)' }} /> : i + 1}</i>
                    {label}
                    <small>{code}</small>
                  </li>
                );
              })}
            </ol>
            <div className="mut13" style={{ margin: '8px 0 12px' }} aria-live="polite">
              {!a ? (p?.drawing ? '도면이 등록되었습니다. [판독 시작]을 누르세요.' : '설비 도면을 등록하면 판독을 시작할 수 있습니다.')
                : a.state === 'FAILED' ? <span style={{ color: 'var(--err)' }}><b>{a.errorCode}</b> · 같은 개정본의 DXF를 제출해 주세요. 원본 · 이전 분석 · 검토 이력은 보존됩니다.</span>
                : a.stage === 'LAYER_ROLES' ? <>첫 분석이 끝났습니다. 계통 분석 완료가 아니라 <b>레이어 역할 지정 대기</b> 상태입니다.</>
                : a.stage === 'SYSTEM_REVIEW' ? '계통 분석까지 끝났습니다. 계통 · 도면에서 검토하세요.'
                : <>서버가 준 stage만 표시합니다 · requestId <span className="num">{a.requestId}</span></>}
            </div>
            <div className="row wrap">
              <button className="btn b-pri sm" onClick={() => start()} disabled={!p?.drawing || !!running || starting}>
                {a?.state === 'FAILED' ? '다시 판독' : a ? '새로 판독' : '판독 시작'}
              </button>
              {api instanceof MockApiAdapter && <button className="btn b-ghost sm" onClick={() => start(true)} disabled={!p?.drawing || !!running}>실패 흐름 보기</button>}
              {a?.stage === 'LAYER_ROLES' && <button className="btn b-sec sm" onClick={() => go('layers', projectId)}>레이어 역할 지정으로 →</button>}
              {a?.stage === 'SYSTEM_REVIEW' && <button className="btn b-sec sm" onClick={() => go('review', projectId)}>계통 · 도면으로 →</button>}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Drop({ icon, title, hint, accept, multiple, onFiles }: { icon: string; title: string; hint: string; accept: string; multiple?: boolean; onFiles: (f: File[]) => void }) {
  const [over, setOver] = useState(false);
  return (
    <label
      className={`drop ${over ? 'over' : ''}`}
      style={{ marginTop: 10 }}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles([...e.dataTransfer.files]); }}
    >
      <span className="ic"><Icon name={icon} /></span>
      <span style={{ flex: 1 }}><b style={{ display: 'block' }}>{title}</b><span className="mut12">{hint}</span></span>
      <input type="file" accept={accept} multiple={multiple} hidden onChange={(e) => { onFiles([...(e.target.files ?? [])]); e.target.value = ''; }} />
    </label>
  );
}

function FileRow({ u }: { u: UploadRow }) {
  const roleLabel = u.role === 'DRAWING' ? '설비 도면' : u.role === 'BOQ' ? '공내역서' : '시방서';
  const bad = !!u.error && !u.doc;
  return (
    <div className="file">
      <span>
        <b>{u.fileName}</b> <span className="mut12">· {fmtMB(u.sizeBytes)} · {roleLabel}</span>
        {u.error && <><br /><span style={{ color: bad ? 'var(--err)' : 'var(--warn)', fontSize: 12 }}>{u.error}</span></>}
      </span>
      <span>
        {bad ? <Badge s="FAILED" text="업로드 실패" /> : u.pct < 100 ? <span className="num mut12">{u.pct}%</span> : <span style={{ fontSize: 12, color: 'var(--ok)', fontWeight: 700 }}>{api.mode === 'mock' ? '등록됨 · 서버 미전송(Mock)' : '등록됨'}</span>}
      </span>
      {!bad && <span className="pb"><i style={{ width: `${u.pct}%` }} /></span>}
    </div>
  );
}
