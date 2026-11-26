import { useEffect, useState } from 'react';

/**
 * 기존 웹사이트와 같은 해시 URL을 유지합니다 (#projects, #register, #review …).
 * 작업별 URL: #review?p=<projectId>  — 새로고침 · 뒤로 가기 시 같은 작업으로 복원됩니다.
 */
export const VIEWS = ['projects', 'register', 'layers', 'review', 'table', 'compare', 'exports'] as const;
export type View = (typeof VIEWS)[number];
export const ORDER: View[] = [...VIEWS];

export interface Route { view: View | null; section: string; projectId: string | null }

export function parseHash(hash = location.hash): Route {
  const h = hash.replace(/^#/, '');
  const [path, query] = h.split('?');
  const p = new URLSearchParams(query ?? '').get('p');
  const view = (VIEWS as readonly string[]).includes(path) ? (path as View) : null;
  return { view, section: view ? '' : path || 'top', projectId: p };
}

export function go(view: View | string, projectId?: string | null) {
  location.hash = projectId ? `${view}?p=${encodeURIComponent(projectId)}` : view;
}

export function useRoute(): Route {
  const [r, setR] = useState(parseHash);
  useEffect(() => {
    const on = () => setR(parseHash());
    addEventListener('hashchange', on);
    return () => removeEventListener('hashchange', on);
  }, []);
  return r;
}

export const VIEW_LABEL: Record<View, string> = {
  projects: '작업 목록', register: '작업 등록', layers: '레이어 역할', review: '계통 · 도면', table: '배관 상세표', compare: '문서 대조', exports: '산출물',
};
