// Phase 3 stock opportunity card helpers.
// Adds resilient chart-data handling and actionable client-side alerts.
(function(){
  'use strict';

  window.Phase3StockCard = {
    riskReward(entry, stopLoss, target) {
      const e = Number(entry), s = Number(stopLoss), t = Number(target);
      if (![e,s,t].every(Number.isFinite) || e === s) return null;
      const risk = Math.abs(e - s), reward = Math.abs(t - e);
      return { risk, reward, ratio: reward / risk };
    },
    formatRR(entry, stopLoss, target) {
      const rr = this.riskReward(entry, stopLoss, target);
      return rr ? `1:${rr.ratio.toFixed(1)}` : '—';
    },
    chartDefaults() {
      return { timeframe: '1W', intervals: ['1W','1M'], tools: ['crosshair','horizontal-line','trendline','support-resistance','zoom','reset'] };
    },
    renderChartControls(container, onChange) {
      if (!container) return;
      container.innerHTML = `<div class="phase3-chart-controls" role="group" aria-label="Chart timeframe and tools">
        <button type="button" data-tf="1W" class="active">Weekly</button>
        <button type="button" data-tf="1M">Monthly</button>
        <span class="chart-tools">
          <button type="button" data-tool="crosshair">Crosshair</button>
          <button type="button" data-tool="trendline">Trendline</button>
          <button type="button" data-tool="horizontal-line">Horizontal</button>
          <button type="button" data-tool="support-resistance">S/R</button>
          <button type="button" data-tool="zoom">Zoom</button>
        </span>
      </div>`;
      container.querySelectorAll('[data-tf]').forEach(btn => btn.addEventListener('click', () => {
        container.querySelectorAll('[data-tf]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        onChange?.({ timeframe: btn.dataset.tf });
      }));
      container.querySelectorAll('[data-tool]').forEach(btn => btn.addEventListener('click', () => onChange?.({ tool: btn.dataset.tool })));
    }
  };

  function isHistoricalUrl(url){
    const u=String(url||'');
    return /^\/api\/(?:historical|index-historical)(?:\/|$)/.test(u) || /\/api\/(?:historical|index-historical)(?:\/|$)/.test(u);
  }

  function fallbackUrl(url){
    const raw=String(url||'');
    if(raw.includes('/api/historical/'))return raw.replace('/api/historical/','/api/v1/stock/').replace(/([?#].*)$/,'');
    return raw;
  }

  function installFetchGuard(){
    if(window.__azPhase3FetchGuard)return;
    const originalFetch=window.fetch;
    if(typeof originalFetch!=='function')return;
    window.__azPhase3FetchGuard=true;

    window.fetch=async function(input,init){
      const requestUrl=typeof input==='string'?input:(input&&input.url)||'';
      if(!isHistoricalUrl(requestUrl)) return originalFetch.apply(this,arguments);

      try{
        const response=await originalFetch.apply(this,arguments);
        const text=await response.clone().text();
        let parsed=null;
        try{ parsed=text?JSON.parse(text):null; }catch(_e){ parsed=null; }
        if(parsed && typeof parsed==='object'){
          return new Response(JSON.stringify(parsed),{status:response.status,statusText:response.statusText,headers:{'Content-Type':'application/json'}});
        }

        // Never let the chart explode on Response.json() when Render/proxy returns
        // an empty body or HTML error page. Give the chart a deterministic JSON error.
        const reason=response.status?`Historical data endpoint returned HTTP ${response.status}.`:'Historical data endpoint returned an empty response.';
        return new Response(JSON.stringify({success:false,message:reason, data:[], status:response.status||0}),{status:response.status||502,headers:{'Content-Type':'application/json'}});
      }catch(error){
        return new Response(JSON.stringify({success:false,message:`Historical data request failed: ${error.message||error}`,data:[]}),{status:502,headers:{'Content-Type':'application/json'}});
      }
    };
  }

  function installAlertPanel(){
    if(document.getElementById('azP3Alerts')) return;
    const css=document.createElement('style');
    css.id='azP3AlertCss';
    css.textContent=`
      #azP3Alerts{position:fixed;right:14px;bottom:64px;z-index:100002}
      #azP3Alerts button{border:1px solid #29445d;background:#0c1c2d;color:#dcecff;border-radius:9px;padding:8px 10px;font-size:10px;font-weight:900;cursor:pointer}
      #azP3AlertPanel{display:none;position:fixed;right:14px;bottom:108px;width:min(360px,calc(100vw - 28px));max-height:62vh;overflow:auto;background:#0a1929;border:1px solid #29445d;border-radius:13px;padding:12px;box-shadow:0 24px 70px rgba(0,0,0,.55)}
      #azP3AlertPanel.open{display:block}
      .azp3a-row{display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid #183149;font-size:10px}
      .azp3a-row:last-child{border:0}.azp3a-muted{color:#8397ab;font-size:9px;line-height:1.45}.azp3a-ok{color:#20d18b}.azp3a-warn{color:#ffb06f}.azp3a-bad{color:#ff5d6c}
    `;
    document.head.appendChild(css);
    const root=document.createElement('div');root.id='azP3Alerts';
    root.innerHTML='<button type="button" id="azP3AlertBtn">🔔 Smart Alerts</button><div id="azP3AlertPanel"><div style="display:flex;justify-content:space-between;gap:8px"><b>Phase 3 Smart Alerts</b><button type="button" id="azP3Close">×</button></div><div class="azp3a-muted" style="margin:7px 0">Monitors the current X10 opportunity data while the dashboard is open.</div><div id="azP3AlertBody"></div></div>';
    document.body.appendChild(root);
    document.getElementById('azP3AlertBtn').onclick=()=>document.getElementById('azP3AlertPanel').classList.toggle('open');
    document.getElementById('azP3Close').onclick=()=>document.getElementById('azP3AlertPanel').classList.remove('open');
    renderAlerts([]);
  }

  function loadAlertState(){
    try{return JSON.parse(localStorage.getItem('azad_phase3_alerts')||'{"enabled":true,"logs":[]}');}catch(_e){return {enabled:true,logs:[]};}
  }
  function saveAlertState(s){try{localStorage.setItem('azad_phase3_alerts',JSON.stringify(s));}catch(_e){}}
  function notify(title,body){try{if('Notification' in window && Notification.permission==='granted')new Notification(title,{body});}catch(_e){}}
  function logAlert(symbol,type,message){
    const st=loadAlertState();
    st.logs.unshift({ts:Date.now(),symbol,type,message});st.logs=st.logs.slice(0,30);saveAlertState(st);notify('Azad AI Plus',`${symbol}: ${message}`);renderAlerts(st.logs);
  }
  function renderAlerts(logs){
    const body=document.getElementById('azP3AlertBody');if(!body)return;
    body.innerHTML=`<div class="azp3a-row"><span>Browser notifications</span><button type="button" id="azP3Notify">Enable</button></div><div class="azp3a-row"><span>Alert engine</span><b class="azp3a-ok">ON</b></div>` + (logs.length?logs.slice(0,10).map(x=>`<div class="azp3a-row"><span><b>${String(x.symbol||'')}</b><br><span class="azp3a-muted">${String(x.message||'')}</span></span><span class="azp3a-muted">${new Date(x.ts).toLocaleTimeString()}</span></div>`).join(''):'<div class="azp3a-muted" style="padding:9px 0">No alerts yet.</div>');
    const b=document.getElementById('azP3Notify');if(b)b.onclick=async()=>{if('Notification' in window){const p=await Notification.requestPermission();if(p==='granted')notify('Azad AI Plus','Browser notifications enabled.')}};
  }

  let previous={};
  function evaluate(stocks){
    const list=Array.isArray(stocks)?stocks:[];
    list.forEach(s=>{
      const symbol=String(s.symbol||'').trim();if(!symbol)return;
      const price=Number(s.price),x10=Number(s.x10_score),early=Number(s.early_momentum_score),rr=Number(s.risk_reward_value||s.risk_reward);
      const old=previous[symbol];
      if(s.dont_chase && !(old&&old.dont_chase))logAlert(symbol,'DON’T CHASE','X10 currently marks the setup as extended or outside the planned entry zone.');
      if(Number.isFinite(x10)&&x10>=80&&!(old&&old.x10>=80))logAlert(symbol,'X10','X10 score reached 80+ (strong setup).');
      if(Number.isFinite(early)&&early>=70&&!(old&&old.early>=70))logAlert(symbol,'EARLY','Early acceleration reached 70+.');
      if(Number.isFinite(rr)&&rr>=2&&!(old&&old.rr>=2))logAlert(symbol,'R:R','Risk/reward reached 1:2 or better.');
      const eLow=Number(s.entry_low),eHigh=Number(s.entry_high),sl=Number(s.stop_loss),t1=Number(s.target_1||s.target);
      if(Number.isFinite(price)&&Number.isFinite(eLow)&&Number.isFinite(eHigh)&&price>=eLow&&price<=eHigh&&!(old&&old.inEntry))logAlert(symbol,'ENTRY','Price is inside the planned entry zone.');
      if(Number.isFinite(price)&&Number.isFinite(sl)&&price<=sl*1.01&&!(old&&old.nearSL))logAlert(symbol,'SL','Price is near the stop-loss level.');
      if(Number.isFinite(price)&&Number.isFinite(t1)&&t1>0&&price>=t1*0.99&&!(old&&old.nearT1))logAlert(symbol,'TARGET','Price is near Target 1.');
      previous[symbol]={price,x10,early,rr,dont_chase:!!s.dont_chase,inEntry:Number.isFinite(price)&&Number.isFinite(eLow)&&Number.isFinite(eHigh)&&price>=eLow&&price<=eHigh,nearSL:Number.isFinite(price)&&Number.isFinite(sl)&&price<=sl*1.01,nearT1:Number.isFinite(price)&&Number.isFinite(t1)&&t1>0&&price>=t1*0.99};
    });
  }

  function hookScanner(){
    if(window.__azP3ScanHook)return true;
    if(typeof window.loadScan!=='function')return false;
    const original=window.loadScan;
    window.loadScan=async function(){const result=await original.apply(this,arguments);try{evaluate(window.stocks||[]);}catch(_e){}return result;};
    window.__azP3ScanHook=true;return true;
  }

  function boot(){installFetchGuard();installAlertPanel();hookScanner();setTimeout(hookScanner,500);setTimeout(hookScanner,1500);}
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot,{once:true}):boot();
})();
