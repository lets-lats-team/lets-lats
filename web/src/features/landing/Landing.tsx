import { useEffect, useRef, useState } from 'react';
import { Icon } from '../../components/Sprite';
import { initHero } from './heroCanvas';
import { initBuildingCarousel } from './buildingCarousel';

/** 소개 페이지 — 기존 웹사이트 구조 · 문구 · 클래스명을 그대로 유지합니다. */
export function Landing({ section }: { section: string }) {
  const [introDone, setIntroDone] = useState(() => !!section && section !== 'top');
  const sky = useRef<HTMLCanvasElement>(null);
  const hero = useRef<HTMLElement>(null);
  const cap = useRef<HTMLDivElement>(null);
  const nav = useRef<HTMLElement>(null);
  const track = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (introDone) return;
    const t = setTimeout(() => setIntroDone(true), 2300);
    return () => clearTimeout(t);
  }, [introDone]);

  useEffect(() => {
    if (!sky.current || !hero.current || !cap.current) return;
    const stopHero = initHero(sky.current, hero.current, cap.current, nav.current);
    const stopBld = initBuildingCarousel();
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add('in'), io.unobserve(e.target))), { threshold: 0.15 });
    document.querySelectorAll('.rv').forEach((el) => io.observe(el));
    const ioT = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target as HTMLElement).style.setProperty('--p', '1')), { threshold: 0.3 });
    if (track.current) ioT.observe(track.current);
    document.title = "LET'S LATS · 도면에서 LATS까지";
    return () => {
      stopHero();
      stopBld();
      io.disconnect();
      ioT.disconnect();
    };
  }, []);

  useEffect(() => {
    if (section && section !== 'top') document.getElementById(section)?.scrollIntoView();
  }, [section]);

  return (
    <div id="site">
      {!introDone && (
        <div id="intro" aria-hidden="true" onClick={() => setIntroDone(true)}>
          <div className="intro-in">
            <div className="bars"><i /><i /><i /></div>
            <div className="intro-word">{"LET'S LATS".split('').map((c, i) => <span key={i} style={{ animationDelay: `${0.35 + i * 0.05}s` }}>{c === ' ' ? ' ' : c}</span>)}</div>
            <div className="intro-sub">LG AX SCHOOL · TEAM 03 · 공조 설계 지원 AI Agent</div>
            <div className="intro-line"><b /></div>
          </div>
        </div>
      )}
      <header className="nav" id="nav" ref={nav}>
        <div className="wrap">
          <a className="logo" href="#top"><span className="mk"><i /><i /><i /></span>LET'S LATS</a>
          <nav aria-label="주요 메뉴">
            <a href="#overview">프로젝트</a><a href="#inside">공조 설계</a><a href="#how">작동 방식</a><a href="#product">제품 체험</a><a href="#guide">사용 가이드</a><a href="#output">산출물</a>
          </nav>
          <a className="btn sm b-pri mobile-cta" href="#projects">시작하기</a>
        </div>
      </header>
      <main id="top">
        <section className={`hero ${introDone ? 'go' : ''}`} id="hero" ref={hero} aria-label="소개">
          <canvas id="sky" ref={sky} aria-hidden="true" />
          <div className="shade" />
          <span className="cv-tag">개념 시각화 · 실제 현장 아님</span>
          <div className="wrap">
            <span className="pill"><i />LG AX SCHOOL · TEAM 03 &nbsp;LET'S LATS</span>
            <h1><span className="ln"><span>도면에서 LATS까지,</span></span><span className="ln"><span>설계의 흐름을 연결하다.</span></span></h1>
            <p className="lead">CAD 도면의 장비와 냉매 배관 정보를 판독하고, 담당자의 검토를 거쳐 LATS 설계 초안으로 연결하는 공조 설계 지원 AI Agent.</p>
            <div className="cta">
              <a className="btn b-light" href="#projects">서비스 시작하기 <Icon name="i-arrow" /></a>
              <a className="btn b-out" href="#review">샘플 체험</a>
            </div>
            <div className="hero-meta"><span><b>입력</b> DWG / DXF</span><span><b>판독</b> 레이어 · 장비 · 배관 · 분기</span><span><b>검토</b> 원본 근거 대조</span><span><b>출력</b> SHD · SHDX 시험 · 실물 검증</span></div>
          </div>
          <div className="stage-cap" id="cap" ref={cap}><b>01 · 받은 CAD 도면</b>도면의 선과 글자를 읽어</div>
        </section>

        <section className="band" id="overview">
          <div className="wrap mission">
            <div className="rv"><p className="k">프로젝트</p><h2 className="h2-2l"><span className="l">이미 받은 도면을,</span><span className="l">다시 그리지 않도록.</span></h2><p className="lede">전문점 설계·영업 담당자는 받은 CAD 도면의 배관 선, 분기, 실내외기 태그와 길이를 다시 재고 LATS에 하나씩 입력합니다. LET'S LATS는 그 반복을 줄이고 담당자가 판단과 검토에 집중하도록 돕습니다.</p></div>
            <div className="vals rv">
              <div><span><b>전문점 설계 생산성</b><br />도면 → LATS 재입력 시간</span><em>측정 예정 · T14</em></div>
              <div><span><b>근거의 일관성</b><br />모든 값에 원본 위치·수정 이력</span><em>설계 원칙</em></div>
              <div><span><b>파트너 경험</b><br />시공사·전문점의 검토 흐름 개선 가능성</span><em>가설 · 비교 실험 예정</em></div>
            </div>
          </div>
        </section>

        <section className="bld" id="inside" aria-roledescription="carousel" aria-label="건물 안의 공조 계통">
          <button className="bld-arr prev" id="bPrev" aria-label="이전 장면"><Icon name="i-left" /></button>
          <div className="bld-in">
            <div className="bld-txt" id="bTxt">
              <p className="bld-k" id="bK">01 · INSIDE THE BUILDING</p>
              <h2 id="bT">건물 안의 공조는<br />하나의 계통입니다.</h2>
              <p className="bld-d" id="bD">옥상 실외기에서 출발한 냉매가 층마다 실내기로 갈라집니다. 이 연결 관계가 LATS 설계의 출발점입니다.</p>
              <ul className="bld-tags" id="bG"><li>실외기</li><li>실내기</li><li>층별 분기</li></ul>
              <div className="bld-ctl"><span className="bld-n num" id="bN">01 / 04</span><div className="bld-dots" id="bDots" role="tablist" aria-label="장면 선택" /></div>
            </div>
            <div className="bld-fig" id="bFig">
              <canvas id="bCv" aria-label="3D 개념 모형 · 휠이나 드래그로 360도 회전" role="img" />
              <div className="bld-legend"><span><i style={{ background: '#FF4D8A' }} />냉매 배관</span><span><i style={{ background: '#F2F0EC' }} />실외기</span><span><i style={{ background: '#6E9BFF' }} />실내기</span><span><i className="dm" />분기</span></div>
              <span className="bld-hint" id="bHint">휠 · 드래그로 360° 회전 · 더블클릭으로 처음 각도</span>
              <span className="bld-cap">가상 시설 · 설명용 3D 모형</span>
            </div>
          </div>
          <button className="bld-arr next" id="bNext" aria-label="다음 장면"><Icon name="i-right" /></button>
        </section>

        <section className="band" id="gap">
          <div className="wrap">
            <div className="rv"><p className="k">설계 격차</p><h2>설계는 연결되어 있는데, 입력은 왜 다시 할까요?</h2></div>
            <div className="gap">
              <div className="col rv"><h3>기존 업무</h3><p className="s">도면을 보며 다시 입력</p><ol className="flow"><li><i>1</i>CAD 도면 · 장비표 확인</li><li><i>2</i>구간별 배관 길이 측정</li><li><i>3</i>장비 · 배관 · 연결 재정리</li><li><i>4</i>LATS에 하나씩 입력 · 불일치 재확인</li></ol></div>
              <div className="col new rv"><h3>LET'S LATS</h3><p className="s">읽은 정보를 근거와 함께 확인</p><ol className="flow"><li><i>1</i>도면 판독 · DWG/DXF 레이어와 개체</li><li><i>2</i>계통 검산 · 분기와 단순 교차 구분</li><li><i>3</i>원본 검토 · 구간마다 원본 위치 대조</li><li><i>4</i>초안 출력 · SHD/SHDX → LATS에서 이어서</li></ol></div>
            </div>
            <p className="note rv">LATS CAD(AutoCAD 애드인)도 도면 위 배치와 길이 계산을 지원합니다. “받은 일반 DWG의 선·글자를 자동으로 읽어 초안을 만든다”는 차별점은 검증 전 가설이며, 동일 계통의 수작업 · LATS CAD 비교 실험으로 확인할 예정입니다.</p>
          </div>
        </section>

        <section className="band how" id="how">
          <div className="wrap">
            <div className="rv"><p className="k" style={{ color: '#ff8ab0' }}>작동 방식</p><h2>판독은 Agent가, 확정은 담당자가.</h2><p className="lede">다섯 단계 모두 워크벤치의 실제 화면으로 이어집니다.</p></div>
            <div className="track" id="track" ref={track}>
              <a href="#register" data-n="01"><b>도면 등록</b><span>DWG/DXF 1개와 선택 문서. AI 외부 전송은 기본 OFF.</span><u>작업 등록 →</u></a>
              <a href="#register" data-n="02"><b>첫 분석</b><span>레이어 목록 확인. 계통 분석 완료가 아닌 역할 지정 대기.</span><u>판독 진행 →</u></a>
              <a href="#layers" data-n="03"><b>역할 지정 · 계통 분석</b><span>냉매 배관·분기·라벨 레이어 지정 후 새 분석.</span><u>레이어 역할 →</u></a>
              <a href="#review" data-n="04"><b>원본 근거 검토</b><span>구간을 눌러 원본 위치와 대조하고 수정·확정·보류.</span><u>계통·도면 →</u></a>
              <a href="#exports" data-n="05"><b>산출물 · 실물 검증</b><span>필수값 확정 시 SHD 또는 SHDX 시험 출력, LATS에서 검증.</span><u>산출물 →</u></a>
            </div>
            <div className="callout">
              <div className="rv"><b>LATS를 대체하지 않습니다.</b><span>제품 선정, 최종 설계, System Check는 LATS와 담당자가 맡습니다.</span></div>
              <div className="rv"><b>성과는 직접 비교합니다.</b><span>검토 시간 · 누락 건수 · 길이 오류를 동일 샘플로 측정할 예정입니다. 현재는 교육용 프로토타입이며 실제 성과는 미측정입니다.</span></div>
            </div>
          </div>
        </section>

        <section className="band" id="product">
          <div className="wrap prod">
            <div className="rv">
              <p className="k">제품 체험</p><h2>밝고 정확한 CAD 검토 워크벤치</h2>
              <p className="lede">도면 · 계통 트리 · 근거 패널이 한 화면에서 서로 연결됩니다. 기본 체험은 DWG/DXF 워크벤치이며, 샘플 도면으로 바로 확인할 수 있습니다.</p>
              <ul className="demo-list">
                <li><Icon name="i-check" />도면 ↔ 트리 ↔ 표 양방향 선택과 확대 · 팬 · 레이어 토글</li>
                <li><Icon name="i-check" />평면 계산값 · 수직 보정값 · 설계 실장 · 상당장 · 현장 입력값 분리</li>
                <li><Icon name="i-check" />PENDING · CONFIRMED · HELD, review_version · 409 충돌 처리</li>
                <li><Icon name="i-check" />미확정 필수 항목이 있으면 SHD/SHDX 출력 제한(422)</li>
              </ul>
              <div className="row wrap"><a className="btn b-pri" href="#review">워크벤치 열기 <Icon name="i-arrow" /></a><a className="btn b-sec" href="#guide">처음이라면 · 사용 가이드</a></div>
            </div>
            <div className="shot rv">
              <div className="bar"><i /><i /><i />&nbsp; LET'S LATS · 계통·도면 검토</div>
              <div className="in">
                <div className="l"><div className="on">OAC-5-1</div><div>S04 · BR-1→BR-2</div><div>S07 · BR-2→BR-3</div><div>S11 · BR-4→BR-5</div><div>S15 · BR-6→IDU-505</div></div>
                <svg viewBox="0 0 1000 700">
                  <rect width="1000" height="700" fill="#FBFAF7" />
                  <rect x="40" y="40" width="920" height="620" fill="none" stroke="#BDB6B0" strokeWidth="6" />
                  <polyline points="86,365 820,365" fill="none" stroke="#0E7490" strokeWidth="5" />
                  <polyline className="flowline" points="86,365 820,365" fill="none" stroke="#fff" strokeWidth="2" />
                  {[150, 320, 510, 690, 820].map((x) => <polyline key={x} points={`${x},190 ${x},520`} fill="none" stroke="#0E7490" strokeWidth="5" />)}
                  <polyline points="320,365 510,365" fill="none" stroke="#7C3AED" strokeWidth="8" strokeDasharray="12 7" />
                  {[150, 320, 510, 690, 820].map((x) => <rect key={'b' + x} x={x - 9} y={356} width="18" height="18" transform={`rotate(45 ${x} 365)`} fill="#C2410C" stroke="#fff" strokeWidth="2" />)}
                  {[150, 320, 510, 690, 820].flatMap((x) => [190, 520].map((y) => <rect key={`${x}-${y}`} x={x - 26} y={y - 26} width="52" height="52" rx="6" fill="#fff" stroke="#1D4ED8" strokeWidth="4" />))}
                  <rect x="56" y="335" width="60" height="60" rx="6" fill="#1D4ED8" />
                </svg>
                <div className="r"><div><b>S07</b> 보류</div><div>평면 4.75 m</div><div>수직 보정 · 근거 필요</div><div>원본 핸들 2F3A</div></div>
              </div>
            </div>
          </div>
        </section>

        <section className="band guide" id="guide">
          <div className="wrap">
            <div className="rv"><p className="k">사용 가이드</p><h2 className="h2-2l"><span className="l">워크벤치,</span><span className="l">이 순서대로 쓰면 됩니다.</span></h2><p className="lede">처음 쓰는 분을 위한 6단계입니다. 각 단계의 링크를 누르면 워크벤치의 해당 화면이 열리고, 워크벤치 안에서도 상단 작업명 옆 <b>사용 가이드</b> 버튼으로 언제든 다시 열 수 있습니다.</p></div>
            <div className="gsteps">
              {GUIDE_STEPS.map(([n, t, d, href, link]) => (
                <div key={n} className="gstep rv"><span className="gn">STEP {n}</span><h3>{t}</h3><p>{d}</p><a className="go" href={href}>{link} →</a></div>
              ))}
            </div>
          </div>
        </section>

        <section className="band inside" id="output">
          <div className="wrap">
            <div className="rv"><p className="k">LATS 출력</p><h2>검토한 도면 그대로, LATS에서 이어서 설계.</h2><p className="lede">파일 생성 상태와 실제 LATS 실물 검증 상태는 언제나 따로 표시합니다.</p></div>
            <div className="outs">
              <div className="out rv"><span className="lv">P0 · 시험 출력</span><h3>SHD 설계 초안</h3><p>해당 계통의 필수 항목이 모두 확정되었을 때만 생성합니다.</p><ul><li>형식: SHD(기본) 또는 SHDX(선택)</li><li>장비 · 배관 연결 · 길이</li><li>대상: 북미판 LATS HVAC 1.9.13.23</li><li>SHDX 지원 여부 · 실물 확인 전</li></ul></div>
              <div className="out rv"><span className="lv">P1 · 예정</span><h3>CSV 검토표</h3><p>검토 버전 · 원본/채택값 · 단위 · 보류 사유를 그대로 유지합니다.</p></div>
              <div className="out rv"><span className="lv">P2 · 예정</span><h3>PDF 검토 리포트</h3><p>확정 구간과 근거를 출력 당시 검토 버전으로 정리합니다.</p></div>
            </div>
            <div className="hand rv">
              <div>
                <b style={{ display: 'block', fontSize: 13, color: 'var(--t2)', marginBottom: 10 }}>LET'S LATS Agent 처리 과정</b>
                <ol>{['DWG 원본 도면', 'DXF 변환', '장비·배관 정보 추출', '연결 관계 분석', '사용자 검수', 'SHD 또는 SHDX 생성', 'LATS HVAC 가져오기', '설계 검증 및 시뮬레이션'].map((s) => <li key={s}>{s}</li>)}</ol>
              </div>
              <span className="badge s-UNVERIFIED"><Icon name="i-shield" />LATS 실물 검증 전</span>
            </div>
          </div>
        </section>

        <section className="beyond2" id="beyond">
          <span className="b2cap">개념 이미지 · 가상 건물</span>
          <div className="wrap">
            <p className="b2k">BEYOND AUTOMATION</p>
            <h2 className="h2-2l"><span className="l">한 번의 자동화에서,</span><span className="l">더 강한 공조 생태계로.</span></h2>
            <div className="b2cols">
              <div className="rv"><span className="b2n">01</span><b>설계 생산성</b><p>반복 입력과 확인에 드는 부담을 줄이고 설계 판단에 집중합니다.</p></div>
              <div className="rv"><span className="b2n">02</span><b>파트너 경험</b><p>시공사와 대리점이 같은 근거를 바탕으로 후속 설계를 이어갑니다.</p></div>
              <div className="rv"><span className="b2n">03</span><b>사업 경쟁력</b><p>설계 지원 효율화와 처리 역량 향상 가능성을 검증합니다.</p></div>
            </div>
            <div className="b2cta"><b>설계의 다음 단계, 직접 확인하세요.</b><a className="btn b-pri" href="#projects">서비스 시작하기</a></div>
          </div>
        </section>
      </main>
      <footer>
        <div className="wrap fwrap">
          <a className="logo" href="#top"><span className="mk"><i /><i /><i /></span>LET'S <em>LATS</em></a>
          <div className="fmid"><span>LG AX SCHOOL · TEAM 03 LET'S LATS · 2026 교육 프로젝트</span><span>LG전자 공식 서비스가 아닙니다. 샘플 도면은 교육용이며 실제 설계에는 담당자 검토가 필요합니다.</span></div>
          <a href="#top" className="ftop">맨 위로</a>
        </div>
      </footer>
    </div>
  );
}

