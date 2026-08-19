import os
import threading
import time
import requests
from functools import wraps

from flask import Flask, jsonify, render_template, request, redirect, url_for, session

from angel_instruments import AngelInstrumentManager
from angel_service import AngelOneService
from stock_service import StockService
from angel_scanner import AngelScanner

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "x10-marketai-session-key-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "false").lower() == "true"

angel_service = AngelOneService()
stock_service = StockService()
instrument_manager = AngelInstrumentManager()

APP_USER_ID = "Admin"
APP_PASSWORD = "Admin"

SCAN_REFRESH_SECONDS = max(60, int(os.getenv("X10_SCAN_REFRESH_SECONDS", "180")))
_scan_lock = threading.Lock()
_scan_state = {"result": None, "updated_at": 0.0, "refreshing": False, "last_error": None}


def is_authenticated():
    return session.get("authenticated") is True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "authenticated": False, "message": "Authentication required."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def clean_stock(stock):
    fields = ["symbol", "name", "token", "price", "technical_score", "x10_score", "success_probability", "signal", "entry", "entry_low", "entry_high", "stop_loss", "target", "target_1", "target_2", "risk", "reward", "risk_reward", "trailing_stop", "chase_price", "dont_chase", "setup_quality", "trend", "momentum", "rsi", "ema20", "ema50", "ema200", "macd", "macd_signal", "macd_histogram", "adx", "plus_di", "minus_di", "support", "resistance", "volume_ratio", "atr", "52_week_high", "52_week_low", "scan_time"]
    return {field: stock.get(field, 0) for field in fields}


def _run_market_scan():
    with _scan_lock:
        if _scan_state["refreshing"]:
            return False
        _scan_state["refreshing"] = True
    started = time.time()
    try:
        scanner = AngelScanner(batch_size=5, delay=0.03, max_workers=5)
        result = scanner.scan_market(limit=30)
        if not result.get("success"):
            raise RuntimeError(result.get("message", "Angel One scanner failed."))
        stocks = [clean_stock(stock) for stock in result.get("stocks", []) if isinstance(stock, dict)]
        payload = {"success": True, "message": "Market scan completed.", "count": len(stocks), "scanned": result.get("scanned", 0), "successful": result.get("successful", 0), "time_seconds": result.get("time_seconds", round(time.time() - started, 2)), "stocks": stocks, "indices": result.get("indices", []), "updated_at": time.time()}
        with _scan_lock:
            _scan_state["result"] = payload
            _scan_state["updated_at"] = payload["updated_at"]
            _scan_state["last_error"] = None
        return True
    except Exception as error:
        print("BACKGROUND X10 SCANNER ERROR:", error)
        with _scan_lock:
            _scan_state["last_error"] = str(error)
        return False
    finally:
        with _scan_lock:
            _scan_state["refreshing"] = False


def _ensure_scan_refresh(force=False):
    with _scan_lock:
        age = time.time() - _scan_state["updated_at"] if _scan_state["updated_at"] else None
        refreshing = _scan_state["refreshing"]
        stale = age is None or age >= SCAN_REFRESH_SECONDS
    if (force or stale) and not refreshing:
        threading.Thread(target=_run_market_scan, name="x10-market-scan", daemon=True).start()


def _snapshot_response():
    with _scan_lock:
        result = _scan_state["result"]
        updated_at = _scan_state["updated_at"]
        refreshing = _scan_state["refreshing"]
        last_error = _scan_state["last_error"]
    if result:
        payload = dict(result)
        payload["refreshing"] = refreshing
        payload["cache_age_seconds"] = round(max(0, time.time() - updated_at), 1)
        payload["stale"] = payload["cache_age_seconds"] >= SCAN_REFRESH_SECONDS
        return payload
    return {"success": True, "message": "Market scan is warming up in the background.", "count": 0, "scanned": 0, "successful": 0, "time_seconds": 0, "stocks": [], "indices": [], "refreshing": refreshing, "cache_age_seconds": None, "stale": True, "last_error": last_error}


def _background_refresh_loop():
    time.sleep(2)
    while True:
        try:
            _ensure_scan_refresh()
        except Exception as error:
            print("BACKGROUND REFRESH LOOP ERROR:", error)
        time.sleep(15)

