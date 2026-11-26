import type { ApiAdapter } from '../adapter';
import {
  ApiError, type Analysis, type AnalysisErrorCode, type AppEvent, type CreateExportBody, type CreateProjectBody,
  type DocumentMeta, type ExportJob, type LatsCheckBody, type LayerRole, type MissingRequiredItem, type Project,
  type RegisterDocumentBody, type ReviewItem, type ReviewPatchBody, type StartAnalysisBody, type UploadRequestBody,
  type UploadTicket,
} from '../contracts';
import { buildPlan, SAMPLE_DRAWING } from './data';
import { newId, nowLabel, safeStorage, seeded, sleep } from '../../lib/util';

/**
 * MockApiAdapter — 서버 없이 화면 흐름을 확인하기 위한 어댑터.
 * - 데이터는 localStorage에 저장되어 새로고침 후에도 남습니다.
 * - 분석 · 출력 진행 상태는 시작 시각 기준으로 계산하므로 폴링 중 새로고침해도 이어집니다.
 * - 모든 결과에 isDemo: true. 파일은 서버로 전송되지 않습니다.
 */

interface StoredAnalysis {
  analysisId: string;
  projectId: string;
  requestId: string;
  drawingName: string;
  drawingSize: number;
  layerRoles: Record<string, LayerRole> | null;
  fail: AnalysisErrorCode | null;
  startedAt: number;
  /** REVIEW 이후 검토 결과 (A05로 갱신) */
  items: ReviewItem[] | null;
  reviewVersion: number;
}
interface StoredExport extends Omit<ExportJob, 'state' | 'sha256'> { startedAt: number; sha: string }
interface DB {
  v: 2;
  projects: Record<string, Project>;
  analyses: Record<string, StoredAnalysis>;
  files: Record<string, { fileName: string; sizeBytes: number }>;
  exports: Record<string, StoredExport>;
  requests: Record<string, string>; // requestId → 결과 id (중복 요청 방지)
}

const store = safeStorage<DB | null>('letslats-mock-db-v2', null);
const T = { queued: 1100, convert: 2400, extract: 3600 };

function seedDb(): DB {
  const now = Date.now();
  const iso = (msAgo: number) => new Date(now - msAgo).toISOString();
  const db: DB = { v: 2, projects: {}, analyses: {}, files: {}, exports: {}, requests: {} };
  const mk = (id: string, name: string, site: string, rev: string, floor: string, scope: Project['scope'], drawing: string, size: number, ago: number, roles: boolean, fail: AnalysisErrorCode | null, startedAgo: number) => {
    const docId = `doc_${id}`;
    const anId = `an_${id}`;
    db.projects[id] = {
      projectId: id, name, siteKey: site, revision: rev, floor, scope, unit: 'mm · 1:100', aiEnabled: false,
      drawing: { documentId: docId, fileName: drawing, sizeBytes: size, role: 'DRAWING', objectKey: `mock/${id}/${drawing}` },
      documents: [], latestAnalysisId: anId, state: 'REVIEW', stageLabel: '', updatedAt: iso(ago), isDemo: true,
    };
    db.analyses[anId] = {
      analysisId: anId, projectId: id, requestId: `req_seed_${id}`, drawingName: drawing, drawingSize: size,
      layerRoles: roles ? {} : null, fail, startedAt: now - startedAgo, items: null, reviewVersion: 1,
    };
  };
  mk('p_inha', '인하대 공조 교체 · OAC-5-1', 'INHA-2026', 'B', '5F', '설치', SAMPLE_DRAWING, 4.8e6, 6e5, true, null, 6e5);
  mk('p_a', 'A동 냉매배관 평면도', 'SAMPLE-A', 'A', '3F', '설치', 'A동_냉매배관_A.dxf', 2.1e6, 6e4, false, null, -60_000);
  mk('p_b', 'B동 설비도면 재등록', 'SAMPLE-B', 'C', '', '설치', 'B동_설비도면_C.dwg', 5.2e6, 864e5, false, 'DWG_CONVERSION_FAILED', 864e5);
  mk('p_c', 'C동 교체 공사 (철거)', 'SAMPLE-C', 'A', '2F', '철거', 'C동_교체_A.dwg', 3.3e6, 2592e5, false, null, 2592e5);
  return db;
}

