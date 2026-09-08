/* Chart AI context surface: selected visual/file context + explicit user action. */
(function(){
  'use strict';
  const MAX_MB = 8;
  const imageTypes = ['image/jpeg','image/jpg','image/png','image/webp'];
  function esc(s){return String(s||'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}
  function current(){return window.__azP4Current || window.currentInstrument || {} }
  function inject(){
    const wrap=document.getElementById('azChartWrap');
    const toolbar=document.querySelector('.az-chart-toolbar');
    if(!wrap||!toolbar||document.getElementById('azChartAiBtn')) return !!wrap;
    const css=document.createElement('style');css.id='azChartAiCss';css.textContent=`
      .az-ai-attach{border:1px solid #29445d;background:#091827;color:#cfe2f5;border-radius:8px;padding:7px 10px;font-size:9px;font-weight:900;cursor:pointer}
      .az-ai-attach:hover{background:rgba(72,167,255,.14);border-color:#4d9ddd}
      .az-ai-context{display:none;position:absolute;left:10px;right:10px;bottom:10px;z-index:5;background:rgba(7,17,31,.96);border:1px solid #29445d;border-radius:10px;padding:9px;box-shadow:0 12px 30px rgba(0,0,0,.35)}
      .az-ai-context.open{display:block}.az-ai-context-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.az-ai-context small{color:#8397ab;font-size:8px}.az-ai-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.az-ai-actions button{border:1px solid #29445d;background:#10243a;color:#fff;border-radius:7px;padding:6px 9px;font-size:8px;font-weight:900;cursor:pointer}.az-ai-actions .primary{background:rgba(72,167,255,.14);border-color:#4d9ddd}.az-ai-preview{margin-top:7px;max-height:130px;overflow:auto;color:#aebfd0;font-size:9px}.az-ai-preview img{max-height:110px;max-width:180px;border-radius:6px;border:1px solid #29445d;display:block;margin-top:5px}.az-ai-menu{display:none;position:absolute;top:42px;left:0;z-index:20;background:#0b1a2a;border:1px solid #29445d;border-radius:10px;padding:6px;box-shadow:0 15px 40px rgba(0,0,0,.45);min-width:150px}.az-ai-menu.open{display:block}.az-ai-menu button{display:block;width:100%;text-align:left;border:0;background:transparent;color:#cfe2f5;padding:8px;border-radius:6px;font-size:9px;cursor:pointer}.az-ai-menu button:hover{background:#10243a}
    `;document.head.appendChild(css);
    const holder=document.createElement('span');holder.style.cssText='position:relative;display:inline-block';
    holder.innerHTML='<button id="azChartAiBtn" class="az-ai-attach" type="button">📎 Chart AI</button><div id="azChartAiMenu" class="az-ai-menu"><button data-kind="camera">📷 Camera</button><button data-kind="image">🖼 Picture / JPG</button><button data-kind="pdf">📄 PDF</button></div>';
    toolbar.insertBefore(holder, toolbar.firstChild);
    const input=document.createElement('input');input.type='file';input.id='azChartAiFile';input.hidden=true;document.body.appendChild(input);
    let selected=null;
    const menu=document.getElementById('azChartAiMenu');
    document.getElementById('azChartAiBtn').onclick=()=>menu.classList.toggle('open');
    holder.querySelectorAll('[data-kind]').forEach(b=>b.onclick=()=>{menu.classList.remove('open');input.accept=b.dataset.kind==='pdf'?'application/pdf':'image/*';input.capture=b.dataset.kind==='camera'?'environment':null;input.click()});
    input.onchange=()=>{
      const f=input.files&&input.files[0];if(!f)return;
      if(f.size>MAX_MB*1024*1024){alert('Please choose a file up to '+MAX_MB+' MB.');input.value='';return}
      if(f.type!=='application/pdf'&&!imageTypes.includes(f.type)){alert('Supported: PDF, JPG/JPEG, PNG or WebP.');input.value='';return}
      selected=f;showContext(f);
    };
    const context=document.createElement('div');context.id='azChartAiContext';context.className='az-ai-context';context.innerHTML='<div class="az-ai-context-head"><b>Selected context</b><button class="az-ai-actions" id="azAiClear" type="button">× Clear</button></div><div class="az-ai-preview" id="azAiPreview"></div><div class="az-ai-actions"><button class="primary" id="azAiAnalyze" type="button">✦ Analyze with Chart AI</button><button id="azAiRemove" type="button">Remove</button></div>';
    wrap.style.position='relative';wrap.appendChild(context);
    document.getElementById('azAiClear').onclick=clear;document.getElementById('azAiRemove').onclick=clear;
    document.getElementById('azAiAnalyze').onclick=()=>selected&&analyze(selected);
    function showContext(f){context.classList.add('open');const p=document.getElementById('azAiPreview');p.innerHTML='<b>'+esc(f.name)+'</b> · '+Math.round(f.size/1024)+' KB · '+esc(f.type||'unknown');if(imageTypes.includes(f.type)){const u=URL.createObjectURL(f);p.innerHTML+='<img src="'+u+'" alt="Selected chart context">'}else p.innerHTML+='<div style="margin-top:5px">PDF selected. Chart AI will read the document and compare it with the current instrument context.</div>'}
    function clear(){selected=null;input.value='';context.classList.remove('open');document.getElementById('azAiPreview').innerHTML=''}
    async function analyze(f){
      const status=document.getElementById('azChartStatus');const old=status?status.textContent:'';if(status)status.textContent='Chart AI · analyzing selected context…';
      const fd=new FormData();fd.append('file',f);fd.append('question','Analyze this selected chart/file in the context of the current market instrument. Identify what the visual/document shows, important technical evidence, possible setup maturity, key support/resistance or levels if visible, risks, and what would invalidate the setup. Do not invent values that are not visible.');fd.append('instrument',JSON.stringify(current()));
      try{const r=await fetch('/api/chart-ai',{method:'POST',body:fd});const d=await r.json();if(!r.ok||!d.success)throw Error(d.message||'Chart AI unavailable');showResult(d.answer);if(status)status.textContent='Chart AI · analysis complete'}catch(e){showResult('Chart AI could not analyze this attachment: '+e.message);if(status)status.textContent=old||'Chart AI · ready'}
    }
    function showResult(text){const p=document.getElementById('azAiPreview');p.innerHTML='<b>Chart AI result</b><div style="white-space:pre-wrap;margin-top:6px;line-height:1.5">'+esc(text)+'</div>';context.classList.add('open')}
    return true;
  }
  function boot(){if(inject())return;setTimeout(inject,300);setTimeout(inject,1200);setTimeout(inject,2500)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  const oldOpen=window.openInstrument; if(typeof oldOpen==='function'&&!window.__chartAiOpenHook){window.__chartAiOpenHook=true;window.openInstrument=function(x){const r=oldOpen.apply(this,arguments);setTimeout(inject,350);setTimeout(inject,1200);return r}}
})();
