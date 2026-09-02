import os
import threading
import time
import requests
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

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
_index_lock = threading.Lock()
_index_state = {"indices": [], "updated_at": 0.0, "refreshing": False, "last_error": None}

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
    fields = [
        "symbol", "name", "token", "price", "technical_score", "x10_score", "base_x10_score",
        "success_probability", "signal", "opportunity_rank", "ranking_reason",
        "early_momentum_score", "momentum_stage", "early_momentum_reasons", "validation",
        "why_buy", "why_not_buy", "entry", "entry_low", "entry_high", "stop_loss", "target",
        "target_1", "target_2", "risk", "reward", "risk_reward", "risk_reward_display",
        "risk_reward_value", "trailing_stop", "chase_price", "dont_chase", "setup_quality",
        "trend", "momentum", "rsi", "ema20", "ema50", "ema200", "macd", "macd_signal",
        "macd_histogram", "adx", "plus_di", "minus_di", "support", "resistance", "volume_ratio",
        "atr", "52_week_high", "52_week_low", "scan_time"
    ]
    return {field: stock.get(field, 0) for field in fields}

def _run_index_refresh():
    with _index_lock:
        if _index_state["refreshing"]:
            return False
        _index_state["refreshing"] = True
    try:
        scanner = AngelScanner(batch_size=5, delay=0.03, max_workers=5)
        login = scanner.service.login()
        if not login.get("success"):
            raise RuntimeError(login.get("message", "Angel One login failed."))
        indices = scanner._get_index_snapshots()
        if not indices:
            raise RuntimeError("Angel One returned no index snapshots.")
        with _index_lock:
            _index_state["indices"] = indices
            _index_state["updated_at"] = time.time()
            _index_state["last_error"] = None
        with _scan_lock:
            if _scan_state["result"] is not None:
                _scan_state["result"] = dict(_scan_state["result"])
                _scan_state["result"]["indices"] = indices
        return True
    except Exception as error:
        print("BACKGROUND INDEX REFRESH ERROR:", error)
        with _index_lock:
            _index_state["last_error"] = str(error)
        return False
    finally:
        with _index_lock:
            _index_state["refreshing"] = False

def _ensure_index_refresh(force=False):
    with _index_lock:
        age = time.time() - _index_state["updated_at"] if _index_state["updated_at"] else None
        refreshing = _index_state["refreshing"]
        stale = age is None or age >= SCAN_REFRESH_SECONDS
    if (force or stale) and not refreshing:
        threading.Thread(target=_run_index_refresh, name="x10-index-refresh", daemon=True).start()

def _publish_scan_payload(result, started):
    stocks = [clean_stock(stock) for stock in result.get("stocks", []) if isinstance(stock, dict)]
    with _index_lock:
        indices = list(_index_state["indices"])
    payload = {
        "success": True,
        "message": result.get("message", "Market scan completed."),
        "count": len(stocks),
        "scanned": result.get("scanned", len(stocks)),
        "successful": result.get("successful", len(stocks)),
        "manual_count": result.get("manual_count", 0),
        "time_seconds": result.get("time_seconds", round(time.time() - started, 2)),
        "stocks": stocks,
        "top_opportunities": stocks[:5],
        "indices": indices,
        "updated_at": time.time(),
        "data_source": result.get("data_source", "MIXED"),
    }
    with _scan_lock:
        _scan_state["result"] = payload
        _scan_state["updated_at"] = payload["updated_at"]
        _scan_state["last_error"] = None
    return payload

