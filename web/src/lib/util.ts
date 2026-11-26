/** requestId: 네트워크 재전송은 같은 ID, 사용자의 명시적 재실행은 새 ID (설계서 9.3) */
export const newRequestId = () => 'req_' + Math.random().toString(36).slice(2, 10);
export const newId = (prefix: string) => `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

export const fmtM = (v: number | null | undefined, d = 2) => (v == null ? '—' : `${v.toFixed(d)} m`);
export const fmtMB = (bytes: number) => `${(bytes / 1048576).toFixed(1)} MB`;

export function nowLabel(d = new Date()) {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function ago(iso: string) {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return '방금';
  if (m < 60) return `${m}분 전`;
  if (m < 1440) return `${Math.round(m / 60)}시간 전`;
  return `${Math.round(m / 1440)}일 전`;
}

export function safeStorage<T>(key: string, fallback: T): { get: () => T; set: (v: T) => void } {
  return {
    get() {
      try {
        const raw = localStorage.getItem(key);
        return raw ? (JSON.parse(raw) as T) : fallback;
      } catch {
        return fallback;
      }
    },
    set(v) {
      try {
        localStorage.setItem(key, JSON.stringify(v));
      } catch {
        /* 저장 공간 부족 등 — 화면은 계속 동작 */
      }
    },
  };
}

/** 문자열 → 0~1 난수열 (같은 파일이면 같은 Mock 결과) */
export function seeded(seedText: string) {
  let s = 0;
  for (let i = 0; i < seedText.length; i++) s = (s * 31 + seedText.charCodeAt(i)) % 2147483647;
  if (s <= 0) s = 12345;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

export const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((res, rej) => {
    const t = setTimeout(res, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(t);
      rej(new DOMException('aborted', 'AbortError'));
    });
  });
