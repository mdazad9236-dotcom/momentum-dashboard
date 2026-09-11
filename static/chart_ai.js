/* Chart AI: automatic analysis of the currently selected instrument. No upload/screenshot required. */
(function(){
  'use strict';

  function current(){return window.__azP4Current || window.currentInstrument || {};}
  function esc(s){return String(s||'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}

  function loadPhase2(){
    if(document.querySelector('script[src="/static/phase2_dashboard.js"]'))return;
    const s=document.createElement('script');s.src='/static/phase2_dashboard.js';s.defer=true;document.body.appendChild(s);
  }

  function inject(){
    const toolbar=document.querySelector('.az-chart-toolbar');
    const wrap=document.getElementById('azChartWrap');
    if(!toolbar||!wrap)return false;
    if(document.getElementById('azChartAiBtn'))return true;

    const style=document.createElement('style');
    style.id='azAutoChartAiCss';
    style.textContent=`
      .az-auto-ai-btn{border:1px solid #29445d!important;background:linear-gradient(135deg,rgba(72,167,255,.16),rgba(72,167,255,.06))!important;color:#dcecff!important;font-weight:950!important}
      .az-auto-ai-btn.busy{opacity:.65;cursor:wait}
      .az-chart-ai-result{margin-top:9px;border:1px solid #29445d;border-radius:11px;background:linear-gradient(145deg,#0b1a2a,#081522);padding:11px;max-height:220px;overflow:auto;display:none}
      .az-chart-ai-result.open{display:block}
      .az-chart-ai-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}
      .az-chart-ai-head b{font-size:10px}.az-chart-ai-meta{font-size:8px;color:#71879b}
      .az-chart-ai-body{white-space:pre-wrap;font-size:10px;line-height:1.55;color:#b8c9d9}
      .az-chart-ai-error{color:#ff9aa3}.az-chart-ai-ok{color:#20d18b}
    `;
    document.head.appendChild(style);

    const button=document.createElement('button');
    button.id='azChartAiBtn';
    button.type='button';
    button.className='az-auto-ai-btn';
    button.textContent='✦ Chart AI: Auto Analyze';
    button.title='Analyze the selected stock/index automatically from its chart data';
    toolbar.insertBefore(button,toolbar.firstChild);

    const result=document.createElement('div');
    result.id='azChartAiResult';
    result.className='az-chart-ai-result';
    result.innerHTML='<div class="az-chart-ai-head"><b>✦ Chart AI</b><span class="az-chart-ai-meta">Waiting for instrument data…</span></div><div class="az-chart-ai-body">Select a stock or index. Its own historical candles will be loaded automatically and analyzed here.</div>';
    wrap.parentElement.appendChild(result);

    button.onclick=()=>analyze(true);
    return true;
  }

  function setResult(text,ok){
    const box=document.getElementById('azChartAiResult');
    if(!box)return;
    box.classList.add('open');
    box.innerHTML='<div class="az-chart-ai-head"><b>✦ Chart AI</b><span class="az-chart-ai-meta">'+(ok?'Automatic chart analysis':'Analysis issue')+'</span></div><div class="az-chart-ai-body '+(ok?'':'az-chart-ai-error')+'">'+esc(text)+'</div>';
  }

  function status(text){const s=document.getElementById('azChartStatus');if(s)s.textContent=text;}

  async function analyze(manual){
    if(!inject())return;
    const instrument=current();
    const symbol=String(instrument.symbol||instrument.name||'').trim();
    if(!symbol){setResult('No stock is selected yet. Open an X10 stock analysis first.',false);return;}

    const button=document.getElementById('azChartAiBtn');
    if(button){button.classList.add('busy');button.textContent='✦ Chart AI: Reading chart…';}
    status('Chart AI · loading '+symbol+' candles…');

    try{
      const isIndex=!!instrument.isIndex;
      const endpoint=isIndex?('/api/index-historical/'+encodeURIComponent(instrument.name||symbol)):('/api/historical/'+encodeURIComponent(symbol));
      const response=await fetch(endpoint,{headers:{'Accept':'application/json'},cache:'no-store'});
      const data=await response.json();
      if(!response.ok||!data.success)throw new Error(data.message||'Historical chart data unavailable');
      const candles=data.data||data.candles||data.history||[];
      if(!Array.isArray(candles)||!candles.length)throw new Error('No historical candles returned for '+symbol);

      status('Chart AI · analyzing '+symbol+' ('+candles.length+' candles)…');
      const aiResponse=await fetch('/api/chart-ai/data',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({instrument:instrument,candles:candles})});
      const ai=await aiResponse.json();
      if(!aiResponse.ok||!ai.success)throw new Error(ai.message||'Chart AI request failed');
      setResult(ai.answer||'No analysis returned.',true);
      status('Chart AI · '+symbol+' analysis complete');
    }catch(error){
      setResult('Chart AI could not analyze '+symbol+'. '+error.message+' The chart data must be available from Angel One for automatic analysis.',false);
      status('Chart AI · unavailable');
    }finally{
      if(button){button.classList.remove('busy');button.textContent='✦ Chart AI: Auto Analyze';}
    }
  }

  function boot(){
    loadPhase2();
    if(!inject()){setTimeout(boot,300);return;}
    setTimeout(()=>analyze(false),700);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  window.__azAutoChartAI={analyze:()=>analyze(true)};
})();