threading.Thread(target=_background_refresh_loop, name="x10-refresh-loop", daemon=True).start()


@app.after_request
def inject_angel_chart(response):
    if request.path != "/" or "text/html" not in response.content_type:
        return response
    try:
        html = response.get_data(as_text=True)
        if 'id="chartBox"' not in html:
            return response
        fix = r'''<script>
(function(){
  function parseCandle(x){
    if(Array.isArray(x)) return {t:x[0],o:+x[1],h:+x[2],l:+x[3],c:+x[4],v:+(x[5]||0)};
    return {t:x.date||x.timestamp||x.time||x.ts,o:+(x.open??x.Open),h:+(x.high??x.High),l:+(x.low??x.Low),c:+(x.close??x.Close),v:+(x.volume??x.Volume??0)};
  }
  function drawChart(box,candles,symbol){
    box.innerHTML='';box.style.position='relative';box.style.overflow='hidden';
    const head=document.createElement('div');head.style.cssText='position:absolute;z-index:2;left:14px;top:10px;font:700 12px Inter,Arial;color:#dce9f5;background:rgba(7,17,31,.72);padding:6px 9px;border-radius:7px';head.textContent='ANGEL ONE · '+symbol+' · DAILY';box.appendChild(head);
    const canvas=document.createElement('canvas');canvas.style.cssText='width:100%;height:100%;display:block';box.appendChild(canvas);const ctx=canvas.getContext('2d');
    const resize=()=>{const dpr=window.devicePixelRatio||1,w=Math.max(320,box.clientWidth),h=Math.max(280,box.clientHeight);canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);if(!candles.length){ctx.fillStyle='#8397ab';ctx.font='12px Arial';ctx.fillText('No Angel One candle data available.',20,40);return;}const data=candles.slice(-120),pad={l:54,r:18,t:38,b:62},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b,max=Math.max(...data.map(d=>d.h)),min=Math.min(...data.map(d=>d.l)),span=(max-min)||1,volMax=Math.max(...data.map(d=>d.v||0),1),volH=Math.min(70,ch*.18),priceH=ch-volH-12,py=p=>pad.t+(max-p)/span*priceH,step=cw/data.length,body=Math.max(2,step*.62);ctx.fillStyle='#07111f';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#183149';ctx.lineWidth=1;ctx.fillStyle='#71879b';ctx.font='10px Arial';for(let i=0;i<5;i++){const y=pad.t+(priceH/4)*i;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();const val=max-span*i/4;ctx.fillText(val.toFixed(2),7,y+3);}data.forEach((d,i)=>{const x=pad.l+i*step+step/2,up=d.c>=d.o,yO=py(d.o),yC=py(d.c),yH=py(d.h),yL=py(d.l);ctx.strokeStyle=up?'#20d18b':'#ff5d6c';ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x,yH);ctx.lineTo(x,yL);ctx.stroke();ctx.fillRect(x-body/2,Math.min(yO,yC),body,Math.max(1,Math.abs(yC-yO)));if(i%Math.ceil(data.length/6)===0){const dt=new Date(d.t),label=isNaN(dt)?String(d.t).slice(0,10):dt.toLocaleDateString('en-IN',{day:'2-digit',month:'short'});ctx.fillStyle='#71879b';ctx.fillText(label,x-18,h-20);}});const volTop=pad.t+priceH+12;data.forEach((d,i)=>{const x=pad.l+i*step+step/2,vh=((d.v||0)/volMax)*volH;ctx.fillStyle=d.c>=d.o?'rgba(32,209,139,.45)':'rgba(255,93,108,.45)';ctx.fillRect(x-body/2,volTop+volH-vh,body,vh);});ctx.fillStyle='#71879b';ctx.fillText('Volume',pad.l,volTop+volH+18);const last=data[data.length-1];ctx.fillStyle=last.c>=last.o?'#20d18b':'#ff5d6c';ctx.font='800 14px Arial';ctx.fillText('₹'+last.c.toFixed(2),w-pad.r-82,pad.t+18);};if(window.ResizeObserver)new ResizeObserver(resize).observe(box);resize();
  }
  window.loadChart=async function(sym){let raw=(sym||(document.getElementById('tv')||{}).value||'NIFTY').toUpperCase().trim().replace(/^NSE:/,'').replace(/[^A-Z0-9_]/g,'');if(!raw)raw='NIFTY';const input=document.getElementById('tv');if(input)input.value=raw;const box=document.getElementById('chartBox');if(!box)return;box.innerHTML='<div class="empty">Loading Angel One candles for '+raw+'…</div>';try{const r=await fetch('/api/historical/'+encodeURIComponent(raw),{cache:'no-store'}),j=await r.json();if(!r.ok||!j.success)throw new Error(j.message||'Angel One historical data unavailable.');const candles=(j.data||j.candles||[]).map(parseCandle).filter(d=>[d.o,d.h,d.l,d.c].every(Number.isFinite));if(!candles.length)throw new Error('Angel One returned no candle data for '+raw+'.');drawChart(box,candles,raw);}catch(e){box.innerHTML='<div class="empty">Angel One chart error: '+String(e.message||e)+'</div>';}};
  window.addEventListener('load',function(){setTimeout(function(){if(document.getElementById('chartBox'))window.loadChart('NIFTY');},150);});
  setTimeout(function(){document.querySelectorAll('a[href="#chart"]').forEach(function(a){a.addEventListener('click',function(){setTimeout(function(){if(document.getElementById('chartBox'))window.loadChart();},50);});});},0);
})();
</script>'''
        html=html.replace('</body>',fix+'</body>')
        html=html.replace('TradingView Chart','Angel One Chart').replace('Reliable direct TradingView embed','Angel One OHLC candles')
        response.set_data(html)
    except Exception as error:
        print('ANGEL CHART INJECTION ERROR:',error)
    return response


