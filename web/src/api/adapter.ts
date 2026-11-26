import type {
  Analysis, AppEvent, CreateExportBody, CreateProjectBody, DocumentMeta, ExportJob, LatsCheckBody, Project,
  RegisterDocumentBody, ReviewPatchBody, StartAnalysisBody, UploadRequestBody, UploadTicket,
} from './contracts';
import { MockApiAdapter } from './mock/mockAdapter';
import { RealApiAdapter } from './real/realAdapter';

/**
 * 화면은 이 인터페이스만 사용합니다. VITE_API_MODE로 Mock/Real을 바꿉니다.
 * 메서드 이름 옆 Axx는 설계서 API ID입니다.
 */
export interface ApiAdapter {
  readonly mode: 'mock' | 'real';

  /** UI-00. Assumption: 목록 API는 설계서에 없음 → real 모드에서도 브라우저 저장 목록 사용 */
  listProjects(): Promise<Project[]>;
  getProject(projectId: string): Promise<Project>;
  /** A01 */
  createProject(body: CreateProjectBody): Promise<Project>;
  /** Assumption: 작업 정보 수정 API는 미정 → 화면 저장용. 서버 계약 확정 시 교체 */
  updateProject(projectId: string, patch: Partial<Project>): Promise<Project>;
  /** A02A */
  requestUpload(projectId: string, body: UploadRequestBody): Promise<UploadTicket>;
  /** 서명 URL로 S3 직접 PUT */
  putFile(ticket: UploadTicket, file: File, onProgress: (pct: number) => void, signal?: AbortSignal): Promise<void>;
  /** A02 */
  registerDocument(projectId: string, body: RegisterDocumentBody): Promise<DocumentMeta>;
  /** A03 */
  startAnalysis(projectId: string, body: StartAnalysisBody): Promise<{ analysisId: string }>;
  /** A04 */
  getAnalysis(analysisId: string, signal?: AbortSignal): Promise<Analysis>;
  /** A05 — 버전 충돌이면 ApiError(409, details.latest) */
  saveReviews(analysisId: string, body: ReviewPatchBody): Promise<Analysis>;
  /** A06 — SHD/SHDX 필수 항목 미확정이면 ApiError(422, details.missing) */
  createExport(analysisId: string, body: CreateExportBody): Promise<{ exportId: string }>;
  /** A07 */
  getExport(exportId: string, signal?: AbortSignal): Promise<ExportJob>;
  /** A07A (VERIFIER) */
  listVerifierExports(): Promise<ExportJob[]>;
  /** A08A (VERIFIER) */
  requestEvidenceUpload(exportId: string, fileName: string): Promise<UploadTicket>;
  /** A08 (VERIFIER) */
  submitLatsCheck(exportId: string, body: LatsCheckBody): Promise<ExportJob>;
  /** A09 — 실패해도 업무는 계속 */
  sendEvent(event: AppEvent): Promise<void>;
}

const mode = (import.meta.env.VITE_API_MODE ?? 'mock') === 'real' ? 'real' : 'mock';
export const api: ApiAdapter = mode === 'real' ? new RealApiAdapter() : new MockApiAdapter();
