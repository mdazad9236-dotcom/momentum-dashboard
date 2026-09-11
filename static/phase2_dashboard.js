/* Phase 2: X10 dashboard intelligence layer. Uses existing /api/scan payload; no new market-data dependency. */
(function(){
  'use strict';
  const CAP_KEY='x10_capital_v1';
  const RISK_KEY='x10_risk_pct_v1';
  const state={stocks:[],indices:[],mode:'top',capital:Number(localStorage.getItem(CAP_KEY)||10000),riskPct:Number(localStorage.getItem(RISK_KEY)||1)};

  const n=v=>{const x=Number(v);return Number.isFinite(x)?x:0};
  const money=v=>n(v).toLocaleString('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2});
  const pct=v=>n(v).toFixed(1)+'%';
  const esc=s=>String(s==null?'':s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const rr=s=>{const d=s&&s.risk_reward_display;if(d&&String(d)!=='0')return String(d);const x=n(s&&s.risk_reward_value||s&&s.risk_reward);return x>0?'1:'+x.toFixed(1):'—'};
  function setup(s){
    const entry=n(s.entry_high||s.entry||s.price), stop=n(s.stop_loss), t1=n(s.target_1||s.target), riskPerShare=Math.max(0,entry-stop), riskCash=state.capital*state.riskPct/100;
    const riskQty=riskPerShare>0?Math.floor(riskCash/riskPerShare):0, capitalQty=entry>0?Math.floor(state.capital/entry):0, qty=Math.max(0,Math.min(riskQty||capitalQty,capitalQty));
    return {entry,stop,t1,riskPerShare,riskCash,riskQty,capitalQty,qty,used:qty*entry,plannedRisk:qty*riskPerShare};
  }
  function regime(indices){
    const names=indices||[];const bull=names.filter(i=>/bull/i.test(String(i.bias||i.market_bias||i.trend||''))).length;const bear=names.filter(i=>/bear/i.test(String(i.bias||i.market_bias||i.trend||''))).length;
    return bull>bear?'BULLISH':bear>bull?'BEARISH':'NEUTRAL';
  }
  function css(){
    if(document.getElementById('azP2css'))return;
    const s=document.createElement('style');s.id='azP2css';s.textContent=`
      #azP2{margin:0 0 22px;border:1px solid #29445d;border-radius:15px;background:linear-gradient(145deg,#0d2135,#081522);box-shadow:0 15px 45px rgba(0,0,0,.22);overflow:hidden}
      .p2head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;border-bottom:1px solid #20384f;background:rgba(72,167,255,.05)}
      .p2title{font-size:14px;font-weight:950}.p2sub{font-size:9px;color:#71879b;margin-top:3px}.p2regime{padding:5px 9px;border-radius:999px;border:1px solid #29445d;background:#091827;font-size:8px;font-weight:900}
      .p2controls{display:flex;align-items:center;gap:6px;padding:10px 12px;border-bottom:1px solid #20384f;flex-wrap:wrap}.p2controls button{border:1px solid #29445d;background:#091827;color:#9fb2c5;border-radius:8px;padding:7px 10px;font-size:9px;font-weight:900;cursor:pointer}.p2controls button.active{background:rgba(72,167,255,.14);border-color:#4d9ddd;color:#e7f3ff}.p2input{height:30px;width:95px;border:1px solid #29445d;border-radius:8px;background:#091827;color:#fff;padding:0 9px;font-size:9px}.p2label{font-size:8px;color:#71879b;font-weight:900}.p2grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;padding:11px}.p2card{border:1px solid #20384f;border-radius:11px;background:#0a1a2a;padding:11px;cursor:pointer}.p2card:hover{border-color:#4d9ddd;transform:translateY(-1px)}.p2top{display:flex;justify-content:space-between;gap:8px}.p2sym{font-size:12px;font-weight:950}.p2rank{font-size:8px;color:#ffb26a;font-weight:900}.p2price{margin-top:4px;font-size:17px;font-weight:950}.p2meta{font-size:8px;color:#71879b;margin-top:3px}.p2bad{color:#ff7f8b}.p2good{color:#20d18b}.p2blue{color:#48a7ff}.p2line{height:1px;background:#20384f;margin:9px 0}.p2metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}.p2m{background:#081522;border-radius:7px;padding:6px}.p2m small{display:block;color:#667f95;font-size:7px}.p2m b{display:block;margin-top:3px;font-size:9px}.p2trade{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-top:7px}.p2trade div{background:#081522;border-radius:7px;padding:6px}.p2trade small{display:block;color:#667f95;font-size:7px}.p2trade b{display:block;margin-top:3px;font-size:8px}.p2badge{display:inline-block;margin-top:8px;border-radius:999px;padding:4px 7px;font-size:7px;font-weight:950;background:rgba(32,209,139,.1);color:#20d18b;border:1px solid rgba(32,209,139,.25)}.p2badge.warn{background:rgba(255,93,108,.09);color:#ff9aa3;border-color:rgba(255,93,108,.25)}.p2empty{padding:22px;text-align:center;color:#71879b;font-size:10px}@media(max-width:1050px){.p2grid{grid-template-columns:1fr 1fr}}@media(max-width:700px){.p2grid{grid-template-columns:1fr}.p2head{align-items:flex-start}.p2controls{align-items:flex-start}.p2trade{grid-template-columns:repeat(2,1fr)}}
    `;document.head.appendChild(s);
  }
  function mount(){
    const anchor=document.getElementById('indices');if(!anchor||document.getElementById('azP2'))return;
    css();const box=document.createElement('section');box.id='azP2';box.innerHTML=`<div class="p2head"><div><div class="p2title">⚡ X10 Opportunity Command</div><div class="p2sub">Best validated setups first · early momentum separated from extended moves</div></div><div id="p2regime" class="p2regime">MARKET REGIME · —</div></div><div class="p2controls"><span class="p2label">VIEW</span><button data-view="top" class="active">Top X10</button><button data-view="early">Early Momentum</button><button data-view="value">Affordable</button><span class="p2label">CAPITAL</span><input id="p2capital" class="p2input" inputmode="decimal" type="number" min="1000" step="500" value="${state.capital}"><span class="p2label">RISK %</span><input id="p2risk" class="p2input" inputmode="decimal" type="number" min="0.25" max="5" step="0.25" value="${state.riskPct}"><span class="p2label">per trade</span></div><div id="p2grid" class="p2grid"></div>`;
    anchor.parentNode.insertBefore(box,anchor);
    box.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{state.mode=b.dataset.view;box.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));render()});
    const cap=box.querySelector('#p2capital'),risk=box.querySelector('#p2risk');cap.onchange=()=>{state.capital=Math.max(1000,n(cap.value));localStorage.setItem(CAP_KEY,String(state.capital));render()};risk.onchange=()=>{state.riskPct=Math.max(.25,Math.min(5,n(risk.value)||1));risk.value=state.riskPct;localStorage.setItem(RISK_KEY,String(state.riskPct));render()};
  }
  function ordered(){
    let list=state.stocks.slice();
    if(state.mode==='early')list=list.filter(s=>/EARLY ACCELERATION|BUILDING MOMENTUM/i.test(String(s.momentum_stage||''))).sort((a,b)=>n(b.early_momentum_score)-n(a.early_momentum_score));
    else if(state.mode==='value')list.sort((a,b)=>n(a.price)-n(b.price));
    else list.sort((a,b)=>n(b.opportunity_rank||b.x10_score)-n(a.opportunity_rank||a.x10_score));
    return list.slice(0,6);
  }
  function render(){
    const grid=document.getElementById('p2grid');if(!grid)return;const reg=document.getElementById('p2regime');if(reg)reg.textContent='MARKET REGIME · '+regime(state.indices);
    const list=ordered();if(!list.length){grid.innerHTML='<div class="p2empty">Waiting for X10 market data… The background scanner will populate this automatically.</div>';return;}
    grid.innerHTML=list.map((s,i)=>{const p=setup(s),score=n(s.x10_score),early=n(s.early_momentum_score),chase=!!s.dont_chase,good=score>=70&&!chase&&n(s.risk_reward_value)>=1.5;const stage=String(s.momentum_stage||'WATCH');return `<article class="p2card" data-symbol="${esc(s.symbol)}"><div class="p2top"><div><div class="p2sym">${esc(s.symbol)}</div><div class="p2meta">${esc(stage)} · ${esc(s.signal||'—')}</div></div><div class="p2rank">#${i+1}</div></div><div class="p2price">${money(s.price)}</div><div class="p2metrics"><div class="p2m"><small>X10</small><b class="${score>=70?'p2good':''}">${score.toFixed(0)}</b></div><div class="p2m"><small>EARLY</small><b>${early.toFixed(0)}</b></div><div class="p2m"><small>R:R</small><b>${esc(rr(s))}</b></div></div><div class="p2trade"><div><small>ENTRY</small><b>${money(s.entry_low||s.entry)}–${money(s.entry_high||s.entry)}</b></div><div><small>STOP</small><b class="p2bad">${money(s.stop_loss)}</b></div><div><small>T1</small><b class="p2good">${money(s.target_1||s.target)}</b></div><div><small>QTY</small><b>${p.qty||'—'}</b></div></div><div class="p2trade"><div><small>CAPITAL USED</small><b>${money(p.used)}</b></div><div><small>RISK</small><b>${money(p.plannedRisk)}</b></div><div><small>SUPPORT</small><b>${money(s.support)}</b></div><div><small>RESIST.</small><b>${money(s.resistance)}</b></div></div><span class="p2badge ${chase?'warn':''}">${chase?'DON’T CHASE':good?'X10 ACTION ZONE':'WATCH / VALIDATE'}</span></article>`}).join('');
    grid.querySelectorAll('.p2card').forEach(card=>card.onclick=()=>{const s=state.stocks.find(x=>String(x.symbol)===card.dataset.symbol);if(s&&typeof window.openInstrument==='function')window.openInstrument(s)});
  }
  function ingest(payload){
    if(!payload||!payload.success)return;state.stocks=Array.isArray(payload.top_opportunities)&&payload.top_opportunities.length?payload.top_opportunities.slice():Array.isArray(payload.stocks)?payload.stocks.slice():[];state.indices=Array.isArray(payload.indices)?payload.indices.slice():[];mount();render();
  }
  function hookFetch(){
    if(window.__azP2FetchHook)return;window.__azP2FetchHook=true;const of=window.fetch;window.fetch=function(){const args=arguments;return of.apply(this,args).then(r=>{try{const u=String(args[0]&&args[0].url||args[0]||'');if(u.includes('/api/scan'))r.clone().json().then(ingest).catch(()=>{})}catch(e){}return r})};
  }
  function boot(){mount();hookFetch();setTimeout(()=>{const existing=window.stocks;if(Array.isArray(existing)&&existing.length)ingest({success:true,stocks:existing,indices:window.indices||[]})},1200);setTimeout(()=>{if(!document.getElementById('azP2'))mount()},2500)}
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot,{once:true}):boot();
  window.Phase2Dashboard={refresh:render,ingest};
})();
