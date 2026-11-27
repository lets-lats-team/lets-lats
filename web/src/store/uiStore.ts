import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserRole } from '../api/contracts';

/**
 * 클라이언트 전용 UI 상태 (Zustand).
 * 서버 데이터(작업 · 분석 · 출력)는 TanStack Query가 관리하고 여기에는 두지 않습니다.
 */
interface UiState {
  currentProjectId: string | null;
  selectedItemId: string | null;
  railCollapsed: boolean;
  guideClosed: Record<string, boolean>;
  /** 인증 미정 → 화면 확인용 역할 전환. 권한 판단은 서버가 합니다. */
  role: UserRole;
  actorName: string;
  /** 작업 등록 폼에 저장하지 않은 변경이 있는지 */
  dirty: boolean;
  toast: { id: number; text: string } | null;

  setProject: (id: string | null) => void;
  select: (itemId: string | null) => void;
  toggleRail: () => void;
  setGuide: (view: string, closed: boolean) => void;
  setRole: (r: UserRole) => void;
  setDirty: (d: boolean) => void;
  notify: (text: string) => void;
}

export const useUi = create<UiState>()(
  persist(
    (set) => ({
      currentProjectId: null,
      selectedItemId: null,
      railCollapsed: false,
      guideClosed: {},
      role: 'USER',
      actorName: '담당자',
      dirty: false,
      toast: null,
      setProject: (id) => set({ currentProjectId: id, selectedItemId: null, dirty: false }),
      select: (itemId) => set({ selectedItemId: itemId }),
      toggleRail: () => set((s) => ({ railCollapsed: !s.railCollapsed })),
      setGuide: (view, closed) => set((s) => ({ guideClosed: { ...s.guideClosed, [view]: closed } })),
      setRole: (role) => set({ role }),
      setDirty: (dirty) => set({ dirty }),
      notify: (text) => set({ toast: { id: Date.now(), text } }),
    }),
    {
      name: 'letslats-ui',
      partialize: (s) => ({ currentProjectId: s.currentProjectId, railCollapsed: s.railCollapsed, guideClosed: s.guideClosed, role: s.role }),
    },
  ),
);
