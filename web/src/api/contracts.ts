/**
 * LET'S LATS 프론트엔드 API 계약 (설계서_v3 · 기능 명세 v0.5 · DB 설계 v0.4 기준)
 *
 * - 이름이 정해진 API(A01~A09)와 상태값은 설계서 그대로 씁니다.
 * - 설계서에 상세 스키마가 없는 부분은 `Assumption:` 주석을 단 임시 타입입니다.
 *   백엔드와 확정되면 이 파일만 고치면 됩니다 (docs/API.md의 '협의 필요' 목록과 같음).
 */

/* ---------- 상태 ---------- */
export type AnalysisState = 'DRAFT' | 'QUEUED' | 'RUNNING' | 'REVIEW' | 'FAILED'; // DRAFT = 화면 전용
/** Assumption: stage 코드 목록은 설계서에 LAYER_ROLES만 명시. 나머지는 화면 표시용 임시값 */
export type AnalysisStage = 'UPLOADED' | 'CONVERTING' | 'EXTRACTING' | 'LAYER_ROLES' | 'SYSTEM_REVIEW' | 'OPTIONAL_DOC_FAILED';
export type AnalysisErrorCode = 'USER_FILE_REQUIRED' | 'RETRY_EXHAUSTED' | 'DWG_CONVERSION_FAILED';
export type ReviewStatus = 'PENDING' | 'CONFIRMED' | 'HELD';
export type ExportState = 'QUEUED' | 'RUNNING' | 'READY' | 'FAILED';
export type ExportFormat = 'SHD' | 'SHDX' | 'CSV' | 'PDF';
export type LatsCheckStatus = 'UNVERIFIED' | 'PASS' | 'FAIL';
export type CompareJudgement = 'MATCH' | 'DIFFERENT' | 'CONDITION_UNMET' | 'NOT_COMPARABLE';
export type UserRole = 'USER' | 'VERIFIER';

export type LayerRole =
  | 'REFRIGERANT_PIPE' | 'BRANCH_FITTING' | 'UNIT_LABEL' | 'PIPE_TAG' | 'ROOM_NAME'
  | 'ARCH_BACKGROUND' | 'ANNOTATION' | 'TITLE_BLOCK' | 'UNKNOWN';

export const LAYER_ROLE_LABEL: Record<LayerRole, string> = {
  REFRIGERANT_PIPE: '냉매 배관', BRANCH_FITTING: '분기 이음', UNIT_LABEL: '장비 라벨', PIPE_TAG: '배관 태그',
  ROOM_NAME: '실명', ARCH_BACKGROUND: '건축 배경', ANNOTATION: '주석', TITLE_BLOCK: '도곽', UNKNOWN: '미지정',
};

export type HoldCode =
  | 'AI_DISABLED' | 'AI_BUDGET' | 'AI_NO_RESPONSE' | 'AI_UNREADABLE' | 'AI_NO_EVIDENCE'
  | 'AI_OUT_OF_DOMAIN' | 'AI_NOT_ATTACHED' | 'AI_DISAGREE' | 'AI_CONFLICT'
  /** Assumption: 벡터 판독 단계의 보류 사유 코드(설계서 문구 기반) */
  | 'NO_VERTICAL_EVIDENCE' | 'NO_SCALE_EVIDENCE' | 'DIAMETER_UNCLEAR';

/* ---------- 원본 근거 ---------- */
/** source_ref (DB 설계 v0.4). Assumption: 내부 구조는 미정 → 핸들 · 레이어 · 좌표만 사용 */
export interface SourceRef { handle: string; layer: string; x: number; y: number }

/* ---------- 문서 · 프로젝트 ---------- */
export type DocumentRole = 'DRAWING' | 'BOQ' | 'SPEC';
export interface DocumentMeta {
  documentId: string;
  fileName: string;
  sizeBytes: number;
  role: DocumentRole;
  objectKey: string;
  /** 변환이 필요한 형식(XLS, 암호화 HWP 등)일 때 안내 문구 */
  conversionHint?: string;
}

export interface Project {
  projectId: string;
  name: string;
  siteKey: string;
  revision: string;
  floor: string;
  scope: '설치' | '철거' | '설치 + 철거';
  unit: string;
  aiEnabled: boolean;
  drawing: DocumentMeta | null;
  documents: DocumentMeta[];
  latestAnalysisId: string | null;
  /** 목록 표시용 요약. 서버가 내려준 값만 표시 */
  state: AnalysisState;
  stageLabel: string;
  updatedAt: string; // ISO
  isDemo: boolean;
}

/* ---------- 분석 결과 (A04) ---------- */
export interface Layer { name: string; entityCount: number; textSample: string; role: LayerRole; previewColor: string }
export interface PlanNode { id: string; label: string; kind: 'OU' | 'BRANCH' | 'IDU'; x: number; y: number; model?: string }
export interface SystemSummary { systemId: string; name: string; segmentCount: number; indoorCount: number }

