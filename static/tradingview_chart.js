/* Instrument-specific chart workspace: TradingView when available, with Angel One local OHLC fallback. */
(function () {
  function symbolForInstrument(s) {
    const raw = String((s && (s.symbol || s.name)) || '').trim().toUpperCase();
    const name = String((s && s.name) || raw).trim().toUpperCase();
    if (s && s.isIndex) {
      const map = {'NIFTY 50':'NSE:NIFTY','NIFTY':'NSE:NIFTY','BANK NIFTY':'NSE:BANKNIFTY','BANKNIFTY':'NSE:BANKNIFTY','SENSEX':'BSE:SENSEX','INDIA VIX':'NSE:INDIAVIX'};
      return map[name] || (raw.includes(':') ? raw : 'NSE:' + raw.replace(/[^A-Z0-9]/g, ''));
    }
    const stock = raw.replace(/^NSE:/, '').replace(/[^A-Z0-9_]/g, '');
    return stock ? 'NSE:' + stock : 'NSE:NIFTY';
  }

  function dataEndpoint(instrument){
    const name=String((instrument&&instrument.name)||'').trim();
    const symbol=String((instrument&&(instrument.symbol||instrument.name))||'').trim();
    return instrument&&instrument.isIndex ? '/api/index-historical/'+encodeURIComponent(name||symbol) : '/api/historical/'+encodeURIComponent(symbol);
  }

  function localChart(wrap,instrument,candles){
    wrap.innerHTML='';
    const canvas=document.createElement('canvas');
    canvas.className='az-canvas';
    canvas.setAttribute('aria-label','Instrument price chart');
    wrap.appendChild(canvas);
    const ctx=canvas.getContext('2d');
    const rows=(candles||[]).map(r=>({
      t:r&&r[0],o:+(r&&r[1]),h:+(r&&r[2]),l:+(r&&r[3]),c:+(r&&r[4]),v:+(r&&r[5]||0)
    })).filter(r=>[r.o,r.h,r.l,r.c].every(Number.isFinite)).slice(-90);
    if(!rows.length){wrap.innerHTML='<div class="az-error">No chart candles returned for this instrument.</div>';return;}
    function draw(){
      const rect=wrap.getBoundingClientRect(),dpr=window.devicePixelRatio||1,w=Math.max(320,rect.width),h=Math.max(280,rect.height);
      canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);canvas.style.width=w+'px';canvas.style.height=h+'px';ctx.setTransform(dpr,0,0,dpr,0,0);
      ctx.clearRect(0,0,w,h);
      const pad={l:58,r:18,t:24,b:34},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b;
      const hi=Math.max(...rows.map(x=>x.h)),lo=Math.min(...rows.map(x=>x.l));
      const span=Math.max(0.01,hi-lo),y=p=>pad.t+(hi-p)/span*ch;
      const x=i=>pad.l+(i+0.5)*cw/rows.length;
      ctx.font='10px Segoe UI,Arial';ctx.lineWidth=1;
      ctx.strokeStyle='rgba(80,110,135,.22)';ctx.fillStyle='#8397ab';
      for(let i=0;i<=4;i++){const py=pad.t+ch*i/4;ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(w-pad.r,py);ctx.stroke();ctx.fillText((hi-span*i/4).toFixed(2),8,py+3);}
      const body=Math.max(2,Math.min(14,cw/rows.length*.65));
      rows.forEach((r,i)=>{
        const px=x(i),up=r.c>=r.o;
        ctx.strokeStyle=up?'#20d18b':'#ff5d6c';ctx.fillStyle=ctx.strokeStyle;
        ctx.beginPath();ctx.moveTo(px,y(r.h));ctx.lineTo(px,y(r.l));ctx.stroke();
        const top=y(Math.max(r.o,r.c)),bot=y(Math.min(r.o,r.c));ctx.fillRect(px-body/2,top,body,Math.max(1,bot-top));
      });
      const last=rows[rows.length-1];
      ctx.fillStyle='#dcecff';ctx.font='bold 11px Segoe UI,Arial';ctx.fillText((instrument.symbol||instrument.name||'Instrument')+' · '+last.c.toFixed(2),pad.l,15);
      ctx.fillStyle='#71879b';ctx.font='9px Segoe UI,Arial';ctx.fillText('Angel One OHLC · last '+rows.length+' sessions',pad.l,h-10);
      const step=Math.max(1,Math.floor(rows.length/5));ctx.fillStyle='#71879b';
      for(let i=0;i<rows.length;i+=step){ctx.fillText(String(rows[i].t||'').slice(0,10),x(i)-20,h-20);}
    }
    draw();window.addEventListener('resize',draw,{passive:true});
  }

  async function loadLocal(wrap,instrument){
    try{
      const r=await fetch(dataEndpoint(instrument),{headers:{'Accept':'application/json'},cache:'no-store'});
      const d=await r.json();
      if(!r.ok||!d.success)throw new Error(d.message||'Historical data unavailable');
      const candles=d.data||d.candles||d.history||[];
      localChart(wrap,instrument,candles);
      const status=document.getElementById('azChartStatus');if(status)status.textContent='Angel One · '+(instrument.symbol||instrument.name||'Instrument')+' · '+candles.length+' candles';
      const hint=document.getElementById('azChartHint');if(hint)hint.textContent='Instrument-specific Angel One chart. Chart AI reads the same candle data automatically.';
      return true;
    }catch(e){console.error('Local chart error:',e);return false;}
  }

  function mount(symbol,instrument){
    const wrap=document.getElementById('azChartWrap'); if(!wrap)return;
    wrap.innerHTML='<div class="az-loading">Loading '+String(instrument.symbol||instrument.name||'instrument')+' chart…</div>';
    loadLocal(wrap,instrument);
    // TradingView is an enhancement. If it loads successfully, it replaces the local chart;
    // if it does not, the local Angel One chart remains available.
    window.setTimeout(function(){
      if(wrap.querySelector('.az-canvas')){
        // Keep the reliable local chart rather than risking an empty cross-origin iframe.
        return;
      }
      const host=document.createElement('div');host.className='tradingview-widget-container';host.style.cssText='height:100%;width:100%;min-height:0;';
      const widget=document.createElement('div');widget.className='tradingview-widget-container__widget';widget.style.cssText='height:100%;width:100%;min-height:0;';host.appendChild(widget);wrap.innerHTML='';wrap.appendChild(host);
      const script=document.createElement('script');script.src='https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';script.async=true;script.type='text/javascript';
      script.innerHTML=JSON.stringify({autosize:true,width:'100%',height:'100%',symbol,interval:'D',timezone:'exchange',theme:'dark',style:'1',locale:'en',withdateranges:true,hide_side_toolbar:false,allow_symbol_change:true,show_popup_button:false,save_image:false,calendar:false,support_host:'https://www.tradingview.com',studies:['Volume@tv-basicstudies','RSI@tv-basicstudies','MACD@tv-basicstudies','Moving Average@tv-basicstudies','Moving Average Exponential@tv-basicstudies']});
      host.appendChild(script);
    },1200);
  }

  function loadPhase4(){if(!document.querySelector('script[src="/static/azad_phase4.js"]')){const s=document.createElement('script');s.src='/static/azad_phase4.js';s.defer=true;document.body.appendChild(s)}}
  function loadChartAI(){if(!document.querySelector('script[src="/static/chart_ai.js"]')){const s=document.createElement('script');s.src='/static/chart_ai.js';s.defer=true;document.body.appendChild(s)}}

  function install(){
    if(window.__azTradingViewInstalled)return true;
    if(typeof window.openInstrument!=='function')return false;
    const modal=document.getElementById('azModal');if(!modal)return false;
    const original=window.openInstrument;window.__azTradingViewOriginalOpenInstrument=original;
    window.openInstrument=function(raw){
      const instrument=raw||{};let result;
      try{result=original(instrument)}catch(e){console.error('Original instrument analysis failed:',e)}
      return Promise.resolve(result).then(function(){
        if(!modal.classList.contains('open')){modal.classList.add('open');modal.setAttribute('aria-hidden','false');document.body.style.overflow='hidden'}
        if(typeof window.switchTab==='function')window.switchTab('chart');
        mount(symbolForInstrument(instrument),instrument);
        setTimeout(loadChartAI,250);
      });
    };
    window.__azTradingViewInstalled=true;loadPhase4();loadChartAI();return true;
  }
  function boot(){if(install())return;setTimeout(install,100);setTimeout(install,500);setTimeout(install,1200);setTimeout(install,2500)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
