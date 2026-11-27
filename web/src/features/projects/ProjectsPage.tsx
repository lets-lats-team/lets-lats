import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/adapter';
import type { Project } from '../../api/contracts';
import { Badge, Empty, ErrorBox, Info, Skeleton } from '../../components/ui';
import { Guide } from '../../components/Shell';
import { Icon } from '../../components/Sprite';
import { qk, useProjects } from '../../hooks/queries';
import { go } from '../../lib/router';
import { ago } from '../../lib/util';
import { useUi } from '../../store/uiStore';

const FILTERS: [string, Project['state'] | null][] = [['전체', null], ['작성 중', 'DRAFT'], ['검토 대기', 'REVIEW'], ['판독 중', 'RUNNING'], ['실패', 'FAILED']];

export function ProjectsPage() {
  const q = useProjects();
  const qc = useQueryClient();
  const { currentProjectId, setProject, notify } = useUi();
  const [text, setText] = useState('');
  const [filter, setFilter] = useState<Project['state'] | null>(null);
  const [creating, setCreating] = useState(false);

  const open = (p: Project) => {
    setProject(p.projectId);
    const v = p.state === 'DRAFT' || p.state === 'RUNNING' || p.state === 'QUEUED' || p.state === 'FAILED' ? 'register' : p.stageLabel === '역할 지정 대기' ? 'layers' : 'review';
    go(v, p.projectId);
  };
  const create = async () => {
    setCreating(true);
    try {
      const p = await api.createProject({ name: '새 작업', aiEnabled: false });
      await qc.invalidateQueries({ queryKey: qk.projects });
      setProject(p.projectId);
      go('register', p.projectId);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const rows = (q.data ?? []).filter(
    (p) => (!filter || p.state === filter || (filter === 'RUNNING' && p.state === 'QUEUED')) && (!text || `${p.name} ${p.siteKey}`.toLowerCase().includes(text.toLowerCase())),
  );

  return (
    <section className="view">
      <Guide view="projects" />
      <div className="vh">
        <div>
          <h1>작업 목록</h1>
          <p>UI-00 · 작업을 고르거나 새로 만드세요</p>
        </div>
        <span className="sp" />
        <button className="btn b-pri sm" onClick={create} disabled={creating}>
          + 새 작업
        </button>
      </div>
      {api.mode === 'real' && <Info kind="demo">작업 목록 조회 API는 설계서에 계약이 없어, 이 브라우저에서 만든 작업만 표시합니다.</Info>}
      <div className="card toolbar">
        <input type="text" placeholder="작업명 · 현장 키 검색" value={text} onChange={(e) => setText(e.target.value)} aria-label="작업 검색" style={{ maxWidth: 320 }} />
        <div className="chips">
          {FILTERS.map(([l, v]) => (
            <button key={l} className="chip" aria-pressed={filter === v} onClick={() => setFilter(v)}>
              {l}
            </button>
          ))}
        </div>
      </div>
      {q.isLoading ? (
        <Skeleton rows={5} />
      ) : q.error ? (
        <ErrorBox error={q.error} onRetry={() => q.refetch()} />
      ) : rows.length === 0 ? (
        <Empty title="조건에 맞는 작업이 없습니다.">필터를 바꾸거나 [+ 새 작업]으로 시작하세요.</Empty>
      ) : (
        <>
          <div className="card hide-m" style={{ overflow: 'auto' }}>
            <table className="t">
              <thead>
                <tr><th>작업명</th><th>현장 · 개정</th><th>최근 분석</th><th className="r">업데이트</th></tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.projectId} className={p.projectId === currentProjectId ? 'sel' : ''} onClick={() => open(p)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && open(p)}>
                    <td>
                      <b>{p.name || '새 작업'}</b>
                      <div className="mut12">{p.drawing ? p.drawing.fileName : '도면 미등록'}{p.isDemo ? ' · Mock' : ''}</div>
                    </td>
                    <td className="num">{[p.siteKey, p.revision && `개정 ${p.revision}`, p.floor].filter(Boolean).join(' · ') || '—'}</td>
                    <td><Badge s={p.state} text={p.stageLabel} /></td>
                    <td className="r">{ago(p.updatedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* 모바일 카드형 */}
          <div className="mcards show-m">
            {rows.map((p) => (
              <button key={p.projectId} className="mcard" onClick={() => open(p)}>
                <span className="mcard-h"><b>{p.name || '새 작업'}</b><Badge s={p.state} text={p.stageLabel} /></span>
                <span className="mut12">{[p.siteKey, p.revision && `개정 ${p.revision}`, p.floor].filter(Boolean).join(' · ') || '현장 정보 없음'} · {ago(p.updatedAt)}</span>
                <span className="mut12"><Icon name="i-file" style={{ width: 13, height: 13 }} /> {p.drawing ? p.drawing.fileName : '도면 미등록'}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