@app.after_request
def inject_compact_assistant_and_stock_popup(response):
    if request.path != "/" or "text/html" not in response.content_type:
        return response
    try:
        html = response.get_data(as_text=True)
        ui = r'''<style>
/* Compact AI assistant */
.assistant{min-height:250px!important;grid-template-columns:1fr 250px!important}.chat{padding:12px!important}.messages{max-height:145px!important;min-height:90px}.msg{padding:7px 10px!important;margin:4px 0!important;font-size:11px!important;line-height:1.35!important}.quick{padding:12px!important}.quick button{margin:5px 0!important;padding:7px 9px!important;font-size:10px!important}.notice{font-size:9px!important}.assistant .head{margin-bottom:7px!important}
/* Stock detail modal */
.az-stock-modal{position:fixed;inset:0;z-index:99999;background:rgba(2,8,15,.78);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;padding:20px}.az-stock-modal.open{display:flex}.az-stock-dialog{width:min(1180px,96vw);height:min(760px,92vh);background:linear-gradient(145deg,#10243a,#081522);border:1px solid #29445d;border-radius:18px;box-shadow:0 30px 100px rgba(0,0,0,.6);overflow:hidden;display:flex;flex-direction:column}.az-stock-head{height:62px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;border-bottom:1px solid #20384f}.az-stock-title b{font-size:19px}.az-stock-title span{display:block;color:#8397ab;font-size:10px;margin-top:3px}.az-close{width:34px;height:34px;border:1px solid #29445d;border-radius:9px;background:#091827;color:#fff;font-size:20px;cursor:pointer}.az-stock-body{display:grid;grid-template-columns:1.45fr 1fr;gap:14px;padding:14px;overflow:auto;flex:1}.az-popup-chart{height:100%;min-height:430px;background:#07111f;border:1px solid #20384f;border-radius:12px;position:relative;overflow:hidden}.az-popup-panel{display:flex;flex-direction:column;gap:10px}.az-dna-card{background:#0b1a2a;border:1px solid #20384f;border-radius:12px;padding:13px}.az-dna-card h3{margin:0 0 10px;font-size:13px}.az-trade-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.az-trade-item{background:#081522;border:1px solid #183149;border-radius:8px;padding:9px}.az-trade-item small{display:block;color:#71879b;font-size:8px}.az-trade-item b{display:block;margin-top:4px;font-size:12px}.az-dna-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.az-dna-grid div{background:#081522;border-radius:8px;padding:8px}.az-dna-grid small{display:block;color:#71879b;font-size:8px}.az-dna-grid b{display:block;margin-top:4px;font-size:11px}.az-popup-loading,.az-popup-error{display:flex;align-items:center;justify-content:center;height:100%;color:#8397ab;font-size:11px;text-align:center;padding:20px}.az-popup-error{color:#ff8792}
@media(max-width:800px){.az-stock-modal{padding:8px}.az-stock-dialog{width:98vw;height:94vh}.az-stock-body{grid-template-columns:1fr}.az-popup-chart{min-height:300px}.az-dna-grid{grid-template-columns:repeat(2,1fr)}.assistant{grid-template-columns:1fr!important}.quick{display:none}}
</style>
<div class="az-stock-modal" id="azStockModal" aria-hidden="true"><div class="az-stock-dialog" role="dialog" aria-modal="true"><div class="az-stock-head"><div class="az-stock-title"><b id="azModalName">Stock Details</b><span id="azModalSub">Angel One · X10</span></div><button class="az-close" id="azModalClose" aria-label="Close">×</button></div><div class="az-stock-body"><div class="az-popup-chart" id="azPopupChart"><div class="az-popup-loading">Loading Angel One chart…</div></div><div class="az-popup-panel" id="azPopupPanel"><div class="az-dna-card"><h3>🔬 Stock DNA</h3><div class="az-dna-grid" id="azDnaGrid"></div></div><div class="az-dna-card"><h3>🎯 Trade Plan</h3><div class="az-trade-grid" id="azTradeGrid"></div><div id="azChase" class="hint" style="margin-top:9px"></div></div></div></div></div></div>
<script>
(function(){
  const modal=()=>document.getElementById('azStockModal'),esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=v=>Number.isFinite(Number(v))?'₹'+Number(v).toFixed(2):'—',num=v=>Number.isFinite(Number(v))?Number(v).toFixed(2):'—';
  function openModal(s){
    if(!s||!s.symbol)return;
    const m=modal();m.classList.add('open');m.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';
    document.getElementById('azModalName').textContent=s.name||s.symbol;document.getElementById('azModalSub').textContent=(s.symbol||'')+' · Angel One · X10 '+num(s.x10_score);
    document.getElementById('azDnaGrid').innerHTML=[['PRICE',money(s.price)],['X10',num(s.x10_score)],['SIGNAL',s.signal],['TREND',s.trend],['MOMENTUM',s.momentum],['RSI',num(s.rsi)],['MACD',num(s.macd)],['ADX',num(s.adx)],['R:R',num(s.risk_reward)]].map(x=>`<div><small>${esc(x[0])}</small><b>${esc(x[1])}</b></div>`).join('');
    document.getElementById('azTradeGrid').innerHTML=[['ENTRY',money(s.entry_low)+' – '+money(s.entry_high)],['STOP LOSS',money(s.stop_loss)],['TARGET 1',money(s.target_1||s.target)],['TARGET 2',money(s.target_2)],['TRAILING',money(s.trailing_stop)],['SUPPORT / RESISTANCE',money(s.support)+' / '+money(s.resistance)]].map(x=>`<div class="az-trade-item"><small>${esc(x[0])}</small><b>${esc(x[1])}</b></div>`).join('');
    document.getElementById('azChase').textContent=s.dont_chase?'⚠ Don’t chase — wait for the planned entry zone.':'✓ Setup is inside the actionable range.';
    loadPopupChart(s.symbol);
  }
  function closeModal(){const m=modal();m.classList.remove('open');m.setAttribute('aria-hidden','true');document.body.style.overflow='';}
  async function loadPopupChart(symbol){const box=document.getElementById('azPopupChart');box.innerHTML='<div class="az-popup-loading">Loading Angel One candles…</div>';try{const r=await fetch('/api/historical/'+encodeURIComponent(symbol),{cache:'no-store'}),j=await r.json();if(!r.ok||!j.success)throw new Error(j.message||'Angel One historical data unavailable.');const raw=j.data||j.candles||[];const data=raw.map(x=>Array.isArray(x)?{t:x[0],o:+x[1],h:+x[2],l:+x[3],c:+x[4],v:+(x[5]||0)}:{t:x.date||x.timestamp||x.time||x.ts,o:+(x.open??x.Open),h:+(x.high??x.High),l:+(x.low??x.Low),c:+(x.close??x.Close),v:+(x.volume??x.Volume??0)}).filter(d=>[d.o,d.h,d.l,d.c].every(Number.isFinite));if(!data.length)throw new Error('No Angel One candle data returned.');drawPopupChart(box,data,symbol);}catch(e){box.innerHTML='<div class="az-popup-error">Angel One chart error:<br>'+esc(e.message||e)+'</div>';}}
  function drawPopupChart(box,data,symbol){box.innerHTML='';const title=document.createElement('div');title.style.cssText='position:absolute;left:12px;top:10px;z-index:2;color:#dce9f5;background:rgba(7,17,31,.78);padding:6px 9px;border-radius:7px;font:700 11px Arial';title.textContent='ANGEL ONE · '+symbol+' · DAILY';box.appendChild(title);const c=document.createElement('canvas');c.style.cssText='width:100%;height:100%;display:block';box.appendChild(c);const ctx=c.getContext('2d');function paint(){const dpr=devicePixelRatio||1,w=box.clientWidth,h=box.clientHeight;c.width=w*dpr;c.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#07111f';ctx.fillRect(0,0,w,h);const a=data.slice(-100),pad={l:55,r:15,t:38,b:55},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b,max=Math.max(...a.map(x=>x.h)),min=Math.min(...a.map(x=>x.l)),span=max-min||1,step=cw/a.length,body=Math.max(2,step*.62),py=p=>pad.t+(max-p)/span*ch;ctx.strokeStyle='#183149';ctx.fillStyle='#71879b';ctx.font='9px Arial';for(let i=0;i<5;i++){let y=pad.t+ch*i/4;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillText((max-span*i/4).toFixed(2),5,y+3);}a.forEach((x,i)=>{let px=pad.l+i*step+step/2,up=x.c>=x.o,y1=py(x.o),y2=py(x.c);ctx.strokeStyle=up?'#20d18b':'#ff5d6c';ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(px,py(x.h));ctx.lineTo(px,py(x.l));ctx.stroke();ctx.fillRect(px-body/2,Math.min(y1,y2),body,Math.max(1,Math.abs(y2-y1)));});const last=a[a.length-1];ctx.fillStyle=last.c>=last.o?'#20d18b':'#ff5d6c';ctx.font='800 14px Arial';ctx.fillText('₹'+last.c.toFixed(2),w-90,24);}paint();window.addEventListener('resize',paint);}
  function wrap(){if(window.showStock&&!window.showStock.__azWrapped){const original=window.showStock;function wrapped(s){openModal(s)}wrapped.__azWrapped=true;window.showStock=wrapped;}if(window.showStockBySymbol&&!window.showStockBySymbol.__azWrapped){const original=window.showStockBySymbol;function wrappedSymbol(sym){const s=(window.stocks||[]).find(x=>x.symbol===sym);if(s)openModal(s);else original(sym)}wrappedSymbol.__azWrapped=true;window.showStockBySymbol=wrappedSymbol;}}
  document.addEventListener('DOMContentLoaded',function(){document.getElementById('azModalClose').onclick=closeModal;modal().addEventListener('click',e=>{if(e.target===modal())closeModal()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});setTimeout(wrap,250);setTimeout(wrap,1000);});
  const oldSet=window.setInterval;window.setInterval=function(fn,ms){return oldSet(fn,ms)};
  const observer=new MutationObserver(wrap);observer.observe(document.body,{childList:true,subtree:true});
})();
</script>'''
        html=html.replace('</body>',ui+'</body>')
        response.set_data(html)
    except Exception as error:
        print('COMPACT UI INJECTION ERROR:',error)
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        if request.form.get("user_id", "") == APP_USER_ID and request.form.get("password", "") == APP_PASSWORD:
            session.clear()
            session["authenticated"] = True
            session["user_id"] = APP_USER_ID
            return redirect(url_for("home"))
        error = "Invalid User ID or Password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/api/analyze/<symbol>")
