// Phase 3: stock-analysis tools, multi-timeframe helpers and alert rules.
// This layer is deliberately independent from the X10 scoring engine and Phase 2 dashboard logic.
(function(){
  'use strict';

  const ALERT_KEY='azad_phase3_alerts_v1';
  const SETTINGS_KEY='azad_phase3_settings_v1';

  function num(v){const n=Number(v);return Number.isFinite(n)?n:null}
  function money(v){const n=num(v);return n===null?'—':'₹'+n.toFixed(2)}
  function loadJSON(key,fallback){try{return JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback))}catch(e){return fallback}}
  function saveJSON(key,value){try{localStorage.setItem(key,JSON.stringify(value))}catch(e){}}

  function riskReward(entry,stopLoss,target){
    const e=num(entry),s=num(stopLoss),t=num(target);
    if([e,s,t].some(v=>v===null)||e===s)return null;
    const risk=Math.abs(e-s),reward=Math.abs(t-e);
    return {risk,reward,ratio:risk>0?reward/risk:null};
  }

  function resample(candles,frame){
    const rows=Array.isArray(candles)?candles.slice().sort((a,b)=>new Date(a.t)-new Date(b.t)):[];
    if(frame==='1D'||!rows.length)return rows;
    const groups=new Map();
    rows.forEach(r=>{
      const d=new Date(r.t), key=frame==='1W'
        ? `${d.getUTCFullYear()}-W${Math.floor((((d-new Date(Date.UTC(d.getUTCFullYear(),0,1)))/86400000)+new Date(Date.UTC(d.getUTCFullYear(),0,1)).getUTCDay())/7)}`
        : `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`;
      if(!groups.has(key))groups.set(key,[]);
      groups.get(key).push(r);
    });
    return Array.from(groups.values()).map(g=>({
      t:g[g.length-1].t,o:g[0].o,h:Math.max(...g.map(x=>x.h)),l:Math.min(...g.map(x=>x.l)),c:g[g.length-1].c,v:g.reduce((s,x)=>s+(num(x.v)||0),0)
    }));
  }

  function alertRules(stock){
    const s=stock||{};
    const p=num(s.price),entry=num(s.entry),stop=num(s.stop_loss),t1=num(s.target_1||s.target),x10=num(s.x10_score),em=num(s.early_momentum_score);
    const rules=[];
    if(p!==null&&entry!==null&&p>=entry*.98&&p<=entry*1.02)rules.push({type:'ENTRY_ZONE',message:`${s.symbol||'Stock'} is near the planned entry zone (${money(entry)}).`});
    if(p!==null&&stop!==null&&p<=stop*1.02)rules.push({type:'STOP_PROXIMITY',message:`${s.symbol||'Stock'} is approaching the stop-loss level (${money(stop)}).`});
    if(p!==null&&t1!==null&&p>=t1*.98)rules.push({type:'TARGET_PROXIMITY',message:`${s.symbol||'Stock'} is approaching Target 1 (${money(t1)}).`});
    if(x10!==null&&x10>=80)rules.push({type:'X10_STRONG',message:`${s.symbol||'Stock'} has a strong X10 score (${x10.toFixed(0)}).`});
    if(em!==null&&em>=70)rules.push({type:'EARLY_ACCELERATION',message:`${s.symbol||'Stock'} is in an early-acceleration zone (${em.toFixed(0)}).`});
    if(s.dont_chase)rules.push({type:'DONT_CHASE',message:`${s.symbol||'Stock'} is marked DON'T CHASE.`});
    return rules;
  }

  function pushAlerts(stock){
    const settings=loadJSON(SETTINGS_KEY,{enabled:true,push:true});
    if(!settings.enabled||!stock||!stock.symbol)return [];
    const rules=alertRules(stock),history=loadJSON(ALERT_KEY,[]),now=Date.now();
    const emitted=[];
    rules.forEach(rule=>{
      const duplicate=history.find(x=>x.symbol===stock.symbol&&x.type===rule.type&&(now-x.ts)<900000);
      if(duplicate)return;
      const item={...rule,symbol:stock.symbol,ts:now};
      history.unshift(item);emitted.push(item);
      if(settings.push&&typeof Notification!=='undefined'&&Notification.permission==='granted'){
        try{new Notification('Azad AI Alert',{body:rule.message})}catch(e){}
      }
    });
    saveJSON(ALERT_KEY,history.slice(0,100));
    return emitted;
  }

  function requestNotifications(){
    if(typeof Notification==='undefined')return Promise.resolve('unsupported');
    return Notification.requestPermission();
  }

  window.Phase3StockCard={
    riskReward,
    formatRR(entry,stopLoss,target){const rr=riskReward(entry,stopLoss,target);return rr&&rr.ratio!==null?'1:'+rr.ratio.toFixed(1):'—'},
    chartDefaults(){return{timeframe:'1W',intervals:['1D','1W','1M'],tools:['crosshair','horizontal-line','trendline','support-resistance','zoom','reset'] }},
    resample,
    alertRules,
    pushAlerts,
    requestNotifications,
    getAlertHistory(){return loadJSON(ALERT_KEY,[])},
    clearAlertHistory(){saveJSON(ALERT_KEY,[])},
    getSettings(){return loadJSON(SETTINGS_KEY,{enabled:true,push:true})},
    saveSettings(v){saveJSON(SETTINGS_KEY,{...loadJSON(SETTINGS_KEY,{enabled:true,push:true}),...v})},
    renderChartControls(container,onChange){
      if(!container)return;
      container.innerHTML=`<div class="phase3-chart-controls" role="group" aria-label="Chart timeframe and tools">
        <span class="phase3-label">TIMEFRAME</span>
        <button type="button" data-tf="1D" class="active">Daily</button><button type="button" data-tf="1W">Weekly</button><button type="button" data-tf="1M">Monthly</button>
        <span class="chart-tools"><button type="button" data-tool="crosshair">Crosshair</button><button type="button" data-tool="trendline">Trendline</button><button type="button" data-tool="horizontal-line">Horizontal</button><button type="button" data-tool="support-resistance">S/R</button><button type="button" data-tool="zoom">Zoom</button></span>
      </div>`;
      container.querySelectorAll('[data-tf]').forEach(btn=>btn.addEventListener('click',()=>{container.querySelectorAll('[data-tf]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');onChange&&onChange({timeframe:btn.dataset.tf})}));
      container.querySelectorAll('[data-tool]').forEach(btn=>btn.addEventListener('click',()=>onChange&&onChange({tool:btn.dataset.tool})));
    }
  };

  // Optional automatic alert evaluation whenever the dashboard exposes a stock object.
  function evaluate(){
    const s=window.__azP4Current||window.currentInstrument;
    if(s&&s.symbol)pushAlerts(s);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(evaluate,900),{once:true});else setTimeout(evaluate,900);
})();