function load(): DB {
  const db = store.get();
  if (db && db.v === 2) return db;
  const fresh = seedDb();
  store.set(fresh);
  return fresh;
}
const save = (db: DB) => store.set(db);
const latency = () => sleep(120 + Math.random() * 180);

function materialize(sa: StoredAnalysis): Analysis {
  const el = Date.now() - sa.startedAt;
  const plan = buildPlan(sa.drawingName, sa.drawingSize, sa.layerRoles ?? undefined);
  const base: Analysis = {
    analysisId: sa.analysisId, projectId: sa.projectId, requestId: sa.requestId, state: 'QUEUED', stage: 'UPLOADED', errorCode: null,
    layers: [], layerRolesApplied: !!sa.layerRoles, systems: [], nodes: [], reviewItems: [], reviewVersion: sa.reviewVersion,
    compareVersion: sa.reviewVersion, reference: null, isDemo: true, createdAt: new Date(sa.startedAt).toISOString(),
  };
  if (el < T.queued) return base;
  if (el < T.convert) return { ...base, state: 'RUNNING', stage: 'CONVERTING' };
  if (sa.fail) return { ...base, state: 'FAILED', stage: 'CONVERTING', errorCode: sa.fail };
  if (el < T.extract) return { ...base, state: 'RUNNING', stage: 'EXTRACTING' };
  if (!sa.layerRoles) return { ...base, state: 'REVIEW', stage: 'LAYER_ROLES', layers: plan.layers };
  const items = sa.items ?? plan.items;
  return {
    ...base, state: 'REVIEW', stage: 'SYSTEM_REVIEW', layers: plan.layers, nodes: plan.nodes, reviewItems: items, reference: plan.reference,
    systems: [{ systemId: 'SYS-1', name: plan.systemName, segmentCount: items.length, indoorCount: plan.nodes.filter((n) => n.kind === 'IDU').length }],
  };
}

function summarize(db: DB, p: Project): Project {
  const sa = p.latestAnalysisId ? db.analyses[p.latestAnalysisId] : null;
  if (!sa) return { ...p, state: 'DRAFT', stageLabel: p.drawing ? '도면 등록 · 판독 전' : '작성 중' };
  const a = materialize(sa);
  const label = a.state === 'QUEUED' ? '대기열' : a.state === 'RUNNING' ? (a.stage === 'CONVERTING' ? '판독 중 · DWG 변환' : '판독 중 · 레이어 추출')
    : a.state === 'FAILED' ? 'DWG 변환 실패' : a.stage === 'LAYER_ROLES' ? '역할 지정 대기' : '검토 대기';
  return { ...p, state: a.state, stageLabel: label };
}

const hex = (seedText: string) => {
  const r = seeded(seedText);
  return Array.from({ length: 64 }, () => Math.floor(r() * 16).toString(16)).join('');
};

export class MockApiAdapter implements ApiAdapter {
  readonly mode = 'mock' as const;
  /** 시연 옵션: 다음 판독을 DWG 변환 실패로 */
  failNext = false;
  /** 시연 옵션: 다음 A05 저장에서 409 */
  conflictNext = false;

