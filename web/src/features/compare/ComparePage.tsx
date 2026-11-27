import { Badge, Info } from '../../components/ui';
import { Guide } from '../../components/Shell';
import { useCurrent } from '../../hooks/useCurrent';
import { go } from '../../lib/router';

/** UI-03 문서 대조 (P2) — 실제 대조는 워커 담당, 현재는 화면 구성 미리보기 */
const ROWS = [
  ['실내기 4WAY 카세트', '9 대', '9 대', '—', 'MATCH', 'CONFIRMED', 'M-501 · 내역 R12'],
  ['냉매 배관 Ø15.88 (평면)', '11.35 m', '12.0 m', '—', 'DIFFERENT', 'PENDING', 'S01 · S04 · S07 · 내역 R31'],
  ['배관 보온재 두께', '—', '—', '25 mm 이상', 'CONDITION_UNMET', 'HELD', '시방서 3.2.4'],
  ['실외기 용량', '모델 확인 필요', '20 HP', '—', 'NOT_COMPARABLE', 'HELD', '단위 · 범위 불명확'],
] as const;
const JD: Record<string, string> = { MATCH: 'j-m', DIFFERENT: 'j-d', CONDITION_UNMET: 'j-c', NOT_COMPARABLE: 'j-n' };

export function ComparePage() {
  const { projectId, project } = useCurrent();
  const docs = project.data?.documents ?? [];
  return (
    <section className="view">
      <Guide view="compare" />
      <div className="vh">
        <div>
          <h1>문서 대조 <span className="badge s-PENDING" style={{ verticalAlign: 'middle' }}>P2 · 준비 중</span></h1>
          <p>UI-03 · 공내역서 · 시방서 값과 도면 판독값 비교 — 현재는 화면 구성 미리보기</p>
        </div>
        <span className="sp" />
        <button className="btn b-sec sm" onClick={() => go('exports', projectId)}>건너뛰고 산출물로 →</button>
      </div>
      <Info kind="demo">문서 대조는 설계서상 <b>P2(후속)</b> 기능이라 실제 대조는 아직 하지 않습니다. 아래 표는 완성 시 모습을 보여주는 <b>가상 미리보기</b>이며, 도면 검토와 SHD 출력은 문서 대조 없이도 진행할 수 있습니다.</Info>
      <div className="grid3" style={{ marginBottom: 14 }}>
        <div className="card pad16"><b className="fs13">비교 조건</b><div className="mut13 mt6">같은 현장 · 개정 · 건물 · 층 · 설치/철거 범위 · 단위일 때만 비교합니다. 불명확하면 비교 보류(NOT_COMPARABLE).</div></div>
        <div className="card pad16"><b className="fs13">판정과 검토는 별개</b><div className="mut13 mt6">판정(MATCH · DIFFERENT · CONDITION_UNMET · NOT_COMPARABLE)과 담당자 검토(미확인 · 확정 · 보류)를 따로 표시합니다.</div></div>
        <div className="card pad16"><b className="fs13">등록된 선택 문서</b><div className="mut13 mt6">{docs.length ? docs.map((d) => d.fileName).join(', ') + ' (P2 연동 전)' : '대조할 자료 없음 · 작업 등록에서 추가할 수 있어요.'}</div></div>
      </div>
      <div className="card hide-m" style={{ overflow: 'auto' }}>
        <table className="t">
          <thead><tr><th>항목</th><th>도면 (판독)</th><th>공내역서</th><th>시방서</th><th>판정</th><th>검토</th><th>근거 위치</th></tr></thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r[0]}><td><b>{r[0]}</b></td><td className="num">{r[1]}</td><td className="num">{r[2]}</td><td className="num">{r[3]}</td><td><span className={`jd ${JD[r[4]]}`}>{r[4]}</span></td><td><Badge s={r[5]} /></td><td className="num">{r[6]}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mcards show-m">
        {ROWS.map((r) => (
          <div key={r[0]} className="mcard">
            <span className="mcard-h"><b>{r[0]}</b><span className={`jd ${JD[r[4]]}`}>{r[4]}</span></span>
            <span className="mkv"><span>도면<b className="num">{r[1]}</b></span><span>공내역서<b className="num">{r[2]}</b></span><span>시방서<b className="num">{r[3]}</b></span></span>
            <span className="row"><Badge s={r[5]} /><span className="mut12">{r[6]}</span></span>
          </div>
        ))}
      </div>
      <p className="mut12" style={{ marginTop: 10 }}>미리보기 · 가상 데이터 · 검토 버전이 바뀌면 '대조 갱신 중'으로 표시될 예정입니다 (compare_version &lt; review_version).</p>
    </section>
  );
}
