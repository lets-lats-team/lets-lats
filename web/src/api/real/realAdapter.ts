import type { ApiAdapter } from '../adapter';
import {
  ApiError, type Analysis, type AppEvent, type CreateExportBody, type CreateProjectBody, type DocumentMeta,
  type ExportJob, type LatsCheckBody, type Project, type RegisterDocumentBody, type ReviewPatchBody,
  type StartAnalysisBody, type UploadRequestBody, type UploadTicket,
} from '../contracts';
import { safeStorage } from '../../lib/util';

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

/** 인증 방식은 미정(설계서 16장) → 토큰 공급자 자리만 둡니다. */
export let getAuthHeader: () => Record<string, string> = () => ({});
export function setAuthHeaderProvider(fn: () => Record<string, string>) {
  getAuthHeader = fn;
}

async function http<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method,
      signal,
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'NETWORK', '네트워크에 연결할 수 없습니다.');
  }
  if (!res.ok) {
    let payload: { code?: string; message?: string; details?: ApiError['details'] } = {};
    try {
      payload = await res.json();
    } catch {
      /* 본문 없음 */
    }
    throw new ApiError(res.status, payload.code ?? `HTTP_${res.status}`, payload.message ?? res.statusText, payload.details);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** UI-00 목록 API가 없어서, 이 브라우저에서 만든 projectId만 기억합니다. */
const knownIds = safeStorage<string[]>('letslats-real-projects', []);

export class RealApiAdapter implements ApiAdapter {
  readonly mode = 'real' as const;

  async listProjects(): Promise<Project[]> {
    const ids = knownIds.get();
    const out = await Promise.allSettled(ids.map((id) => this.getProject(id)));
    return out.flatMap((r) => (r.status === 'fulfilled' ? [r.value] : []));
  }
  /** Assumption: GET /api/projects/{id} (설계서 미정의) */
  getProject(projectId: string) {
    return http<Project>('GET', `/api/projects/${projectId}`);
  }
  async createProject(body: CreateProjectBody) {
    const p = await http<Project>('POST', '/api/projects', body);
    knownIds.set([p.projectId, ...knownIds.get().filter((x) => x !== p.projectId)]);
    return p;
  }
  /** Assumption: PATCH /api/projects/{id} (설계서 미정의) */
  updateProject(projectId: string, patch: Partial<Project>) {
    return http<Project>('PATCH', `/api/projects/${projectId}`, patch);
  }
  requestUpload(projectId: string, body: UploadRequestBody) {
    return http<UploadTicket>('POST', `/api/projects/${projectId}/uploads`, body);
  }
  putFile(ticket: UploadTicket, file: File, onProgress: (pct: number) => void, signal?: AbortSignal) {
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('PUT', ticket.putUrl);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
      xhr.onload = () => (xhr.status < 300 ? resolve() : reject(new ApiError(xhr.status, 'S3_PUT_FAILED', '파일 업로드에 실패했습니다.')));
      xhr.onerror = () => reject(new ApiError(0, 'NETWORK', '업로드 중 연결이 끊겼습니다.'));
      signal?.addEventListener('abort', () => xhr.abort());
      xhr.send(file);
    });
  }
  registerDocument(projectId: string, body: RegisterDocumentBody) {
    return http<DocumentMeta>('POST', `/api/projects/${projectId}/documents`, body);
  }
  startAnalysis(projectId: string, body: StartAnalysisBody) {
    return http<{ analysisId: string }>('POST', `/api/projects/${projectId}/analyses`, body);
  }
  getAnalysis(analysisId: string, signal?: AbortSignal) {
    return http<Analysis>('GET', `/api/analyses/${analysisId}`, undefined, signal);
  }
  saveReviews(analysisId: string, body: ReviewPatchBody) {
    return http<Analysis>('PATCH', `/api/analyses/${analysisId}/reviews`, body);
  }
  createExport(analysisId: string, body: CreateExportBody) {
    return http<{ exportId: string }>('POST', `/api/analyses/${analysisId}/exports`, body);
  }
  getExport(exportId: string, signal?: AbortSignal) {
    return http<ExportJob>('GET', `/api/exports/${exportId}`, undefined, signal);
  }
  listVerifierExports() {
    return http<ExportJob[]>('GET', '/api/exports?format=SHD,SHDX');
  }
  requestEvidenceUpload(exportId: string, fileName: string) {
    return http<UploadTicket>('POST', `/api/exports/${exportId}/lats-checks/uploads`, { fileName });
  }
  submitLatsCheck(exportId: string, body: LatsCheckBody) {
    return http<ExportJob>('POST', `/api/exports/${exportId}/lats-checks`, body);
  }
  async sendEvent(event: AppEvent) {
    try {
      await http<void>('POST', '/api/events', event);
    } catch {
      /* A09 실패는 무시 */
    }
  }
}