def _run_market_scan():
    with _scan_lock:
        if _scan_state["refreshing"]:
            return False
        _scan_state["refreshing"] = True
    started = time.time()
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        scanner = AngelScanner(batch_size=3, delay=0.03, max_workers=3)
        fallback_future = executor.submit(scanner._fallback_yfinance_scan, 6)
        broker_future = executor.submit(lambda: scanner.scan_market(limit=12, include_indices=False))
        fallback_published = False
        try:
            fallback_results = fallback_future.result(timeout=20)
            if fallback_results:
                _publish_scan_payload({
                    "success": True,
                    "message": "Live stock scan is running; showing X10 market-data candidates while broker data refreshes.",
                    "stocks": fallback_results,
                    "scanned": len(fallback_results),
                    "successful": len(fallback_results),
                    "data_source": "YAHOO FALLBACK",
                }, started)
                fallback_published = True
        except Exception as error:
            print("BACKGROUND FALLBACK SCAN ERROR:", error)
        try:
            result = broker_future.result(timeout=45)
            if result and result.get("success") and result.get("stocks"):
                _publish_scan_payload(result, started)
            elif not fallback_published:
                raise RuntimeError((result or {}).get("message", "Broker scanner returned no stocks."))
        except Exception as error:
            print("BACKGROUND X10 SCANNER ERROR:", error)
            with _scan_lock:
                _scan_state["last_error"] = str(error)
            if not fallback_published:
                try:
                    late_fallback = fallback_future.result(timeout=20)
                    if late_fallback:
                        _publish_scan_payload({
                            "success": True,
                            "message": "Broker scan unavailable; showing X10 market-data candidates.",
                            "stocks": late_fallback,
                            "scanned": len(late_fallback),
                            "successful": len(late_fallback),
                            "data_source": "YAHOO FALLBACK",
                        }, started)
                except Exception as fallback_error:
                    print("BACKGROUND LATE FALLBACK ERROR:", fallback_error)
        return True
    except Exception as error:
        print("BACKGROUND X10 SCANNER ERROR:", error)
        with _scan_lock:
            _scan_state["last_error"] = str(error)
        return False
    finally:
        executor.shutdown(wait=False, cancel_futures=False)
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
    with _index_lock:
        index_state = dict(_index_state)
    if result:
        payload = dict(result)
        if index_state["indices"]:
            payload["indices"] = list(index_state["indices"])
        payload["refreshing"] = refreshing or index_state["refreshing"]
        payload["cache_age_seconds"] = round(max(0, time.time() - updated_at), 1)
        payload["stale"] = payload["cache_age_seconds"] >= SCAN_REFRESH_SECONDS
        payload["index_updated_at"] = index_state["updated_at"]
        payload["index_last_error"] = index_state["last_error"]
        return payload
    return {"success": True, "message": "Market data is initializing in the background.", "count": 0, "scanned": 0, "successful": 0, "time_seconds": 0, "stocks": [], "top_opportunities": [], "indices": list(index_state["indices"]), "refreshing": refreshing or index_state["refreshing"], "cache_age_seconds": None, "stale": True, "last_error": last_error, "index_last_error": index_state["last_error"]}

def _background_refresh_loop():
    time.sleep(2)
    while True:
        try:
            _ensure_index_refresh()
            _ensure_scan_refresh()
        except Exception as error:
            print("BACKGROUND REFRESH LOOP ERROR:", error)
        time.sleep(15)
threading.Thread(target=_background_refresh_loop, name="x10-refresh-loop", daemon=True).start()