@login_required
def analyze_stock(symbol):
    try:
        result = stock_service.get_stock_analysis(symbol.upper().strip())
        if not result:
            return jsonify({"success": False, "message": "No analysis result returned."}), 500
        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


@app.route("/api/scan")
@login_required
def scan():
    _ensure_scan_refresh()
    return jsonify(_snapshot_response())


@app.route("/api/scan/refresh")
@login_required
def scan_refresh():
    _ensure_scan_refresh(force=True)
    return jsonify({"success": True, "message": "X10 scan refresh started in background.", "refreshing": True})


@app.route("/api/indices")
@login_required
def indices_endpoint():
    _ensure_scan_refresh()
    snapshot = _snapshot_response()
    return jsonify({"success": True, "indices": snapshot.get("indices", []), "cached": True, "refreshing": snapshot.get("refreshing", False)})


@app.route("/api/historical/<symbol>")
@login_required
def historical_endpoint(symbol):
    try:
        stock = instrument_manager.find_stock(symbol.upper().strip())
        if not stock:
            return jsonify({"success": False, "message": "NSE equity or supported index symbol not found in Angel One instrument master."}), 404
        result = angel_service.get_historical_data(symbol=stock["symbol"], token=stock["token"], days=200, interval="ONE_DAY", exchange=stock.get("exchange", "NSE"))
        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "data": []}), 500


