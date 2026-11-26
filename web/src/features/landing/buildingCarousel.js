// @ts-nocheck
/* 기존 웹사이트의 3D 건물 캐러셀 렌더러를 그대로 재사용합니다 (canvas 2D, 원근 투영 + 화가 알고리즘).
   React에서는 <BuildingCarousel/>가 같은 id의 마크업을 렌더한 뒤 initBuildingCarousel()을 호출합니다. */
export function initBuildingCarousel(){
const __cleanups=[];let __alive=true;

const RMb=matchMedia('(prefers-reduced-motion: reduce)').matches;
const SL=[
['01 · INSIDE THE BUILDING','건물 안의 공조는<br>하나의 계통입니다.','옥상 실외기에서 출발한 냉매가 층마다 실내기로 갈라집니다. 이 연결 관계가 LATS 설계의 출발점입니다.',['실외기','실내기','층별 분기'],{yaw:-0.62,pitch:0.42,zoom:1}],
['02 · THE DESIGN GAP','도면에 이미 있는 선을,<br>왜 다시 재고 있을까요?','배관 선과 분기, 실내기 태그, 길이를 사람이 다시 측정하고 LATS에 하나씩 입력합니다. 가장 번거롭고 오류가 잦은 단계입니다.',['구간 길이 재측정','연결 재정리','재입력'],{yaw:0.5,pitch:0.32,zoom:1.06}],
['03 · READ · CHECK · CONFIRM','읽고, 검산하고,<br>근거를 보여줍니다.','레이어 역할을 지정하면 계통과 구간 길이를 계산하고, 근거가 부족한 수직 길이와 단위는 보류로 남겨 담당자에게 묻습니다.',['레이어 역할','분기와 교차 구분','보류 우선'],{yaw:-1.05,pitch:0.5,zoom:1.04}],
['04 · HAND-OFF TO LATS','확정한 도면 그대로,<br>LATS에서 이어서 설계.','필수 항목이 모두 확정된 계통만 SHD/SHDX 초안으로 출력합니다. LATS 실물 호환은 검증 기록이 있을 때만 PASS로 표시합니다.',['필수값 확정 후 출력','북미판 1.9.13.23 실물 검증 전'],{yaw:-0.62,pitch:1.35,zoom:1.02}]];
const q=s=>document.querySelector(s);
const sec=q('#inside'),cv=q('#bCv'),ctx=cv.getContext('2d'),txt=q('#bTxt');
let si=0,cam={yaw:-0.62,pitch:0.42,zoom:1},tw=null,userUntil=0,hover=false,timer=null,W=0,H=0,DPR=1;const t0=performance.now();
q('#bDots').innerHTML=SL.map((s,i)=>`<button role="tab" aria-label="${i+1}번 장면" aria-selected="${i===0}"></button>`).join('');
function show(i,fromUser){si=(i+SL.length)%SL.length;const s=SL[si];q('#bK').textContent=s[0];q('#bT').innerHTML=s[1];q('#bD').textContent=s[2];q('#bG').innerHTML=s[3].map(t=>`<li>${t}</li>`).join('');q('#bN').textContent=`0${si+1} / 04`;
 [...q('#bDots').children].forEach((b,j)=>{const n=b.cloneNode(true);n.setAttribute('aria-selected',j===si);b.replaceWith(n)});
 txt.classList.remove('swap');void txt.offsetWidth;txt.classList.add('swap');
 if(!fromUser||performance.now()>userUntil)tw={from:{...cam},to:{...s[4]},t:performance.now()};
 sched()}
function sched(){clearTimeout(timer);const paused=RMb||hover||performance.now()<userUntil||document.hidden;sec.classList.toggle('paused',paused);if(!paused)timer=setTimeout(()=>show(si+1),3000);else timer=setTimeout(sched,800)}
q('#bDots').addEventListener('click',e=>{const b=e.target.closest('button');if(b)show([...q('#bDots').children].indexOf(b),true)});
q('#bPrev').onclick=()=>show(si-1,true);q('#bNext').onclick=()=>show(si+1,true);
const fig=q('#bFig');fig.addEventListener('pointerenter',()=>{hover=true;sched()});fig.addEventListener('pointerleave',()=>{hover=false;sched()});
const touch=()=>{userUntil=performance.now()+6000;tw=null;q('#bHint').style.opacity=.35;sched()};
cv.addEventListener('wheel',e=>{e.preventDefault();touch();const k=e.deltaMode===1?0.05:0.0022;if(e.shiftKey||Math.abs(e.deltaX)>Math.abs(e.deltaY))cam.pitch+=(e.shiftKey?e.deltaY:e.deltaX)*k;else cam.yaw+=e.deltaY*k},{passive:false});
let dr=null;cv.addEventListener('pointerdown',e=>{dr={x:e.clientX,y:e.clientY};cv.setPointerCapture(e.pointerId);cv.classList.add('drag');touch()});
cv.addEventListener('pointermove',e=>{if(!dr)return;cam.yaw+=(e.clientX-dr.x)*0.009;cam.pitch+=(e.clientY-dr.y)*0.009;dr={x:e.clientX,y:e.clientY};touch()});
const up=()=>{dr=null;cv.classList.remove('drag')};cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',up);
cv.addEventListener('dblclick',()=>{userUntil=0;tw={from:{...cam},to:{...SL[si][4]},t:performance.now()};sched()});
function size(){DPR=Math.min(2,devicePixelRatio||1);W=cv.clientWidth;H=cv.clientHeight;cv.width=W*DPR;cv.height=H*DPR}
addEventListener('resize',size);__cleanups.push(()=>removeEventListener('resize',size));size();
const FH=3.4,NF=3,XW=18,ZD=10,RY=FH*NF;
const hex=h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];
const L=(()=>{const v=[-0.45,0.8,0.55],m=Math.hypot(...v);return v.map(a=>a/m)})();
function box(x0,y0,z0,x1,y1,z1,col,a,o={}){const c=hex(col);const P=[[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]];
 const F=[[[0,3,2,1],[0,0,-1]],[[4,5,6,7],[0,0,1]],[[0,1,5,4],[0,-1,0]],[[3,7,6,2],[0,1,0]],[[0,4,7,3],[-1,0,0]],[[1,2,6,5],[1,0,0]]];
 return F.map(([ix,n])=>({k:'f',p:ix.map(i=>P[i]),n,c,a,e:o.e||0,s:o.s,cull:a>=0.99}))}