@app.route("/api/historical/<path:symbol>")
@login_required
def historical(symbol):
    try:
        instrument = instrument_manager.find_stock(symbol)
        if not instrument:
            return jsonify({"success": False, "message": f"Angel One instrument not found: {symbol}", "data": []}), 404
        result = angel_service.get_historical_data(instrument["symbol"], instrument["token"], days=400, interval="ONE_DAY", exchange=instrument.get("exchange", "NSE"))
        return jsonify(result), (200 if result.get("success") else 502)
    except Exception as error:
        print("HISTORICAL API ERROR:", error)
        return jsonify({"success": False, "message": str(error), "data": []}), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        if request.form.get("user_id", "") == APP_USER_ID and request.form.get("password", "") == APP_PASSWORD:
            session.clear(); session["authenticated"] = True; session["user_id"] = APP_USER_ID
            return redirect(url_for("home"))
        error = "Invalid User ID or Password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def home():
    html = render_template("index.html")
    html = html.replace("timer=setInterval(()=>{loadScan();loadIndices()},30000);", "timer=setInterval(()=>{loadScan();loadIndices()},60000);")
    # Phase 4 Step 2: guard dashboard polling against duplicate in-flight requests
    # and stop polling while the browser tab is hidden. The backend remains the
    # source of truth and continues its own cached background refresh.
    guard_js = '''<script>(function(){\nconst originalLoadScan=window.loadScan,originalLoadIndices=window.loadIndices;\nlet scanBusy=false,indexBusy=false;\nwindow.loadScan=async function(){if(scanBusy||document.hidden)return;scanBusy=true;try{return await originalLoadScan()}finally{scanBusy=false}};\nwindow.loadIndices=async function(){if(indexBusy||document.hidden)return;indexBusy=true;try{return await originalLoadIndices()}finally{indexBusy=false}};\nif(window.timer)clearInterval(window.timer);\nwindow.timer=setInterval(function(){if(!document.hidden){window.loadScan();window.loadIndices()}},60000);\ndocument.addEventListener('visibilitychange',function(){if(!document.hidden){window.loadScan();window.loadIndices()}});\n})();</script>'''

    # Phase 4 Step 3: make X10 decision intelligence visible inside Stock DNA.
    # This only changes presentation. X10 scoring, ranking and trade-plan logic
    # continue to come from the backend engine without modification.
    step3_js = '''<style>
.az-dna-hero{padding:13px;border-radius:12px;background:linear-gradient(135deg,rgba(255,122,24,.13),rgba(72,167,255,.08));border:1px solid #29445d}.az-dna-hero-row{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:10px}.az-dna-stat{background:#081522;border:1px solid #183149;border-radius:8px;padding:9px}.az-dna-stat small{display:block;color:#71879b;font-size:8px}.az-dna-stat b{display:block;margin-top:4px;font-size:12px}.az-reason-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.az-reason{border-radius:10px;padding:11px;border:1px solid #20384f;background:#081522}.az-reason.good{border-color:rgba(32,209,139,.35);background:rgba(32,209,139,.06)}.az-reason.bad{border-color:rgba(255,93,108,.35);background:rgba(255,93,108,.06)}.az-reason h3{font-size:11px!important;margin:0 0 7px!important}.az-reason p{margin:0;color:#a9b9ca;font-size:10px;line-height:1.55}.az-validation{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.az-validation span{padding:5px 7px;border-radius:999px;background:#091827;border:1px solid #29445d;color:#aebfd0;font-size:8px;font-weight:900}.az-validation .warn{color:#ff9aa3;border-color:rgba(255,93,108,.4)}.az-dna-tech{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.az-dna-tech .az-metric{border:1px solid #183149}.az-dna-note{margin-top:8px;color:#71879b;font-size:9px;line-height:1.45}@media(max-width:700px){.az-dna-hero-row,.az-dna-tech{grid-template-columns:repeat(2,1fr)}.az-reason-grid{grid-template-columns:1fr}}
</style><script>(function(){
const originalRenderDNA=window.renderDNA;
function textValue(v,fallback){if(Array.isArray(v))return v.filter(Boolean).join(' · ');if(v&&typeof v==='object')return Object.entries(v).map(function(x){return x[0]+': '+x[1]}).join(' · ');const t=String(v??'').trim();return(!t||t==='0')?(fallback||'—'):t}
function ratioValue(s){if(s.risk_reward_display&&String(s.risk_reward_display)!=='0')return String(s.risk_reward_display);const n=Number(s.risk_reward_value||s.risk_reward);return Number.isFinite(n)&&n>0?'1 : '+n.toFixed(1):'—'}
function scoreValue(v){const n=Number(v);return Number.isFinite(n)&&n>=0?n.toFixed(0):'—'}
window.renderDNA=function(s){
 if(s&&s.isIndex){return originalRenderDNA(s)}
 s=s||{};
 const whyBuy=textValue(s.why_buy,'No strong early-momentum confirmation yet.');
 const whyNot=textValue(s.why_not_buy,'No major X10 validation warning.');
 const validations=Array.isArray(s.validation)?s.validation:(String(s.validation||'').split(/[;,|]/).map(function(x){return x.trim()}).filter(Boolean));
 const reasons=Array.isArray(s.early_momentum_reasons)?s.early_momentum_reasons:[];
 const stage=textValue(s.momentum_stage,'WATCH');
 const setup=textValue(s.setup_quality,'—');
 const signal=textValue(s.signal,'WATCH');
 const dontChase=!!s.dont_chase||signal.toUpperCase().includes("DON'T CHASE")||signal.toUpperCase().includes('WAIT');
 const technical=[['TREND',textValue(s.trend)],['MOMENTUM',textValue(s.momentum)],['RSI',num(s.rsi)],['MACD',num(s.macd)],['ADX',num(s.adx)],['VOLUME RATIO',num(s.volume_ratio)],['SUPPORT',money(s.support)],['RESISTANCE',money(s.resistance)],['ATR',num(s.atr)]];
 const validationHtml=validations.length?validations.map(function(v){const warn=/WEAK|LOW|CHASE|AVOID|RISK/i.test(String(v));return '<span class="'+(warn?'warn':'')+'">'+esc(v)+'</span>'}).join(''):'<span>No extra validation flags</span>';
 const reasonHtml=reasons.length?'<div class="az-dna-note">Momentum evidence: '+reasons.map(esc).join(' · ')+'</div>':'';
 const html='<div class="az-dna-hero"><h3>🔬 X10 Stock DNA</h3><div class="az-dna-hero-row">'+
  '<div class="az-dna-stat"><small>X10 SCORE</small><b class="orange">'+scoreValue(s.x10_score)+'/100</b></div>'+
  '<div class="az-dna-stat"><small>EARLY MOMENTUM</small><b>'+scoreValue(s.early_momentum_score)+'/100</b></div>'+
  '<div class="az-dna-stat"><small>LIFECYCLE STAGE</small><b>'+esc(stage)+'</b></div>'+
  '<div class="az-dna-stat"><small>SETUP QUALITY</small><b class="'+(setup==='GOOD'?'green':setup==='WEAK'?'red':'orange')+'">'+esc(setup)+'</b></div>'+
  '</div><div class="az-validation">'+validationHtml+'</div>'+reasonHtml+'</div>'+
  '<div class="az-reason-grid"><div class="az-reason good"><h3>✅ Why Buy</h3><p>'+esc(whyBuy)+'</p></div><div class="az-reason bad"><h3>⚠ Why Not Buy</h3><p>'+esc(whyNot)+'</p></div></div>'+
  '<div class="az-info-card"><h3>🎯 Decision Snapshot</h3><div class="az-dna-tech">'+
  '<div class="az-metric"><small>SIGNAL</small><b class="'+cls(signal)+'">'+esc(signal)+'</b></div>'+
  '<div class="az-metric"><small>R:R</small><b>'+esc(ratioValue(s))+'</b></div>'+
  '<div class="az-metric"><small>CHASE STATUS</small><b class="'+(dontChase?'red':'green')+'">'+(dontChase?'DON’T CHASE':'ACTIONABLE ZONE')+'</b></div>'+
  '</div></div>'+
  '<div class="az-info-card"><h3>📊 Technical DNA</h3><div class="az-dna-tech">'+technical.map(function(x){return '<div class="az-metric"><small>'+esc(x[0])+'</small><b>'+esc(x[1])+'</b></div>'}).join('')+'</div><div class="az-dna-note">Stock DNA summarizes the current X10 decision-support output. It does not guarantee a future price move.</div></div>';
 const target=document.getElementById('azDna');if(target)target.innerHTML=html;
};
})();</script>'''

    # Phase 5 Step 1: broker-style visual shell. Presentation-only; no market
    # data, X10 scoring, ranking, trade-plan or refresh behavior is changed.
    broker_ui_js = '''<style>
:root{--az-glow:rgba(72,167,255,.16);--az-panel-2:#0a1827}
body{background:radial-gradient(circle at 72% -15%,rgba(72,167,255,.16),transparent 34%),radial-gradient(circle at 12% 0%,rgba(255,122,24,.08),transparent 28%),#06101d}
.top{height:72px;padding:0 26px;background:rgba(5,14,25,.92);box-shadow:0 8px 30px rgba(0,0,0,.16)}
.logo{letter-spacing:-.35px}.logo:before{content:'◈';display:inline-block;margin-right:8px;color:var(--blue);font-size:17px}
.search input{height:40px;background:#071522;border-color:#29445d;box-shadow:inset 0 0 0 1px rgba(255,255,255,.015)}
.topright .live{padding:6px 9px;border:1px solid rgba(32,209,139,.25);border-radius:999px;background:rgba(32,209,139,.07)}
.layout{grid-template-columns:228px 1fr}aside{background:rgba(4,12,22,.72);box-shadow:12px 0 40px rgba(0,0,0,.08)}
nav a{border:1px solid transparent;transition:.18s ease}nav a:hover{border-color:#29445d;transform:translateX(2px)}
.main{max-width:1760px;padding:27px 30px 70px}.hero{padding:3px 2px 4px}.hero h1{letter-spacing:-.7px}.hero p{max-width:720px}
.btn{box-shadow:0 8px 24px rgba(255,122,24,.16);transition:.18s ease}.btn:hover{transform:translateY(-1px);filter:brightness(1.04)}
.section{margin-top:27px}.head h2{letter-spacing:-.25px}.head .hint{padding:6px 9px;border:1px solid #20384f;border-radius:999px;background:#091827}
.card{background:linear-gradient(145deg,rgba(16,36,58,.98),rgba(7,19,32,.98));box-shadow:0 12px 34px rgba(0,0,0,.17);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}.card:hover{border-color:#31516d;box-shadow:0 18px 42px rgba(0,0,0,.24)}
.index,.op{padding:18px}.index:after{content:'›';float:right;color:#58718a;font-size:18px;margin-top:-2px}.price{font-size:25px;letter-spacing:-.4px}.op h3{font-size:15px}.rank{padding:4px 7px;border-radius:999px;background:rgba(255,122,24,.09);border:1px solid rgba(255,122,24,.2)}
.trade div{background:rgba(3,12,22,.58);border-color:#1d3850}.trade b{font-size:11px}.pill{border:1px solid rgba(32,209,139,.18)}
.slab{background:linear-gradient(145deg,#0e2033,#081522)}.slabhead{background:linear-gradient(90deg,rgba(72,167,255,.08),rgba(255,122,24,.06))}.row:hover{background:rgba(72,167,255,.05)}
.tablebox,.chart,.assistant{box-shadow:0 15px 40px rgba(0,0,0,.16)}
.az-modal{background:rgba(1,7,14,.88)}.az-dialog{box-shadow:0 40px 120px rgba(0,0,0,.72)}
@media(max-width:700px){.top{height:64px;padding:0 12px}.main{padding:17px 12px 55px}.hero h1{font-size:24px}.head .hint{display:none}}
</style><script>(function(){
const mark=document.createElement('div');mark.id='azMarketShellStatus';mark.innerHTML='<span class="az-shell-dot">●</span> X10 DECISION CENTER';mark.style.cssText='position:fixed;bottom:14px;right:16px;z-index:20;padding:7px 10px;border:1px solid #20384f;border-radius:999px;background:rgba(7,17,31,.88);backdrop-filter:blur(10px);color:#8397ab;font-size:9px;font-weight:900;letter-spacing:.5px;box-shadow:0 8px 25px rgba(0,0,0,.25)';document.body.appendChild(mark);
})();</script>'''
    html = html.replace("</body>", guard_js + step3_js + broker_ui_js + "</body>")
    return html