@app.route("/api/instruments")
@login_required
def instruments_endpoint():
    try:
        result = instrument_manager.load_cache()
        if not result.get("success"):
            return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities()
        return jsonify({"success": True, "count": len(stocks), "stocks": stocks})
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "stocks": []}), 500


@app.route("/api/instruments/refresh")
@login_required
def refresh_instruments_endpoint():
    try:
        result = instrument_manager.refresh()
        if not result.get("success"):
            return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities()
        return jsonify({"success": True, "count": len(stocks), "message": "Angel One instrument master refreshed.", "stocks": stocks})
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "stocks": []}), 500


@app.route("/api/instrument/<symbol>")
@login_required
def instrument_endpoint(symbol):
    try:
        stock = instrument_manager.find_stock(symbol)
        if not stock:
            return jsonify({"success": False, "message": "Stock not found."}), 404
        return jsonify({"success": True, "stock": stock})
    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


@app.route("/api/ai-assistant", methods=["POST"])
@login_required
def ai_assistant():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return jsonify({"success": False, "message": "AI Assistant is not configured yet. Add OPENAI_API_KEY to the Render environment variables."}), 503
    body = request.get_json(silent=True) or {}
    question = str(body.get("message", "")).strip()
    if not question:
        return jsonify({"success": False, "message": "Please enter a stock or market question."}), 400
    if len(question) > 4000:
        question = question[:4000]
    snapshot = _snapshot_response()
    context = {"indices": snapshot.get("indices", []), "top_stocks": snapshot.get("stocks", [])[:12], "updated_at": snapshot.get("updated_at")}
    system_prompt = """You are Azad AI Plus, a concise Indian stock-market research assistant. Answer questions about NSE/BSE stocks, indices, technical analysis, market structure, corporate developments and current market news. For anything time-sensitive, especially current news, today's market, recent events, prices or announcements, use web search and clearly distinguish confirmed facts from interpretation. Use the supplied live X10/Angel One snapshot when relevant. Never invent prices, news, targets or company facts. If the user asks whether to buy, provide a decision-support view with bull case, bear case, key levels and risk; do not present certainty or guaranteed returns. Prefer Indian market terminology and INR. Keep answers practical and easy to read. Mention when information is delayed or requires confirmation from the live broker feed."""
    user_prompt = f"User question:\n{question}\n\nCurrent Azad AI Plus market snapshot:\n{context}\n\nAnswer the user's question directly. If current news is requested, search the web before answering and include the publication/source names and dates in the response."
    payload = {"model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), "input": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "tools": [{"type": "web_search"}], "max_output_tokens": 1400}
    try:
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=45)
        data = response.json()
        if response.status_code >= 400:
            return jsonify({"success": False, "message": data.get("error", {}).get("message", "AI service request failed.")}), 502
        answer = data.get("output_text", "").strip()
        if not answer:
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in ("output_text", "text"):
                        answer += content.get("text", "")
        return jsonify({"success": True, "answer": answer or "I couldn't generate an answer right now. Please try again.", "model": payload["model"]})
    except requests.RequestException as error:
        return jsonify({"success": False, "message": f"AI service connection failed: {error}"}), 502


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Azad AI Plus", "ai_configured": bool(os.getenv("OPENAI_API_KEY"))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