  async listProjects() {
    await latency();
    const db = load();
    return Object.values(db.projects).map((p) => summarize(db, p)).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }
  async getProject(projectId: string) {
    await latency();
    const db = load();
    const p = db.projects[projectId];
    if (!p) throw new ApiError(404, 'NOT_FOUND', '작업을 찾을 수 없습니다.');
    return summarize(db, p);
  }
  async createProject(body: CreateProjectBody) {
    await latency();
    if (!body.name.trim()) throw new ApiError(400, 'NAME_REQUIRED', '작업명을 입력해 주세요.');
    const db = load();
    const id = newId('p');
    db.projects[id] = {
      projectId: id, name: body.name.trim(), siteKey: body.siteKey ?? '', revision: '', floor: '', scope: '설치', unit: 'mm · 1:100',
      aiEnabled: body.aiEnabled, drawing: null, documents: [], latestAnalysisId: null, state: 'DRAFT', stageLabel: '작성 중',
      updatedAt: new Date().toISOString(), isDemo: true,
    };
    save(db);
    return db.projects[id];
  }
  async updateProject(projectId: string, patch: Partial<Project>) {
    await latency();
    const db = load();
    const p = db.projects[projectId];
    if (!p) throw new ApiError(404, 'NOT_FOUND', '작업을 찾을 수 없습니다.');
    db.projects[projectId] = { ...p, ...patch, projectId, updatedAt: new Date().toISOString() };
    save(db);
    return summarize(db, db.projects[projectId]);
  }
  async requestUpload(projectId: string, body: UploadRequestBody): Promise<UploadTicket> {
    await latency();
    const ext = body.fileName.split('.').pop()?.toLowerCase() ?? '';
    if (body.role === 'DRAWING' && !['dwg', 'dxf'].includes(ext)) throw new ApiError(415, 'UNSUPPORTED_DRAWING', '설비 도면은 DWG 또는 DXF만 등록할 수 있습니다.');
    if (body.sizeBytes > 200 * 1048576) throw new ApiError(400, 'FILE_TOO_LARGE', '파일이 너무 큽니다 (최대 200MB).');
    const objectKey = `mock/${projectId}/${Date.now()}_${body.fileName}`;
    const db = load();
    db.files[objectKey] = { fileName: body.fileName, sizeBytes: body.sizeBytes };
    save(db);
    return { objectKey, putUrl: `mock://s3/${objectKey}` };
  }
  async putFile(_t: UploadTicket, _file: File, onProgress: (pct: number) => void, signal?: AbortSignal) {
    for (let p = 0; p < 100; ) {
      await sleep(160, signal);
      p = Math.min(100, p + 18 + Math.round(Math.random() * 14));
      onProgress(p);
    }
  }
  async registerDocument(projectId: string, body: RegisterDocumentBody): Promise<DocumentMeta> {
    await latency();
    const db = load();
    const p = db.projects[projectId];
    if (!p) throw new ApiError(404, 'NOT_FOUND', '작업을 찾을 수 없습니다.');
    const dupe = db.requests[body.requestId];
    if (dupe) return [p.drawing, ...p.documents].find((d) => d?.documentId === dupe)!;
    const ext = body.fileName.split('.').pop()?.toLowerCase();
    const doc: DocumentMeta = {
      documentId: newId('doc'), fileName: body.fileName, sizeBytes: body.sizeBytes, role: body.role, objectKey: body.objectKey,
      conversionHint: ext === 'xls' ? 'XLS는 지원하지 않습니다 · XLSX로 변환해 주세요' : ext === 'hwp' ? '암호화 HWP일 수 있습니다 · HWPX 또는 텍스트 PDF 권장' : undefined,
    };
    if (body.role === 'DRAWING') p.drawing = doc;
    else p.documents = [...p.documents.filter((d) => d.fileName !== doc.fileName), doc];
    p.updatedAt = new Date().toISOString();
    db.requests[body.requestId] = doc.documentId;
    save(db);
    return doc;
  }
  async startAnalysis(projectId: string, body: StartAnalysisBody) {
    await latency();
    const db = load();
    const p = db.projects[projectId];
    if (!p) throw new ApiError(404, 'NOT_FOUND', '작업을 찾을 수 없습니다.');
    if (!p.drawing || p.drawing.documentId !== body.drawingId) throw new ApiError(400, 'USER_FILE_REQUIRED', '설비 도면(DWG/DXF)을 먼저 등록해 주세요.');
    const dupe = db.requests[body.requestId];
    if (dupe) return { analysisId: dupe };
    const id = newId('an');
    const fail: AnalysisErrorCode | null = this.failNext || /fail|실패/i.test(p.drawing.fileName) ? 'DWG_CONVERSION_FAILED' : null;
    this.failNext = false;
    db.analyses[id] = {
      analysisId: id, projectId, requestId: body.requestId, drawingName: p.drawing.fileName, drawingSize: p.drawing.sizeBytes,
      layerRoles: body.layerRoles ?? null, fail, startedAt: Date.now() - (body.layerRoles ? T.extract - 1500 : 0), items: null, reviewVersion: 1,
    };
    p.latestAnalysisId = id;
    p.updatedAt = new Date().toISOString();
    db.requests[body.requestId] = id;
    save(db);
    return { analysisId: id };
  }
  async getAnalysis(analysisId: string, signal?: AbortSignal) {
    await sleep(100 + Math.random() * 120, signal);
    const sa = load().analyses[analysisId];
    if (!sa) throw new ApiError(404, 'NOT_FOUND', '분석을 찾을 수 없습니다.');
    return materialize(sa);
  }
  async saveReviews(analysisId: string, body: ReviewPatchBody) {
    await latency();
    const db = load();
    const sa = db.analyses[analysisId];
    if (!sa) throw new ApiError(404, 'NOT_FOUND', '분석을 찾을 수 없습니다.');
    const current = materialize(sa);
    if (current.stage !== 'SYSTEM_REVIEW') throw new ApiError(422, 'NOT_REVIEWABLE', '계통 분석이 끝난 뒤 검토할 수 있습니다.');
    if (this.conflictNext) {
      // 다른 담당자가 먼저 저장한 상황을 만듭니다.
      this.conflictNext = false;
      const items = current.reviewItems.map((it) => (it.itemId === body.items[0]?.itemId ? { ...it, history: [...it.history, { who: '김담당', what: `메모 추가 · v${sa.reviewVersion + 1}`, at: nowLabel() }] } : it));
      sa.items = items;
      sa.reviewVersion += 1;
      save(db);
      throw new ApiError(409, 'REVIEW_VERSION_CONFLICT', '다른 담당자가 먼저 저장했습니다.', { latest: materialize(sa) });
    }
    if (body.reviewVersion !== sa.reviewVersion) throw new ApiError(409, 'REVIEW_VERSION_CONFLICT', '검토 버전이 최신이 아닙니다.', { latest: current });
    const next = sa.reviewVersion + 1;
    const at = nowLabel();
    const items = current.reviewItems.map((it) => {
      const ops = body.items.filter((o) => o.itemId === it.itemId);
      let n = { ...it, history: [...it.history] };
      for (const o of ops) {
        if (o.action === 'CONFIRM') {
          if (n.status === 'HELD' && n.verticalLengthM == null && n.adoptedLengthM == null) throw new ApiError(422, 'EVIDENCE_REQUIRED', `${n.itemId}: 근거 없이 확정할 수 없습니다.`);
          n = { ...n, status: 'CONFIRMED', adoptedLengthM: n.adoptedLengthM ?? n.planLengthM };
          n.history.push({ who: body.actor, what: `확정 · v${next}`, at });
        } else if (o.action === 'HOLD') {
          n = { ...n, status: 'HELD', holdReason: o.reason ?? n.holdReason ?? '근거 부족', holdNote: o.evidence ?? n.holdNote };
          n.history.push({ who: body.actor, what: `보류 · ${n.holdReason}`, at });
        } else if (o.action === 'EDIT') {
          if (!(o.value && o.value > 0)) throw new ApiError(400, 'INVALID_VALUE', '0보다 큰 값을 입력해 주세요.');
          if (!o.reason?.trim()) throw new ApiError(400, 'REASON_REQUIRED', '수정 근거를 입력해 주세요.');
          n = o.valueKind === 'VERTICAL' ? { ...n, verticalLengthM: o.value, lengthType: '수직 보정값' } : { ...n, adoptedLengthM: o.value };
          if (n.status === 'HELD') n = { ...n, status: 'PENDING', holdCode: null, holdReason: '' };
          n.history.push({ who: body.actor, what: `수정 · ${o.valueKind === 'VERTICAL' ? '수직 보정값' : '채택값'} ${o.value.toFixed(2)} m · ${o.evidence ?? ''} · “${o.reason}”`, at });
        }
        n.updatedBy = body.actor;
        n.updatedAt = at;
      }
      return n;
    });
    sa.items = items;
    sa.reviewVersion = next;
    db.projects[sa.projectId].updatedAt = new Date().toISOString();
    save(db);
    return materialize(sa);
  }
  async createExport(analysisId: string, body: CreateExportBody) {
    await latency();
    const db = load();
    const sa = db.analyses[analysisId];
    if (!sa) throw new ApiError(404, 'NOT_FOUND', '분석을 찾을 수 없습니다.');
    if (body.format === 'CSV' || body.format === 'PDF') throw new ApiError(400, 'FORMAT_NOT_READY', `${body.format} 출력은 아직 준비 중입니다 (P1 · P2).`);
    if (!body.targetVersion.trim()) throw new ApiError(400, 'TARGET_VERSION_REQUIRED', 'targetVersion이 필요합니다.');
    const a = materialize(sa);
    const missing: MissingRequiredItem[] = a.reviewItems
      .filter((i) => i.systemId === body.systemId && i.shdRequired && i.status !== 'CONFIRMED')
      .map((i) => ({ itemId: i.itemId, status: i.status, reason: i.holdReason || '확인 필요' }));
    if (missing.length) throw new ApiError(422, 'SHD_REQUIRED_UNCONFIRMED', `미확정 필수 항목 ${missing.length}개`, { missing });
    const dupe = db.requests[body.requestId];
    if (dupe) return { exportId: dupe };
    const id = newId('ex');
    db.exports[id] = {
      exportId: id, analysisId, systemId: body.systemId, format: body.format, reviewVersion: body.reviewVersion, targetVersion: body.targetVersion,
      downloadUrl: null, latsCheck: { status: 'UNVERIFIED' }, isDemo: true, createdAt: new Date().toISOString(), startedAt: Date.now(), sha: hex(id),
    };
    db.requests[body.requestId] = id;
    save(db);
    return { exportId: id };
  }
  async getExport(exportId: string, signal?: AbortSignal): Promise<ExportJob> {
    await sleep(100, signal);
    const e = load().exports[exportId];
    if (!e) throw new ApiError(404, 'NOT_FOUND', '출력을 찾을 수 없습니다.');
    const el = Date.now() - e.startedAt;
    const state = el < 900 ? 'QUEUED' : el < 2300 ? 'RUNNING' : 'READY';
    const { startedAt: _s, sha, ...rest } = e;
    return { ...rest, state, sha256: state === 'READY' ? sha : null };
  }
  async listVerifierExports() {
    await latency();
    const ids = Object.keys(load().exports);
    return Promise.all(ids.map((id) => this.getExport(id)));
  }
  async requestEvidenceUpload(exportId: string, fileName: string) {
    await latency();
    return { objectKey: `mock/evidence/${exportId}/${fileName}`, putUrl: 'mock://s3' };
  }
  async submitLatsCheck(_exportId: string, _body: LatsCheckBody): Promise<ExportJob> {
    await latency();
    throw new ApiError(422, 'MOCK_NO_LATS_RECORD', 'Mock 모드에서는 Windows LATS 실물 시험 기록을 등록하지 않습니다. PASS · FAIL은 서버에 등록된 기록이 있을 때만 표시됩니다.');
  }
  async sendEvent(event: AppEvent) {
    const log = safeStorage<AppEvent[]>('letslats-mock-events', []);
    log.set([...log.get().slice(-199), event]);
  }
}