@app.route("/api/analyze/<symbol>")
@login_required
def analyze_stock(symbol):
    try:
        result = stock_service.get_stock_analysis(symbol.upper().strip())
        if not result: return jsonify({"success": False, "message": "No analysis result returned."}), 500
        return jsonify(result)
    except Exception as error: return jsonify({"success": False, "message": str(error)}), 500

@app.route("/api/scan")
@login_required
def scan():
    _ensure_index_refresh(); _ensure_scan_refresh(); return jsonify(_snapshot_response())

@app.route("/api/scan/refresh")
@login_required
def scan_refresh():
    _ensure_index_refresh(force=True); _ensure_scan_refresh(force=True)
    return jsonify({"success": True, "message": "X10 scan and index refresh started in background.", "refreshing": True})

@app.route("/api/indices")
@login_required
def indices_endpoint():
    _ensure_index_refresh();
    with _index_lock:
        return jsonify({"success": True, "indices": list(_index_state["indices"]), "cached": bool(_index_state["indices"]), "refreshing": _index_state["refreshing"], "updated_at": _index_state["updated_at"], "last_error": _index_state["last_error"]})

@app.route("/api/instruments")
@login_required
def instruments_endpoint():
    try:
        result = instrument_manager.load_cache()
        if not result.get("success"): return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities(); return jsonify({"success": True, "count": len(stocks), "stocks": stocks})
    except Exception as error: return jsonify({"success": False, "message": str(error), "stocks": []}), 500

@app.route("/api/instruments/refresh")
@login_required
def refresh_instruments_endpoint():
    try:
        result = instrument_manager.refresh()
        if not result.get("success"): return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities(); return jsonify({"success": True, "count": len(stocks), "message": "Angel One instrument master refreshed.", "stocks": stocks})
    except Exception as error: return jsonify({"success": False, "message": str(error), "stocks": []}), 500

@app.route("/api/instrument/<symbol>")
@login_required
def instrument_endpoint(symbol):
    try:
        stock = instrument_manager.find_stock(symbol)
        if not stock: return jsonify({"success": False, "message": "Stock not found."}), 404
        return jsonify({"success": True, "stock": stock})
    except Exception as error: return jsonify({"success": False, "message": str(error)}), 404