const ODU=[[11,13.1],[13.5,15.6],[16,18.1]];
const IDU=[];for(let k=0;k<NF;k++)for(const x of [3,9,15])for(const z of [2.6,7.4])IDU.push([x,k*FH+FH-0.75,z,k]);
const RX=17.2,RZ=5.2;
const PIPES=(()=>{const P=[];const top=RY+0.55;
 P.push({id:'hdr',pts:[[12.05,top,4.4],[12.05,top,RZ],[RX,top,RZ]],kind:'main'});
 [14.55,17.05].forEach(x=>P.push({id:'hdr'+x,pts:[[x,top,4.4],[x,top,RZ]],kind:'main'}));
 P.push({id:'riser',pts:[[RX,top,RZ],[RX,FH-0.55,RZ]],kind:'riser'});
 for(let k=0;k<NF;k++){const y=k*FH+FH-0.55;P.push({id:'m'+k,pts:[[RX,y,RZ],[2,y,RZ]],kind:'main',k});
  for(const x of [3,9,15])for(const z of [2.6,7.4])P.push({id:'b'+k+x+z,pts:[[x,y,RZ],[x,y,z]],kind:'br',k,x,z})}
 return P})();
function scene(st){const I=[];const fadeShell=st===3?0.04:0.07;
 I.push(...box(-2.5,-0.8,-2.5,XW+2.5,0,ZD+2.5,'#E7E0D5',1));
 for(let k=0;k<=NF;k++){const y=k*FH;I.push(...box(0,y-0.3,0,XW,y,ZD,'#F1ECE4',k===0?1:(st===3?0.35:0.55)))}
 for(const[x,z]of[[0,0],[XW,0],[0,ZD],[XW,ZD],[6,ZD],[12,ZD],[6,0],[12,0]])I.push(...box(x-0.25,0,z-0.25,x+0.25,RY,z+0.25,'#D6CFC5',st===3?0.35:1));
 for(const f of box(0,0,0,XW,RY,ZD,'#A9C4D6',fadeShell)){f.edge=1;I.push(f)}
 ODU.forEach(([a,b])=>{I.push(...box(a,RY,2.2,b,RY+1.8,4.4,'#F2F0EC',1,{s:'odu'}));I.push({k:'circ',c:[(a+b)/2,RY+1.81,3.3],r:0.7,col:'#4b4547'});I.push(...box(a,RY+1.55,4.38,b,RY+1.7,4.42,'#FF4D8A',1,{e:1}))});
 IDU.forEach(([x,y,z])=>I.push(...box(x-0.65,y,z-0.65,x+0.65,y+0.32,z+0.65,'#6E9BFF',1,{e:0.6,s:'idu'})));
 PIPES.forEach(p=>{let col='#FF4D8A',w=3,dash=null,glow=1;
  if(st===1){col='#E3A37F';dash=[7,6];glow=0}
  if(st===2){col='#34C38F';glow=0;if(p.kind==='riser'){col='#F5B13D';dash=[8,6]}if(p.id==='m2'){col='#B794FF';w=5;glow=1}if(p.k===0&&p.kind==='br'&&p.x===9){col='#F5B13D';dash=[6,5]}}
  if(st===3){w=2;glow=0}
  for(let i=1;i<p.pts.length;i++)I.push({k:'l',a:p.pts[i-1],b:p.pts[i],col,w:p.kind==='br'?w*0.75:w,dash,glow})});
 for(let k=0;k<NF;k++)for(const x of [3,9,15])I.push({k:'dia',c:[x,k*FH+FH-0.55,RZ],col:'#E07A3A'});
 for(let i=0;i<5;i++){const x=-1.2+i*2.7;I.push(...box(x-0.15,0,ZD+1.3,x+0.15,1.4,ZD+1.6,'#6B5244',1));I.push(...box(x-0.8,1.3,ZD+0.65,x+0.8,2.9,ZD+2.25,'#6E8A68',1))}
 if(st===3){const y=RY+0.62;const pl=[[[0.6,y,0.6],[XW-0.6,y,0.6],[XW-0.6,y,ZD-0.6],[0.6,y,ZD-0.6],[0.6,y,0.6]],[[6,y,0.6],[6,y,ZD-0.6]],[[12,y,0.6],[12,y,ZD-0.6]],[[0.6,y,RZ-0.8],[XW-0.6,y,RZ-0.8]],[[0.6,y,RZ+0.8],[XW-0.6,y,RZ+0.8]]];
  pl.forEach(ps=>{for(let i=1;i<ps.length;i++)I.push({k:'l',a:ps[i-1],b:ps[i],col:'#F6F1EE',w:1.6,dash:null,glow:0,top:1})});
  I.push({k:'l',a:[RX,y,RZ],b:[2,y,RZ],col:'#FF4D8A',w:3,glow:1,top:1});
  for(const x of [3,9,15])for(const z of [2.6,7.4]){I.push({k:'l',a:[x,y,RZ],b:[x,y,z],col:'#FF4D8A',w:2.2,glow:1,top:1});I.push({k:'sq',c:[x,y,z],col:'#F6F1EE',top:1})}}
 return I}
