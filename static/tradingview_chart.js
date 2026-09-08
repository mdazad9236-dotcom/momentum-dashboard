/* Native X10 chart workspace. Angel One candles are the source; no screenshot/upload/TradingView dependency. */
(function(){
  'use strict';
  let resizeBound=false;
  let state={instrument:{},candles:[],mode:'candle',view:90,offset:0,indicator:'none',frame:'1D'};

  function current(){return window.__azP4Current||window.currentInstrument||state.instrument||{}}
  function dataEndpoint(i){
    const name=String((i&&i.name)||'').trim();
    const symbol=String((i&&(i.symbol||i.name))||'').trim();
    return i&&i.isIndex?'/api/index-historical/'+encodeURIComponent(name||symbol):'/api/historical/'+encodeURIComponent(symbol);
  }
  function num(v){const n=Number(v);return Number.isFinite(n)?n:null}
  function esc(s){return String(s==null?'':s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]))}

  function normalize(rows){
    return (rows||[]).map(r=>({t:r&&r[0],o:num(r&&r[1]),h:num(r&&r[2]),l:num(r&&r[3]),c:num(r&&r[4]),v:num(r&&r[5])||0})).filter(r=>[r.o,r.h,r.l,r.c].every(v=>v!==null));
  }
  function sma(a,n){return a.map((_,i)=>{if(i+1<n)return null;let s=0;for(let j=i-n+1;j<=i;j++)s+=a[j];return s/n})}
  function ema(a,n){const k=2/(n+1);let out=[],prev=null;a.forEach((v,i)=>{prev=prev===null?v:v*k+prev*(1-k);out.push(i+1<n?null:prev)});return out}
  function rsi(a,n){let out=Array(a.length).fill(null),g=0,l=0;for(let i=1;i<a.length;i++){const d=a[i]-a[i-1],up=Math.max(d,0),dn=Math.max(-d,0);if(i<=n){g+=up;l+=dn;if(i===n){g/=n;l/=n;out[i]=l===0?100:100-100/(1+g/l)}}else{g=(g*(n-1)+up)/n;l=(l*(n-1)+dn)/n;out[i]=l===0?100:100-100/(1+g/l)}}return out}

  function ensureUI(wrap,instrument){
    let root=wrap.parentElement;
    if(!document.getElementById('azNativeChartCss')){
      const st=document.createElement('style');st.id='azNativeChartCss';st.textContent=`
      .az-native-toolbar{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:8px;padding:7px;border:1px solid #20384f;border-radius:10px;background:#091827}
      .az-native-toolbar .grp{display:flex;gap:4px;align-items:center}
      .az-native-toolbar button{border:1px solid #29445d;background:#0a1a2a;color:#9fb2c5;border-radius:7px;padding:6px 9px;font-size:9px;font-weight:900;cursor:pointer}
      .az-native-toolbar button:hover,.az-native-toolbar button.active{background:rgba(72,167,255,.14);color:#e8f4ff;border-color:#4d9ddd}
      .az-native-toolbar .spacer{flex:1}.az-native-toolbar .label{font-size:8px;color:#667f95;font-weight:900;letter-spacing:.4px}
      .az-native-stage{position:relative;height:100%;width:100%;overflow:hidden;background:linear-gradient(180deg,#06111d,#071522)}
      .az-native-canvas{display:block;width:100%;height:100%;cursor:crosshair}
      .az-native-readout{position:absolute;left:10px;top:10px;z-index:3;padding:8px 10px;background:rgba(5,14,24,.88);border:1px solid #20384f;border-radius:8px;pointer-events:none;font-size:9px;line-height:1.55;min-width:220px}
      .az-native-readout b{font-size:10px;color:#e3effa}.az-native-readout span{color:#7f95aa}.az-native-crosshair{position:absolute;display:none;pointer-events:none;border-left:1px dashed rgba(180,210,235,.45);border-top:1px dashed rgba(180,210,235,.45);z-index:2}
      .az-native-footer{position:absolute;right:10px;bottom:8px;z-index:3;color:#60768b;font-size:8px;pointer-events:none}
      `;document.head.appendChild(st);
    }
    let tb=document.getElementById('azNativeToolbar');
    if(!tb){
      const old=wrap.previousElementSibling;
      tb=document.createElement('div');tb.id='azNativeToolbar';tb.className='az-native-toolbar';
      tb.innerHTML=`<span class="label">TIMEFRAME</span><div class="grp" data-group="frame"><button data-v="1D" class="active">1D</button><button data-v="1W">1W</button><button data-v="1M">1M</button></div><span class="label">VIEW</span><div class="grp" data-group="mode"><button data-v="candle" class="active">Candles</button><button data-v="ha">Heikin Ashi</button><button data-v="line">Line</button></div><span class="label">INDICATOR</span><div class="grp" data-group="indicator"><button data-v="none" class="active">None</button><button data-v="ema">EMA 20/50</button><button data-v="rsi">RSI</button><button data-v="volume">Volume</button></div><span class="spacer"></span><button data-act="reset">Reset</button><button data-act="fullscreen">⛶</button>`;
      if(old&&old.classList.contains('az-chart-toolbar'))old.style.display='none';
      wrap.before(tb);
      tb.querySelectorAll('button[data-v]').forEach(b=>b.addEventListener('click',()=>{
        const group=b.parentElement.dataset.group;state[group]=b.dataset.v;tb.querySelectorAll(`[data-group="${group}"] button`).forEach(x=>x.classList.toggle('active',x===b));draw();
      }));
      tb.querySelector('[data-act="reset"]').onclick=()=>{state.view=90;state.offset=0;draw()};
      tb.querySelector('[data-act="fullscreen"]').onclick=()=>{const el=wrap.closest('.az-panel')||wrap;if(el.requestFullscreen)el.requestFullscreen();};
    }
    return tb;
  }

  function installStage(wrap){
    wrap.innerHTML='<div class="az-native-stage"><canvas class="az-native-canvas"></canvas><div class="az-native-readout"></div><div class="az-native-crosshair"></div><div class="az-native-footer">X10 Native Chart · Angel One OHLC</div></div>';
    const stage=wrap.firstElementChild,canvas=stage.querySelector('canvas'),readout=stage.querySelector('.az-native-readout'),cross=stage.querySelector('.az-native-crosshair');
    const onMove=e=>{const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;state._hover={x,y};cross.style.display='block';cross.style.left=x+'px';cross.style.top=y+'px';cross.style.width='0';cross.style.height='0';draw();};
    canvas.addEventListener('mousemove',onMove);canvas.addEventListener('mouseleave',()=>{state._hover=null;cross.style.display='none';draw()});
    canvas.addEventListener('wheel',e=>{e.preventDefault();state.view=Math.max(30,Math.min(state.candles.length, state.view+(e.deltaY>0?10:-10)));draw()},{passive:false});
    canvas.addEventListener('mousedown',e=>{state._drag={x:e.clientX,view:state.view,offset:state.offset}});
    window.addEventListener('mouseup',()=>{state._drag=null});
    window.addEventListener('mousemove',e=>{if(!state._drag)return;const dx=e.clientX-state._drag.x;state.offset=Math.max(0,Math.min(Math.max(0,state.candles.length-state.view),Math.round(-dx/7)+state._drag.offset));draw()});
    if(!resizeBound){window.addEventListener('resize',draw,{passive:true});resizeBound=true}
    return {canvas,stage,readout};
  }

  function draw(){
    const wrap=document.getElementById('azChartWrap');if(!wrap||!state.candles.length)return;const stage=wrap.querySelector('.az-native-stage'),canvas=stage&&stage.querySelector('canvas');if(!canvas)return;
    const ctx=canvas.getContext('2d'),rect=stage.getBoundingClientRect(),dpr=window.devicePixelRatio||1,w=Math.max(420,rect.width),h=Math.max(320,rect.height);canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);canvas.style.width=w+'px';canvas.style.height=h+'px';ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    const all=state.candles,n=Math.min(state.view,all.length),end=Math.max(n,all.length-state.offset),start=Math.max(0,end-n),rows=all.slice(start,end);if(!rows.length)return;
    const ind=state.indicator,volH=ind==='volume'?Math.min(95,h*.18):0,rsiH=ind==='rsi'?Math.min(85,h*.17):0,pad={l:58,r:16,t:26,b:34},chartH=h-pad.t-pad.b-volH-rsiH;
    const hi=Math.max(...rows.map(r=>r.h)),lo=Math.min(...rows.map(r=>r.l)),span=Math.max(0.0001,hi-lo),x=i=>pad.l+(i+.5)*(w-pad.l-pad.r)/rows.length,y=p=>pad.t+(hi-p)/span*chartH;
    ctx.font='10px Segoe UI,Arial';ctx.strokeStyle='rgba(110,140,165,.17)';ctx.fillStyle='#7c92a7';ctx.lineWidth=1;
    for(let i=0;i<=5;i++){const py=pad.t+chartH*i/5;ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(w-pad.r,py);ctx.stroke();ctx.fillText((hi-span*i/5).toFixed(2),8,py+3)}
    const body=Math.max(2,Math.min(12,(w-pad.l-pad.r)/rows.length*.62)),closes=rows.map(r=>r.c),e20=ema(closes,20),e50=ema(closes,50),rs=rsi(closes,14);
    function plot(vals,top,height,min,max,stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1.25;ctx.beginPath();let on=false;vals.forEach((v,i)=>{if(v==null)return;const px=x(i),py=top+(max-v)/Math.max(0.0001,max-min)*height;if(!on){ctx.moveTo(px,py);on=true}else ctx.lineTo(px,py)});if(on)ctx.stroke()}
    if(state.mode==='line'){ctx.strokeStyle='#48a7ff';ctx.lineWidth=1.5;ctx.beginPath();rows.forEach((r,i)=>{const px=x(i),py=y(r.c);if(i===0)ctx.moveTo(px,py);else ctx.lineTo(px,py)});ctx.stroke()}
    else rows.forEach((r,i)=>{let o=r.o,c=r.c,hv=r.h,lv=r.l;if(state.mode==='ha'){const prev= i?rows[i-1]:r; c=(r.o+r.h+r.l+r.c)/4;o=(prev.o+prev.c)/2;hv=Math.max(r.h,o,c);lv=Math.min(r.l,o,c)}const up=c>=o;ctx.strokeStyle=up?'#20d18b':'#ff5d6c';ctx.fillStyle=ctx.strokeStyle;const px=x(i);ctx.beginPath();ctx.moveTo(px,y(hv));ctx.lineTo(px,y(lv));ctx.stroke();const top=y(Math.max(o,c)),bot=y(Math.min(o,c));ctx.fillRect(px-body/2,top,body,Math.max(1,bot-top))});
    if(state.indicator==='ema'){const eh=Math.max(...rows.map(r=>r.h)),el=Math.min(...rows.map(r=>r.l));plot(e20,pad.t,chartH,el,eh,'#f4c95d');plot(e50,pad.t,chartH,el,eh,'#48a7ff')}
    if(volH){const base=pad.t+chartH+volH-8,maxV=Math.max(...rows.map(r=>r.v||0))||1;rows.forEach((r,i)=>{const bh=(r.v/maxV)*(volH-18);ctx.fillStyle=r.c>=r.o?'rgba(32,209,139,.45)':'rgba(255,93,108,.45)';ctx.fillRect(x(i)-body/2,base-bh,body,bh)});ctx.fillStyle='#6d8398';ctx.fillText('VOLUME',pad.l,base+8)}
    if(rsiH){const top=pad.t+chartH+volH,max=100,min=0;[30,70].forEach(v=>{const py=top+(max-v)/100*rsiH;ctx.strokeStyle='rgba(130,150,170,.18)';ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(w-pad.r,py);ctx.stroke()});plot(rs,top,rsiH,min,max,'#c792ff');ctx.fillStyle='#6d8398';ctx.fillText('RSI 14',pad.l,top+11)}
    const last=rows[rows.length-1],current=current();const title=(current.symbol||current.name||'Instrument')+' · '+last.c.toFixed(2);ctx.fillStyle='#dcecff';ctx.font='bold 12px Segoe UI,Arial';ctx.fillText(title,pad.l,15);ctx.fillStyle='#6e8499';ctx.font='9px Segoe UI,Arial';ctx.fillText(String(last.t||'').slice(0,19),w-145,15);
    const hov=state._hover;if(hov){const idx=Math.max(0,Math.min(rows.length-1,Math.floor((hov.x-pad.l)/(w-pad.l-pad.r)*rows.length)));const r=rows[idx];if(r){const px=x(idx);ctx.strokeStyle='rgba(200,220,240,.22)';ctx.beginPath();ctx.moveTo(px,pad.t);ctx.lineTo(px,pad.t+chartH);ctx.stroke();const rd=stage.querySelector('.az-native-readout');rd.innerHTML=`<b>${esc(String(r.t||'').slice(0,19))}</b><br><span>O</span> ${r.o.toFixed(2)} &nbsp; <span>H</span> ${r.h.toFixed(2)} &nbsp; <span>L</span> ${r.l.toFixed(2)} &nbsp; <span>C</span> ${r.c.toFixed(2)}<br><span>Volume</span> ${Math.round(r.v||0).toLocaleString('en-IN')}`}}
    const levels=[['Resistance',current.resistance||current.r1||current.resistance_price],['Support',current.support||current.s1||current.support_price],['Entry',current.entry||current.entry_price],['Stop',current.stop_loss||current.sl],['Target 1',current.target1||current.t1],['Target 2',current.target2||current.t2]].map(x=>[x[0],num(x[1])]).filter(x=>x[1]!==null);
    levels.forEach(([label,val])=>{if(val<lo||val>hi)return;const py=y(val);ctx.setLineDash([5,4]);ctx.strokeStyle=label==='Stop'?'rgba(255,93,108,.9)':label.startsWith('Target')?'rgba(32,209,139,.9)':'rgba(72,167,255,.8)';ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(w-pad.r,py);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=ctx.strokeStyle;ctx.fillText(label+' '+val.toFixed(2),w-pad.r-105,py-4)});
  }

  async function load(instrument){
    const wrap=document.getElementById('azChartWrap');if(!wrap)return;state.instrument=instrument||{};state.offset=0;
    ensureUI(wrap,instrument);const refs=installStage(wrap);refs.readout.textContent='Loading instrument candles…';
    try{const r=await fetch(dataEndpoint(instrument),{headers:{Accept:'application/json'},cache:'no-store'});const d=await r.json();if(!r.ok||!d.success)throw new Error(d.message||'Historical data unavailable');state.candles=normalize(d.data||d.candles||d.history||[]);if(!state.candles.length)throw new Error('No candles returned');refs.readout.innerHTML='<b>'+esc(instrument.symbol||instrument.name||'Instrument')+'</b><br><span>Angel One OHLC</span> · '+state.candles.length+' candles';draw();const status=document.getElementById('azChartStatus');if(status)status.textContent='X10 Native · '+(instrument.symbol||instrument.name||'Instrument')+' · '+state.candles.length+' candles';const hint=document.getElementById('azChartHint');if(hint)hint.textContent='Native X10 chart · Angel One candle data · Chart AI uses the same data automatically.';if(window.__azAutoChartAI&&typeof window.__azAutoChartAI.analyze==='function')setTimeout(()=>window.__azAutoChartAI.analyze(),180)}catch(e){refs.stage.innerHTML='<div class="az-error">Unable to load chart candles for '+esc(instrument.symbol||instrument.name||'instrument')+'. '+esc(e.message)+'</div>';const status=document.getElementById('azChartStatus');if(status)status.textContent='Chart unavailable';}
  }

  function install(){
    if(window.__azTradingViewInstalled)return true;if(typeof window.openInstrument!=='function')return false;const modal=document.getElementById('azModal');if(!modal)return false;
    const original=window.openInstrument;window.__azTradingViewOriginalOpenInstrument=original;
    window.openInstrument=function(raw){const instrument=raw||{};let result;try{result=original(instrument)}catch(e){console.error('Original instrument analysis failed:',e)}return Promise.resolve(result).then(function(){if(!modal.classList.contains('open')){modal.classList.add('open');modal.setAttribute('aria-hidden','false');document.body.style.overflow='hidden'}if(typeof window.switchTab==='function')window.switchTab('chart');state.instrument=instrument;load(instrument);});};
    window.__azTradingViewInstalled=true;return true;
  }
  function boot(){if(install())return;setTimeout(install,100);setTimeout(install,500);setTimeout(install,1200);setTimeout(install,2500)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
