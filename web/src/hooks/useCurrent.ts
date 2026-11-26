import { useEffect } from 'react';
import { useRoute } from '../lib/router';
import { useUi } from '../store/uiStore';
import { useAnalysis, useProject } from './queries';

/**
 * 현재 작업 = URL의 ?p= (우선) → 마지막으로 연 작업.
 * 화면은 항상 프로젝트의 최신 analysisId 기준으로 데이터를 보여줍니다.
 */
export function useCurrent() {
  const route = useRoute();
  const stored = useUi((s) => s.currentProjectId);
  const setProject = useUi((s) => s.setProject);
  const projectId = route.projectId ?? stored;
  useEffect(() => {
    if (route.projectId && route.projectId !== stored) setProject(route.projectId);
  }, [route.projectId, stored, setProject]);
  const project = useProject(projectId);
  const analysis = useAnalysis(project.data?.latestAnalysisId ?? null);
  return { projectId, project, analysis };
}
