import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { Icon } from './Sprite';
import { useUi } from '../store/uiStore';

/* 상태 배지 — 색 + 아이콘 + 텍스트 (설계서 5.1) */
const ICO: Record<string, string> = {
  PENDING: 'i-clock', CONFIRMED: 'i-ok', HELD: 'i-hold', REVIEW: 'i-info', QUEUED: 'i-clock', RUNNING: 'i-ref', FAILED: 'i-xc',
  READY: 'i-ok', PASS: 'i-shield', FAIL: 'i-xc', UNVERIFIED: 'i-shield', DRAFT: 'i-pen', DEMO: 'i-info',
};
const LBL: Record<string, string> = {
  PENDING: '미확인', CONFIRMED: '확정', HELD: '보류', REVIEW: '검토 대기', QUEUED: '대기열', RUNNING: '판독 중', FAILED: '실패',
  READY: '준비 완료', PASS: 'PASS', FAIL: 'FAIL', UNVERIFIED: '검증 전', DRAFT: '작성 중', DEMO: 'DEMO',
};
export function Badge({ s, text }: { s: string; text?: string }) {
  const cls = s === 'DRAFT' ? 'PENDING' : s;
  return (
    <span className={`badge s-${cls}`}>
      <Icon name={ICO[s] ?? 'i-info'} />
      {text ?? LBL[s] ?? s}
    </span>
  );
}

export function Info({ kind, children, style }: { kind?: 'warn' | 'err' | 'demo' | 'ok'; children: ReactNode; style?: CSSProperties }) {
  const ico = kind === 'warn' || kind === 'err' ? 'i-alert' : kind === 'ok' ? 'i-ok' : 'i-info';
  return (
    <div className={`info ${kind && kind !== 'ok' ? kind : ''}`} style={{ ...(kind === 'ok' ? { background: 'var(--okt)' } : {}), ...style }}>
      <Icon name={ico} style={kind === 'ok' ? { color: 'var(--ok)' } : undefined} />
      <div>{children}</div>
    </div>
  );
}

export function Modal({ open, onClose, children, label }: { open: boolean; onClose: () => void; children: ReactNode; label: string }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    addEventListener('keydown', k);
    setTimeout(() => box.current?.querySelector<HTMLElement>('button')?.focus(), 30);
    return () => removeEventListener('keydown', k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="mbox" role="dialog" aria-modal="true" aria-label={label} ref={box}>
        {children}
      </div>
    </div>
  );
}

export function Toast() {
  const t = useUi((s) => s.toast);
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!t) return;
    setOn(true);
    const h = setTimeout(() => setOn(false), 2600);
    return () => clearTimeout(h);
  }, [t]);
  return (
    <div id="toast" role="status" aria-live="polite" className={on ? 'on' : ''}>
      {t?.text}
    </div>
  );
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="card" style={{ padding: 16, display: 'grid', gap: 10 }} aria-busy="true" aria-label="불러오는 중">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skel" style={{ height: 14, width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error as { status?: number; message?: string };
  return (
    <Info kind="err">
      <b>{e.status === 0 ? '네트워크 연결이 끊겼습니다' : `오류${e.status ? ` (${e.status})` : ''}`}</b>
      <div style={{ marginTop: 2 }}>{e.message ?? '알 수 없는 오류'}</div>
      {onRetry && (
        <button className="btn b-ghost sm" style={{ marginTop: 8 }} onClick={onRetry}>
          <Icon name="i-ref" />
          다시 시도
        </button>
      )}
    </Info>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card" style={{ padding: 28, textAlign: 'center', color: 'var(--t2)' }}>
      <b style={{ display: 'block', color: 'var(--t1)', marginBottom: 6 }}>{title}</b>
      {children}
    </div>
  );
}