const LBL=[[['실외기 · Multi V',[14.5,RY+2.6,3.3]],['실내기 (층별 6대)',[3,2*FH+FH-0.4,2.6]],['층별 분기',[9,FH+FH-0.55,RZ]]],
 [['구간 길이 ?',[9.5,2*FH+FH-0.55,RZ]],['수직 길이 ?',[RX,FH*1.6,RZ]],['분기 연결 ?',[15,FH-0.55,7.4]]],
 [['확정',[5,FH-0.55,RZ]],['보류 · 수직 근거 없음',[RX,FH*1.6,RZ]],['선택 구간',[6,2*FH+FH-0.55,RZ]]],
 [['2D 평면 → SHD 초안',[9,RY+0.7,ZD-0.6]]]];
function proj(p,c){const x=p[0]-9,y=p[1]-4.6,z=p[2]-5;const cy=Math.cos(c.yaw),sy=Math.sin(c.yaw),cp=Math.cos(c.pitch),sp=Math.sin(c.pitch);
 const x1=x*cy+z*sy,z1=-x*sy+z*cy;const y2=y*cp-z1*sp,z2=y*sp+z1*cp;const D=58,f=D/(D-z2),sc=Math.min(W,H)/22*c.zoom;
 return[W/2+x1*f*sc,H*0.52-y2*f*sc,z2]}
