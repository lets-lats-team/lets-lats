// @ts-nocheck
/* 기존 웹사이트 히어로 캔버스(해 질 녘 도시 · 청사진 타워 · 냉매 배관 흐름)를 그대로 재사용합니다. */
export function initHero(cv, hero, capEl, nav){
let introT0=performance.now()-2300;let alive=true;const cleanups=[];
/* ---------------- hero canvas ---------------- */
const cx=cv.getContext('2d');let W=0,H=0,DPR=1,mx=0,my=0,sy=0;
function rnd(seed){return()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646}}
let layers=[];
function build(){const r=rnd(42);layers=[0.55,0.75,1].map((d,li)=>{const arr=[];let x=-60;while(x<W+60){const w=(30+r()*70)*(0.7+li*0.25);const h=H*(0.08+r()*(0.16+li*0.1));arr.push({x,w,h,win:[...Array(30)].map(()=>r())});x+=w+(2+r()*10)}return{d,arr}})}
function size(){DPR=Math.min(2,devicePixelRatio||1);W=cv.clientWidth;H=cv.clientHeight;cv.width=W*DPR;cv.height=H*DPR;cx.setTransform(DPR,0,0,DPR,0,0);build()}
addEventListener('resize',size);size();cleanups.push(()=>removeEventListener('resize',size));
hero.addEventListener('pointermove',e=>{const b=hero.getBoundingClientRect();mx=(e.clientX-b.left)/b.width-.5;my=(e.clientY-b.top)/b.height-.5});
const onScroll=()=>{sy=scrollY;nav&&nav.classList.toggle('solid',scrollY>innerHeight*0.7)};addEventListener('scroll',onScroll,{passive:true});cleanups.push(()=>removeEventListener('scroll',onScroll));
const caps=[['01 · 받은 CAD 도면','도면의 선과 글자를 읽어'],['02 · 계통 검산','실외기에서 실내기까지 연결하고'],['03 · 원본 근거 검토','담당자가 근거를 보며 확정'],['04 · LATS 초안','SHD(X)로 후속 설계 연결']];
let capI=-1;
function draw(now){
 const t=(now-introT0)/1000; const ease=x=>1-Math.pow(1-Math.min(1,Math.max(0,x)),3);
 const hz=H*0.8; const px=mx*18, py=my*10, sc=1+Math.sin(t*0.08)*0.012+Math.min(sy/H,1)*0.06;
 cx.save();cx.translate(W/2,H/2);cx.scale(sc,sc);cx.translate(-W/2,-H/2+sy*0.25);
 let g=cx.createLinearGradient(0,0,0,hz);g.addColorStop(0,'#0c0910');g.addColorStop(.45,'#2a0c1d');g.addColorStop(.8,'#7a1f2c');g.addColorStop(1,'#d0693a');cx.fillStyle=g;cx.fillRect(-50,-50,W+100,hz+60);
 const sunX=W*0.74+px*0.4,sunY=hz-H*0.04;let rg=cx.createRadialGradient(sunX,sunY,0,sunX,sunY,H*0.6);rg.addColorStop(0,'rgba(255,190,120,.55)');rg.addColorStop(.25,'rgba(230,110,80,.25)');rg.addColorStop(1,'rgba(165,0,52,0)');cx.fillStyle=rg;cx.fillRect(0,0,W,H);
 for(let i=0;i<5;i++){const cxp=((i*W*0.27+t*8*(i%2?1:.6))%(W+600))-300+px,cyp=H*(0.16+i*0.07),rw=W*0.22;const cg=cx.createRadialGradient(cxp,cyp,0,cxp,cyp,rw);cg.addColorStop(0,'rgba(255,200,180,.07)');cg.addColorStop(1,'rgba(255,200,180,0)');cx.fillStyle=cg;cx.save();cx.translate(cxp,cyp);cx.scale(1,0.12);cx.translate(-cxp,-cyp);cx.fillRect(cxp-rw,cyp-rw,rw*2,rw*2);cx.restore()}
 layers.forEach((L,li)=>{const off=px*L.d*1.4;cx.fillStyle=['#4a1a2c','#2a1220','#140d16'][li];
  L.arr.forEach(b=>{const x=b.x+off,y=hz-b.h;cx.fillRect(x,y,b.w,b.h+H);
   if(li>0){const cols=Math.max(2,Math.floor(b.w/9)),rows=Math.floor(b.h/12);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const v=b.win[(r*cols+c)%30];if(v>0.72){const tw=0.5+0.5*Math.sin(t*1.3+v*50);cx.fillStyle=`rgba(255,${190+li*20},130,${(li===2?0.55:0.3)*tw})`;cx.fillRect(x+3+c*9,y+6+r*12,4,5)}}cx.fillStyle=['#4a1a2c','#2a1220','#140d16'][li]}})});
 // hero tower
 const tw=Math.max(140,W*0.13),th=H*0.62,tx=W*0.62+px*1.6,ty=hz-th;const p=ease((t-0.2)/2.2),p2=ease((t-1.8)/1.4);
 cx.save();cx.globalAlpha=p2;let tg=cx.createLinearGradient(tx,0,tx+tw,0);tg.addColorStop(0,'#3a1d22');tg.addColorStop(.18,'#8a4a35');tg.addColorStop(.35,'#26151c');tg.addColorStop(1,'#120c12');cx.fillStyle=tg;cx.fillRect(tx,ty,tw,th+H);
 const side=tw*0.32;cx.fillStyle='#0d090e';cx.beginPath();cx.moveTo(tx+tw,ty);cx.lineTo(tx+tw+side,ty+side*0.35);cx.lineTo(tx+tw+side,hz+H);cx.lineTo(tx+tw,hz+H);cx.fill();
 const floors=14;cx.strokeStyle='rgba(255,220,190,.10)';cx.lineWidth=1;for(let i=1;i<floors;i++){const y=ty+i*th/floors;cx.beginPath();cx.moveTo(tx,y);cx.lineTo(tx+tw,y);cx.stroke()}
 for(let i=0;i<floors;i++)for(let c=0;c<6;c++){const v=Math.sin(i*7.1+c*3.3);if(v>0.35){cx.fillStyle=`rgba(255,200,140,${0.18+0.12*Math.sin(t+i+c)})`;cx.fillRect(tx+6+c*(tw-12)/6,ty+i*th/floors+5,(tw-12)/6-5,th/floors-9)}}
 for(let i=0;i<4;i++){const ux=tx+8+i*(tw-16)/4;cx.fillStyle='#e9e1da';cx.fillRect(ux,ty-12,(tw-16)/4-6,12);cx.fillStyle='#5d5257';cx.beginPath();cx.ellipse(ux+((tw-16)/4-6)/2,ty-12,5,2,0,0,7);cx.fill()}
 cx.restore();
 // blueprint outline drawing in
 if(p<1||p2<1){cx.save();cx.strokeStyle='rgba(140,220,255,.85)';cx.lineWidth=1.2;const per=2*(tw+th);cx.setLineDash([per*p,per]);cx.beginPath();cx.rect(tx,ty,tw,th);cx.stroke();cx.setLineDash([]);cx.globalAlpha=(1-p2)*.6;for(let i=1;i<floors;i++){const y=ty+i*th/floors;cx.beginPath();cx.moveTo(tx,y);cx.lineTo(tx+tw*Math.min(1,p*1.4),y);cx.stroke()}cx.restore()}
 // refrigerant network
 const q=ease((t-2.4)/1.8);if(q>0){cx.save();cx.lineCap='round';cx.lineJoin='round';const rx=tx+tw-10;
  const pipe=(pts,col,w,dash)=>{cx.beginPath();pts.forEach(([a,b],i)=>i?cx.lineTo(a,b):cx.moveTo(a,b));cx.strokeStyle=col;cx.lineWidth=w;cx.shadowColor=col;cx.shadowBlur=12;cx.globalAlpha=q*.35;cx.stroke();cx.shadowBlur=0;cx.globalAlpha=q;cx.lineWidth=w*.5;cx.setLineDash(dash||[]);cx.lineDashOffset=-t*40;cx.stroke();cx.setLineDash([])};
  pipe([[tx+20,ty-6],[rx,ty-6],[rx,hz-4]],'#ff4d8a',4,[18,10]);
  for(let i=1;i<floors;i+=2){const y=ty+i*th/floors+th/floors/2;pipe([[rx,y],[tx+16,y]],'#ff4d8a',2.4,[8,14]);cx.fillStyle='#ffd1e0';cx.globalAlpha=q*(0.6+0.4*Math.sin(t*3+i));cx.fillRect(tx+tw*0.3-3,y-2,6,4);cx.fillRect(tx+tw*0.62-3,y-2,6,4)}
  const by=hz+6;pipe([[rx,hz-4],[rx,by],[W*0.2+px,by+18],[W*0.06,by+18]],'#5EE6F5',1.6,[4,10]);pipe([[rx,by],[W*0.96,by+26]],'#5EE6F5',1.6,[4,10]);
  cx.restore()}
 cx.restore();
 // ground
 g=cx.createLinearGradient(0,hz,0,H);g.addColorStop(0,'rgba(18,13,20,0)');g.addColorStop(.3,'rgba(18,13,20,.85)');g.addColorStop(1,'#120d14');cx.fillStyle=g;cx.fillRect(0,hz-10,W,H-hz+10);
 cx.strokeStyle='rgba(255,255,255,.05)';cx.lineWidth=1;for(let i=-10;i<=10;i++){cx.beginPath();cx.moveTo(W/2+px,hz+8);cx.lineTo(W/2+i*W*0.12+px*2,H);cx.stroke()}
 // dust
 cx.fillStyle='rgba(255,220,200,.35)';for(let i=0;i<40;i++){const x=(i*97.3+t*(6+i%5))%W,y=(i*53.7+Math.sin(t*.4+i)*20)%(hz);cx.globalAlpha=.15+.25*Math.sin(t+i);cx.fillRect(x,y,1.5,1.5)}cx.globalAlpha=1;
 const ci=Math.min(3,Math.floor(Math.max(0,t-0.5)/2.6)%4);if(ci!==capI){capI=ci;capEl.innerHTML=`<b>${caps[ci][0]}</b>${caps[ci][1]}`}
 if(!document.hidden&&hero.getBoundingClientRect().bottom>0)(alive&&requestAnimationFrame(draw));else setTimeout(()=>(alive&&requestAnimationFrame(draw)),400);
}
(alive&&requestAnimationFrame(draw));
return ()=>{alive=false;cleanups.forEach(f=>f())};
}