const GUIDE_STEPS: [string, string, string, string, string][] = [
  ['01', '작업 열기', '작업 목록에서 검토할 작업을 고르거나 [+ 새 작업]을 누릅니다. 상태 배지로 검토 대기 · 판독 중 · 실패를 구분합니다.', '#projects', '작업 목록 열기'],
  ['02', '도면 등록 · 판독 시작', '설비 DWG/DXF 1개는 필수, 공내역서 · 시방서는 선택입니다. [판독 시작]을 누르면 첫 분석이 역할 지정 대기까지 진행됩니다.', '#register', '작업 등록 열기'],
  ['03', '레이어 역할 지정', '냉매 배관 · 분기 · 장비 라벨 레이어를 골라 [역할 확정]을 누르면 새 분석으로 계통과 구간 길이가 계산됩니다. 이전 결과는 보존됩니다.', '#layers', '레이어 역할 열기'],
  ['04', '도면에서 구간 확인', '도면 위 배관을 클릭하면 오른쪽에 원본값 · 채택값 · 원본 위치가 열립니다. 휠로 확대, 드래그로 이동하고, 왼쪽 메뉴는 화살표로 접을 수 있습니다.', '#review', '계통 · 도면 열기'],
  ['05', '수정 · 확정 · 보류', '근거가 맞으면 확정, 근거가 없으면 보류를 유지하고 [수정]에서 값과 근거(예: 층고표)를 입력합니다. 일괄 확정은 미확인 항목만 대상입니다.', '#review', '검토 시작'],
  ['06', '표로 점검 후 출력', '배관 상세표에서 전체 구간을 한 번에 점검하고, 산출물에서 SHD(또는 SHDX)를 만듭니다. 미확정 필수 항목이 있으면 출력이 제한됩니다.', '#table', '배관 상세표 열기'],
];
