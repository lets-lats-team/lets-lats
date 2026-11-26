import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/adapter';
import { ApiError, type Analysis, type ExportJob, type Project } from '../api/contracts';

const POLL = Number(import.meta.env.VITE_POLL_MS ?? 1500);

export const qk = {
  projects: ['projects'] as const,
  project: (id: string) => ['project', id] as const,
  analysis: (id: string) => ['analysis', id] as const,
  export: (id: string) => ['export', id] as const,
};

export const useProjects = () => useQuery({ queryKey: qk.projects, queryFn: () => api.listProjects() });

export const useProject = (id: string | null) =>
  useQuery({
    queryKey: qk.project(id ?? '-'),
    queryFn: () => api.getProject(id!),
    enabled: !!id,
    // 분석 진행 중이면 요약 상태도 갱신
    refetchInterval: (q) => (q.state.data && ['QUEUED', 'RUNNING'].includes((q.state.data as Project).state) ? POLL : false),
  });

/**
 * A04 폴링. 종료 상태(REVIEW · FAILED)에서 멈추고, 대상이 바뀌면 TanStack Query가 이전 요청을 취소합니다.
 * queryKey에 analysisId가 들어가므로 이전 분석의 늦은 응답이 최신 화면을 덮어쓰지 않습니다 (T16).
 */
export const useAnalysis = (analysisId: string | null) =>
  useQuery({
    queryKey: qk.analysis(analysisId ?? '-'),
    queryFn: ({ signal }) => api.getAnalysis(analysisId!, signal),
    enabled: !!analysisId,
    refetchInterval: (q) => {
      const d = q.state.data as Analysis | undefined;
      return d && (d.state === 'REVIEW' || d.state === 'FAILED') ? false : POLL;
    },
  });

/** A07 폴링. READY · FAILED에서 멈춤 */
export const useExportJob = (exportId: string | null) =>
  useQuery({
    queryKey: qk.export(exportId ?? '-'),
    queryFn: ({ signal }) => api.getExport(exportId!, signal),
    enabled: !!exportId,
    refetchInterval: (q) => {
      const d = q.state.data as ExportJob | undefined;
      return d && (d.state === 'READY' || d.state === 'FAILED') ? false : POLL;
    },
  });

/** A05 저장. 성공하면 캐시를 새 버전으로 바꾸고, 409면 최신값을 캐시에 넣은 뒤 오류를 그대로 던집니다. */
export function useSaveReviews(analysisId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof api.saveReviews>[1]) => api.saveReviews(analysisId!, body),
    onSuccess: (a) => {
      qc.setQueryData(qk.analysis(a.analysisId), a);
      qc.invalidateQueries({ queryKey: qk.projects });
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409 && e.details?.latest) qc.setQueryData(qk.analysis(analysisId!), e.details.latest);
    },
  });
}