function rotN(n,c){const cy=Math.cos(c.yaw),sy=Math.sin(c.yaw),cp=Math.cos(c.pitch),sp=Math.sin(c.pitch);const z1=-n[0]*sy+n[2]*cy;return n[1]*sp+z1*cp}
function frame(now){if(tw){const k=Math.min(1,(now-tw.t)/900),e=1-Math.pow(1-k,3);const d=(a,b)=>{let v=b-a;v=((v+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI;return a+v*e};cam.yaw=d(tw.from.yaw,tw.to.yaw);cam.pitch=d(tw.from.pitch,tw.to.pitch);cam.zoom=tw.from.zoom+(tw.to.zoom-tw.from.zoom)*e;if(k>=1)tw=null}
 ctx.setTransform(DPR,0,0,DPR,0,0);ctx.clearRect(0,0,W,H);
 const st=si,I=scene(st),R=[];
 for(const it of I){if(it.k==='f'){const pr=it.p.map(p=>proj(p,cam));const nz=rotN(it.n,cam);if(it.cull&&nz<=0)continue;const z=pr.reduce((s,p)=>s+p[2],0)/4;R.push({it,pr,z})}
  else if(it.k==='l'){const a=proj(it.a,cam),b=proj(it.b,cam);R.push({it,a,b,z:(a[2]+b[2])/2+(it.top?50:0.02)})}
  else{const c=proj(it.c,cam);R.push({it,c,z:c[2]+(it.top?50:0.05)})}}
 R.sort((p,q)=>p.z-q.z);
 const tm=(now-t0)/1000;
 for(const r of R){const it=r.it;
  if(it.k==='f'){const nd=it.n[0]*L[0]+it.n[1]*L[1]+it.n[2]*L[2];const sh=it.e?0.85+0.15*Math.max(0,nd):0.6+0.4*Math.max(0,nd);const[c0,c1,c2]=it.c;let a=it.a;
   if(it.s==='idu'&&st!==0&&st!==2)a=0.55;
   ctx.beginPath();r.pr.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle=`rgba(${c0*sh|0},${c1*sh|0},${c2*sh|0},${a})`;ctx.fill();
   if(it.edge){ctx.strokeStyle='rgba(200,225,240,.18)';ctx.lineWidth=1;ctx.stroke()}else if(a<1){ctx.strokeStyle='rgba(255,255,255,.12)';ctx.lineWidth=.8;ctx.stroke()}}
  else if(it.k==='l'){ctx.save();ctx.lineCap='round';if(it.glow){ctx.strokeStyle=it.col;ctx.globalAlpha=.25;ctx.lineWidth=it.w*3.2;ctx.beginPath();ctx.moveTo(r.a[0],r.a[1]);ctx.lineTo(r.b[0],r.b[1]);ctx.stroke();ctx.globalAlpha=1}
   if(it.dash){ctx.setLineDash(it.dash);ctx.lineDashOffset=-tm*14}ctx.strokeStyle=it.col;ctx.lineWidth=it.w;ctx.beginPath();ctx.moveTo(r.a[0],r.a[1]);ctx.lineTo(r.b[0],r.b[1]);ctx.stroke();ctx.restore()}
  else if(it.k==='dia'){ctx.save();ctx.translate(r.c[0],r.c[1]);ctx.rotate(Math.PI/4);ctx.fillStyle=it.col;ctx.fillRect(-3.5,-3.5,7,7);ctx.restore()}
  else if(it.k==='sq'){ctx.strokeStyle=it.col;ctx.lineWidth=1.4;ctx.strokeRect(r.c[0]-5,r.c[1]-5,10,10)}
  else if(it.k==='circ'){ctx.beginPath();for(let i=0;i<=16;i++){const a=i/16*Math.PI*2;const p=proj([it.c[0]+Math.cos(a)*it.r,it.c[1],it.c[2]+Math.sin(a)*it.r],cam);i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1])}ctx.fillStyle=it.col;ctx.fill()}}
 if((st===0||st===3)&&!RMb){ctx.save();ctx.fillStyle='#FFD1E0';ctx.shadowColor='#FF4D8A';ctx.shadowBlur=8;
  const top=RY+0.55;for(let k=NF-1;k>=0;k--){const y=k*FH+FH-0.55;const ps=[[12.05,top,4.4],[12.05,top,RZ],[RX,top,RZ],[RX,y,RZ],[2,y,RZ]];const seg=[];let tot=0;for(let i=1;i<ps.length;i++){const d=Math.hypot(ps[i][0]-ps[i-1][0],ps[i][1]-ps[i-1][1],ps[i][2]-ps[i-1][2]);seg.push(d);tot+=d}
   for(let n=0;n<6;n++){let u=((tm*4+n*tot/6+k*2)%tot);let i=0;while(i<seg.length-1&&u>seg[i]){u-=seg[i];i++}const a=ps[i],b=ps[i+1],f=Math.min(1,u/seg[i]);const p=proj([a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,a[2]+(b[2]-a[2])*f],cam);ctx.beginPath();ctx.arc(p[0],p[1],2.6,0,7);ctx.fill()}}ctx.restore()}
 ctx.font='700 12px "Noto Sans KR",sans-serif';ctx.textBaseline='middle';ctx.textAlign='center';
 LBL[st].forEach(([t,p])=>{const s=proj(p,cam);const w=ctx.measureText(t).width+18;const x=s[0],y=s[1]-22;ctx.fillStyle='rgba(29,25,28,.92)';ctx.strokeStyle='rgba(255,255,255,.28)';ctx.lineWidth=1;ctx.beginPath();if(ctx.roundRect)ctx.roundRect(x-w/2,y-12,w,24,5);else ctx.rect(x-w/2,y-12,w,24);ctx.fill();ctx.stroke();ctx.beginPath();ctx.moveTo(x,y+12);ctx.lineTo(s[0],s[1]-3);ctx.stroke();ctx.fillStyle='#fff';ctx.fillText(t,x,y+.5)});
 const rb=sec.getBoundingClientRect();if(rb.bottom>-50&&rb.top<innerHeight+50&&!document.hidden)(__alive&&requestAnimationFrame(frame));else setTimeout(()=>(__alive&&requestAnimationFrame(frame)),300)}
show(0);(__alive&&requestAnimationFrame(frame));

return ()=>{__alive=false;clearTimeout(timer);__cleanups.forEach(f=>f())};
}
