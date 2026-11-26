import { useEffect, type ReactNode } from 'react';
import { api } from '../api/adapter';
import { go, ORDER, VIEW_LABEL, type View } from '../lib/router';
import { useUi } from '../store/uiStore';
import { useCurrent } from '../hooks/useCurrent';
import { Badge } from './ui';
import { Icon } from './Sprite';
import { GUIDES } from './guides';

const RAIL: { v: View; icon: string; tag?: string }[] = [
  { v: 'projects', icon: 'i-list' }, { v: 'register', icon: 'i-up' }, { v: 'layers', icon: 'i-layers' }, { v: 'review', icon: 'i-branch' },
  { v: 'table', icon: 'i-table' }, { v: 'compare', icon: 'i-cols', tag: 'P2' }, { v: 'exports', icon: 'i-send' },
];

function stateBadge(state?: string, stage?: string) {
  if (!state) return null;
  if (state === 'REVIEW') return <Badge s="REVIEW" text={stage === 'LAYER_ROLES' ? '역할 지정 대기' : '검토 대기'} />;
  return <Badge s={state} />;
}

export function Shell({ view, children }: { view: View; children: ReactNode }) {
  const { projectId, project, analysis } = useCurrent();
  const { railCollapsed, toggleRail, dirty, guideClosed, setGuide } = useUi();
  const p = project.data;
  const a = analysis.data;
  const link = (v: View) => go(v, projectId);
  const prev = () => {
    const i = ORDER.indexOf(view);
    if (i <= 0) location.hash = 'top';
    else link(ORDER[i - 1]);
  };
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault();
        prev();
      }
    };
    addEventListener('keydown', k);
    return () => removeEventListener('keydown', k);
  });
  useEffect(() => {
    document.title = `${p?.name || "LET'S LATS"} · ${VIEW_LABEL[view]}`;
  }, [p?.name, view]);
  const sub = p ? [p.siteKey, p.revision && `개정 ${p.revision}`, p.floor, p.scope].filter(Boolean).join(' · ') : '';

  return (
    <div id="app">
      <div className="top">
        <button className="backb" onClick={prev} aria-label="뒤로 가기" title="이전 단계로 (Alt+←)">
          <Icon name="i-left" />
          <span>뒤로</span>
        </button>
        <a className="logo" href="#top" title="소개 페이지">
          <span className="mk"><i /><i /><i /></span>LET'S LATS
        </a>
        <div className="job">
          <b>{p ? p.name || '새 작업' : '작업을 선택하세요'}</b>
          <span>{p ? sub || '작업 정보를 입력하고 저장하세요' : '작업 목록에서 열거나 새로 만드세요'}</span>
        </div>
        {GUIDES[view] && (
          <button className="helpb" onClick={() => setGuide(view, !guideClosed[view])} title="이 화면의 사용 가이드 열기/닫기">
            <Icon name="i-info" />
            사용 가이드
          </button>
        )}
        <span className="sp" />
        {stateBadge(a?.state, a?.stage)}
        {a && <span className="ver num hide-s">{a.analysisId}</span>}
        {a && <span className="ver num">검토 v{a.reviewVersion}</span>}
        <span className={`savest ${dirty ? 'dirty' : ''}`} title="저장 상태">
          <Icon name={dirty ? 'i-alert' : 'i-ok'} />
          {dirty ? '저장 안 됨' : '저장됨'}
        </span>
        {api.mode === 'mock' && (
          <span className="badge s-DEMO" title="MockApiAdapter · 서버 미연결 · 데이터는 이 브라우저에 저장">
            <Icon name="i-info" />
            Mock
          </span>
        )}
      </div>
      <div className={`shell ${railCollapsed ? 'rc' : ''}`}>
        <nav className="rail" aria-label="워크벤치">
          <button className="railtog" onClick={toggleRail} aria-expanded={!railCollapsed} title={railCollapsed ? '메뉴 펼치기' : '메뉴 접기'}>
            <Icon name="i-left" />
            <span>{railCollapsed ? '메뉴 펼치기' : '메뉴 접기'}</span>
          </button>
          {RAIL.map((r) => (
            <a key={r.v} href={`#${r.v}${projectId ? `?p=${projectId}` : ''}`} aria-current={r.v === view ? 'page' : undefined} title={VIEW_LABEL[r.v]}>
              <Icon name={r.icon} />
              {VIEW_LABEL[r.v]}
              {r.tag && <small>{r.tag}</small>}
              {r.v === 'layers' && a?.layerRolesApplied && <span className="done"><Icon name="i-check" style={{ width: 14 }} /></span>}
            </a>
          ))}
          <div className="foot">
            {api.mode === 'mock' ? 'Mock 어댑터로 동작합니다. 업로드 파일은 서버로 전송되지 않습니다.' : '서버와 연결되어 있습니다.'}
            <br />
            LG AX SCHOOL · TEAM 03 LET'S LATS
          </div>
        </nav>
        {children}
      </div>
      <BottomNav view={view} projectId={projectId} />
    </div>
  );
}

/** 980px 이하: 왼쪽 레일 대신 하단 내비게이션 (목록 · 등록 · 도면 · 표 · 더보기) */
function BottomNav({ view, projectId }: { view: View; projectId: string | null }) {
  const more: View[] = ['layers', 'compare', 'exports'];
  const href = (v: View) => `#${v}${projectId ? `?p=${projectId}` : ''}`;
  const items: { v: View; icon: string; label: string }[] = [
    { v: 'projects', icon: 'i-list', label: '목록' }, { v: 'register', icon: 'i-up', label: '등록' },
    { v: 'review', icon: 'i-branch', label: '도면' }, { v: 'table', icon: 'i-table', label: '표' },
  ];
  return (
    <nav className="bnav" aria-label="워크벤치 하단 메뉴">
      {items.map((i) => (
        <a key={i.v} href={href(i.v)} aria-current={i.v === view ? 'page' : undefined}>
          <Icon name={i.icon} />
          <span>{i.label}</span>
        </a>
      ))}
      <details className="bmore">
        <summary aria-current={more.includes(view) ? 'page' : undefined}>
          <Icon name="i-more" />
          <span>더보기</span>
        </summary>
        <div className="bmore-sheet">
          {more.map((v) => (
            <a key={v} href={href(v)} onClick={(e) => (e.currentTarget.closest('details') as HTMLDetailsElement).removeAttribute('open')}>
              {VIEW_LABEL[v]}
            </a>
          ))}
        </div>
      </details>
    </nav>
  );
}

export function Guide({ view, float }: { view: View; float?: boolean }) {
  const { guideClosed, setGuide } = useUi();
  const g = GUIDES[view];
  if (!g || guideClosed[view]) return null;
  return (
    <div className={`vguide ${float ? 'float' : ''}`} role="note">
      <div className="vg-h">
        <span className="vg-k">사용 가이드 · {g.step}</span>
        <button className="vg-x" onClick={() => setGuide(view, true)} aria-label="사용 가이드 닫기" title="닫기 · 상단 [사용 가이드]로 다시 열 수 있어요">
          <Icon name="i-x" />
        </button>
      </div>
      <b className="vg-t">{g.title}</b>
      <ol className="vg-s">
        {g.steps.map(([t, d], i) => (
          <li key={t}>
            <i>{i + 1}</i>
            <span>
              <b>{t}</b>
              {d}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