export type LengthType = '평면 계산값' | '수직 보정값' | '설계 실장' | '상당장' | '현장 입력값';
export interface ReviewHistory { who: string; what: string; at: string }

export interface ReviewItem {
  itemId: string;
  systemId: string;
  from: string; // PlanNode.id
  to: string;
  diameterMm: string; // 예: '15.88/9.52'
  /** 원본값(판독) — 절대 덮어쓰지 않음 */
  planLengthM: number;
  verticalLengthM: number | null;
  /** 채택값(담당자) */
  adoptedLengthM: number | null;
  lengthType: LengthType;
  status: ReviewStatus;
  holdCode: HoldCode | null;
  holdReason: string;
  holdNote: string;
  shdRequired: boolean;
  sourceRef: SourceRef;
  /** 꺾인 배관일 때 좌표 목록(도면 좌표) */
  points?: [number, number][];
  history: ReviewHistory[];
  updatedBy?: string;
  updatedAt?: string;
}

/** T03 검증 기준값 (종류별로 분리 표시, 합산 금지) */
export interface ReferenceTotals { planCount: number; planTotalM: number; treeSegments: number; treeTotalM: number; longestM: number; label: string }

export interface Analysis {
  analysisId: string;
  projectId: string;
  requestId: string;
  state: AnalysisState;
  stage: AnalysisStage;
  errorCode: AnalysisErrorCode | null;
  layers: Layer[];
  layerRolesApplied: boolean;
  systems: SystemSummary[];
  nodes: PlanNode[];
  reviewItems: ReviewItem[];
  reviewVersion: number;
  compareVersion: number;
  reference: ReferenceTotals | null;
  /** 이 결과가 Mock(시연) 데이터인지. 화면에 반드시 구분 표시 */
  isDemo: boolean;
  createdAt: string;
}

/* ---------- 요청 바디 ---------- */
export interface CreateProjectBody { name: string; siteKey?: string; aiEnabled: boolean } // A01
export interface UploadRequestBody { fileName: string; contentType: string; sizeBytes: number; role: DocumentRole } // A02A
export interface UploadTicket { objectKey: string; putUrl: string }
export interface RegisterDocumentBody { objectKey: string; fileName: string; role: DocumentRole; sizeBytes: number; revision?: string; scope?: string; requestId: string } // A02
export interface StartAnalysisBody { drawingId: string; documentIds: string[]; floor?: string; unit?: string; layerRoles?: Record<string, LayerRole>; requestId: string } // A03

export type ReviewActionKind = 'CONFIRM' | 'HOLD' | 'EDIT';
export interface ReviewAction {
  itemId: string;
  action: ReviewActionKind;
  value?: number;
  valueKind?: 'VERTICAL' | 'ADOPTED';
  evidence?: string;
  reason?: string;
}
export interface ReviewPatchBody { reviewVersion: number; items: ReviewAction[]; actor: string } // A05

export interface CreateExportBody { systemId: string; reviewVersion: number; format: ExportFormat; targetVersion: string; requestId: string } // A06

export interface LatsCheckRecord {
  status: LatsCheckStatus;
  appVersion?: string;
  sha256?: string;
  steps?: { importCad: boolean | null; saveReopen: boolean | null; systemCheck: boolean | null };
  evidenceKey?: string;
  checkedAt?: string;
}

export interface ExportJob {
  exportId: string;
  analysisId: string;
  systemId: string;
  format: ExportFormat;
  reviewVersion: number;
  targetVersion: string;
  state: ExportState;
  sha256: string | null;
  downloadUrl: string | null;
  latsCheck: LatsCheckRecord;
  isDemo: boolean;
  createdAt: string;
}

export interface LatsCheckBody { appVersion: string; sha256: string; steps: NonNullable<LatsCheckRecord['steps']>; evidenceKey?: string } // A08
export interface AppEvent { name: string; projectId?: string; analysisId?: string; at: string; props?: Record<string, string | number | boolean> } // A09

/* ---------- 오류 ---------- */
export interface MissingRequiredItem { itemId: string; status: ReviewStatus; reason: string }

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: { latest?: Analysis; missing?: MissingRequiredItem[] } & Record<string, unknown>,
  ) {
    super(message);
  }
}

/** HTTP 상태별 사용자 안내 (설계서 9.3 오류 UI) */
export const HTTP_GUIDE: Record<number, string> = {
  400: '입력값을 확인해 주세요.',
  403: '이 작업에 대한 권한이 없습니다.',
  404: '대상을 찾을 수 없습니다. 목록에서 다시 열어 주세요.',
  409: '다른 변경이 먼저 저장되었습니다. 최신값을 확인해 주세요.',
  415: '지원하지 않는 파일 형식입니다.',
  422: '처리 조건을 만족하지 않습니다.',
};
