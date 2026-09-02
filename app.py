import os
import threading
import time
import requests
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

from flask import Flask, jsonify, render_template, request, redirect, url_for, session

from angel_instruments import AngelInstrumentManager
from angel_service import AngelOneService
from stock_service import StockService
from angel_scanner import AngelScanner
from market_indices import INDEX_DEFINITIONS

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
    guard_js = '''<script>(function(){
const originalLoadScan=window.loadScan,originalLoadIndices=window.loadIndices;
let scanBusy=false,indexBusy=false;
window.loadScan=async function(){if(scanBusy||document.hidden)return;scanBusy=true;try{return await originalLoadScan()}finally{scanBusy=false}};
window.loadIndices=async function(){if(indexBusy||document.hidden)return;indexBusy=true;try{return await originalLoadIndices()}finally{indexBusy=false}};
if(window.timer)clearInterval(window.timer);
window.timer=setInterval(function(){if(!document.hidden){window.loadScan();window.loadIndices()}},60000);
document.addEventListener('visibilitychange',function(){if(!document.hidden){window.loadScan();window.loadIndices()}});
})();</script>'''
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
  '<div class="az-metric"><small>CHASE STATUS</small><b class="'+(dontChase?'red':'green')+'">'+(dontChase?'DON’T CHASE':'ACTIONABLE ZONE')+'</b></div>
  '</div></div>'+
  '<div class="az-info-card"><h3>📊 Technical DNA</h3><div class="az-dna-tech">'+technical.map(function(x){return '<div class="az-metric"><small>'+esc(x[0])+'</small><b>'+esc(x[1])+'</b></div>'}).join('')+'</div><div class="az-dna-note">Stock DNA summarizes the current X10 decision-support output. It does not guarantee a future price move.</div></div>';
 const target=document.getElementById('azDna');if(target)target.innerHTML=html;
};
})();</script>'''
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
    step2_js = '''<style>
.az-index-pulse{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px;margin-bottom:2px}.az-index-card{position:relative;padding:15px 16px!important;min-height:174px;overflow:hidden}.az-index-card:before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(72,167,255,.08),transparent 58%);pointer-events:none}.az-index-card.bull:before{background:linear-gradient(135deg,rgba(32,209,139,.11),transparent 58%)}.az-index-card.bear:before{background:linear-gradient(135deg,rgba(255,93,108,.11),transparent 58%)}.az-index-card.vix:before{background:linear-gradient(135deg,rgba(255,122,24,.1),transparent 58%)}.az-index-top{display:flex;align-items:center;justify-content:space-between;gap:8px}.az-index-name{font-size:11px;color:#a9b9ca;font-weight:900;letter-spacing:.3px}.az-index-bias{font-size:8px;font-weight:950;padding:4px 7px;border-radius:999px;border:1px solid #29445d;background:#091827}.az-index-bias.bull{color:#20d18b;border-color:rgba(32,209,139,.35);background:rgba(32,209,139,.08)}.az-index-bias.bear{color:#ff5d6c;border-color:rgba(255,93,108,.35);background:rgba(255,93,108,.08)}.az-index-bias.neutral{color:#ffb06f;border-color:rgba(255,122,24,.3);background:rgba(255,122,24,.07)}.az-index-price{font-size:23px;font-weight:950;letter-spacing:-.5px;margin:11px 0 2px}.az-index-change{font-size:10px;font-weight:900}.az-index-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:11px}.az-index-level{padding:6px 7px;border-radius:7px;background:rgba(4,12,22,.62);border:1px solid #183149}.az-index-level small{display:block;color:#71879b;font-size:7px}.az-index-level b{display:block;margin-top:3px;font-size:9px}.az-index-targets{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.az-index-target{font-size:8px;color:#9db0c3;padding:4px 6px;border-radius:6px;background:#091827;border:1px solid #20384f}.az-index-target b{color:#20d18b}.az-index-open{margin-top:9px;font-size:8px;color:#48a7ff;font-weight:900}.az-index-banner{grid-column:1/-1;padding:10px 12px;border:1px solid #20384f;border-radius:11px;background:linear-gradient(90deg,rgba(72,167,255,.07),rgba(255,122,24,.06));display:flex;justify-content:space-between;align-items:center;gap:10px}.az-index-banner b{font-size:10px}.az-index-banner span{font-size:8px;color:#8397ab}.az-index-detail{margin-top:8px;color:#8397ab;font-size:8px;line-height:1.4}@media(max-width:1200px){.az-index-pulse{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.az-index-pulse{grid-template-columns:1fr}.az-index-banner{display:block}.az-index-banner span{display:block;margin-top:4px}}
</style><script>(function(){
function indexKey(name){return String(name||'').toUpperCase().trim()}
function biasClass(b){const x=String(b||'NEUTRAL').toUpperCase();return x.includes('BULL')?'bull':x.includes('BEAR')?'bear':'neutral'}
function indexMoney(v){return Number.isFinite(Number(v))?'₹'+Number(v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}):'—'}
function indexPct(v){const n=Number(v);return Number.isFinite(n)?(n>=0?'+':'')+n.toFixed(2)+'%':'—'}
window.renderIndices=function(a){marketIndices=a||[];const b=document.getElementById('indicesBox');b.innerHTML='';if(!a.length){b.innerHTML='<div class="card empty">Market data is warming up in the background.</div>';return}const wrap=document.createElement('div');wrap.className='az-index-pulse';const banner=document.createElement('div');banner.className='az-index-banner';banner.innerHTML='<b>MARKET PULSE · ACTIONABLE INDEX MAP</b><span>Price → support / resistance → target zones · click any index for detailed analysis</span>';wrap.appendChild(banner);a.slice(0,4).forEach(i=>{const bias=biasClass(i.bias),tz=i.target_zones||{},dz=i.downside_zones||{};const d=document.createElement('div');d.className='card az-index-card '+bias+(indexKey(i.name)==='INDIA VIX'?' vix':'');d.onclick=()=>window.openInstrument({...i,isIndex:true,symbol:i.name,name:i.name});d.innerHTML='<div class="az-index-top"><div class="az-index-name">'+esc(i.name)+'</div><span class="az-index-bias '+bias+'">'+esc(i.bias||'NEUTRAL')+'</span></div><div class="az-index-price">'+indexMoney(i.price)+'</div><div class="az-index-change '+(Number(i.change)>=0?'green':'red')+'">'+(Number(i.change)>=0?'+':'')+num(i.change)+' · '+indexPct(i.change_percent)+'</div><div class="az-index-levels"><div class="az-index-level"><small>SUPPORT</small><b>'+indexMoney(i.support)+'</b></div><div class="az-index-level"><small>RESISTANCE</small><b>'+indexMoney(i.resistance)+'</b></div><div class="az-index-level"><small>ENTRY ZONE</small><b>'+indexMoney((i.entry_zone||{}).low)+' – '+indexMoney((i.entry_zone||{}).high)+'</b></div></div><div class="az-index-targets"><span class="az-index-target">T1 <b>'+indexMoney(tz.target_1)+'</b></span><span class="az-index-target">T2 <b>'+indexMoney(tz.target_2)+'</b></span><span class="az-index-target">T3 <b>'+indexMoney(tz.target_3)+'</b></span></div><div class="az-index-detail">Downside zones: '+indexMoney(dz.support_1)+' / '+indexMoney(dz.support_2)+'</div><div class="az-index-open">▣ OPEN INDEX ANALYSIS · HEIKIN-ASHI · LEVELS</div>';wrap.appendChild(d)});b.appendChild(wrap)};
const originalOpenInstrument=window.openInstrument;
window.openInstrument=async function(raw){const s=raw||{};if(!s.isIndex)return originalOpenInstrument(s);currentInstrument=s;document.getElementById('azModal').classList.add('open');document.getElementById('azModal').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';document.getElementById('azTitle').textContent=s.name||s.symbol||'Market Index';document.getElementById('azSubtitle').textContent=(s.name||s.symbol||'')+' · Angel One · INDEX';document.getElementById('azChartWrap').innerHTML='<div class="az-loading">Loading index candles…</div>';document.getElementById('azChartStatus').textContent='Loading index data…';renderDNA(s);renderTrade(s);switchTab('chart');try{const name=encodeURIComponent(s.name||s.symbol);const r=await fetch('/api/index-historical/'+name,{cache:'no-store'});const j=await r.json();if(!r.ok||!j.success)throw new Error(j.message||'Index historical data unavailable.');const rawCandles=(j.data||[]).map(parseCandle).filter(x=>[x.o,x.h,x.l,x.c].every(Number.isFinite));currentCandles=toHeikinAshi(rawCandles);if(!currentCandles.length)throw new Error('No index candles returned.');chartState={start:Math.max(0,currentCandles.length-45),end:currentCandles.length,baseStart:Math.max(0,currentCandles.length-45),baseEnd:currentCandles.length};document.getElementById('azChartStatus').textContent='Angel One · Heikin-Ashi · '+currentCandles.length+' daily candles · '+(s.name||s.symbol);document.getElementById('azChartWrap').innerHTML='<div class="az-chart-overlay" id="azOverlay"></div><canvas class="az-canvas" id="azCanvas"></canvas>';document.getElementById('azCanvas').addEventListener('wheel',chartWheel,{passive:false});document.getElementById('azCanvas').addEventListener('mousedown',chartDown);document.getElementById('azCanvas').addEventListener('dblclick',()=>resetChart());drawAdvancedChart();window.addEventListener('resize',drawAdvancedChart,{passive:true});}catch(e){document.getElementById('azChartWrap').innerHTML='<div class="az-error">Index chart error<br>'+esc(e.message||e)+'</div>';document.getElementById('azChartStatus').textContent='Index chart unavailable'}};
function toHeikinAshi(candles){let prevO=0,prevC=0;return candles.map(function(d,i){const c=(d.o+d.h+d.l+d.c)/4;const o=i===0?(d.o+d.c)/2:(prevO+prevC)/2;const h=Math.max(d.h,o,c);const l=Math.min(d.l,o,c);prevO=o;prevC=c;return{t:d.t,o,h,l,c,v:d.v}})}
const originalIndexDNA=window.renderDNA;window.renderDNA=function(s){if(!s||!s.isIndex)return originalIndexDNA(s);const tz=s.target_zones||{},dz=s.downside_zones||{},ez=s.entry_zone||{};document.getElementById('azDna').innerHTML='<div class="az-info-card"><h3>🧭 Index Structure</h3><div class="az-metric-grid"><div class="az-metric"><small>BIAS</small><b class="'+cls(s.bias)+'">'+esc(s.bias||'NEUTRAL')+'</b></div><div class="az-metric"><small>CURRENT</small><b>'+indexMoney(s.price)+'</b></div><div class="az-metric"><small>CHANGE</small><b class="'+(Number(s.change)>=0?'green':'red')+'">'+(Number(s.change)>=0?'+':'')+num(s.change)+' ('+indexPct(s.change_percent)+')</b></div><div class="az-metric"><small>SUPPORT</small><b>'+indexMoney(s.support)+'</b></div><div class="az-metric"><small>RESISTANCE</small><b>'+indexMoney(s.resistance)+'</b></div><div class="az-metric"><small>ENTRY ZONE</small><b>'+indexMoney(ez.low)+' – '+indexMoney(ez.high)+'</b></div></div></div><div class="az-info-card"><h3>🎯 Target Map</h3><div class="az-trade-grid"><div class="az-trade-item"><small>TARGET 1</small><b class="green">'+indexMoney(tz.target_1)+'</b></div><div class="az-trade-item"><small>TARGET 2</small><b class="green">'+indexMoney(tz.target_2)+'</b></div><div class="az-trade-item"><small>TARGET 3</small><b class="green">'+indexMoney(tz.target_3)+'</b></div><div class="az-trade-item"><small>SUPPORT 1</small><b>'+indexMoney(dz.support_1)+'</b></div><div class="az-trade-item"><small>SUPPORT 2</small><b>'+indexMoney(dz.support_2)+'</b></div><div class="az-trade-item"><small>RANGE</small><b>'+indexMoney(s.support)+' → '+indexMoney(s.resistance)+'</b></div></div></div><div class="az-info-card"><h3>📌 Market Read</h3><p class="az-summary">'+esc(s.bias||'NEUTRAL')+' bias is derived from current price structure, support/resistance position and daily change. These are decision-support zones, not guaranteed targets.</p></div>'};
const originalIndexTrade=window.renderTrade;window.renderTrade=function(s){if(!s||!s.isIndex)return originalIndexTrade(s);const p=Number(s.price),sup=Number(s.support),res=Number(s.resistance),bias=String(s.bias||'NEUTRAL');const upside=Number.isFinite(p)&&Number.isFinite(res)&&p?((res-p)/p*100):NaN;const downside=Number.isFinite(p)&&Number.isFinite(sup)&&p?((p-sup)/p*100):NaN;document.getElementById('azTrade').innerHTML='<div class="az-info-card"><h3>🎯 Index Decision Plan</h3><div class="az-trade-grid"><div class="az-trade-item"><small>BIAS</small><b class="'+cls(bias)+'">'+esc(bias)+'</b></div><div class="az-trade-item"><small>CURRENT</small><b>'+indexMoney(p)+'</b></div><div class="az-trade-item"><small>SUPPORT</small><b>'+indexMoney(sup)+'</b></div><div class="az-trade-item"><small>RESISTANCE</small><b>'+indexMoney(res)+'</b></div><div class="az-trade-item"><small>UPSIDE TO R</small><b>'+ (Number.isFinite(upside)?upside.toFixed(2)+'%':'—') +'</b></div><div class="az-trade-item"><small>DOWNSIDE TO S</small><b>'+ (Number.isFinite(downside)?downside.toFixed(2)+'%':'—') +'</b></div></div><p class="az-summary">Use the support/resistance and target zones as a map. Wait for confirmation near the planned zone and avoid chasing extended moves.</p></div>'};
})();</script>'''
    tv_chart_js = '''<style>
.az-tv-chart{height:100%;width:100%;min-height:360px;background:#07111f;border-radius:12px;overflow:hidden}.az-tv-chart .tradingview-widget-container,.az-tv-chart .tradingview-widget-container__widget{height:100%!important;width:100%!important}.az-tv-chart .tradingview-widget-copyright{display:none}
</style><script>(function(){
const legacyOpenInstrument=window.openInstrument;
const indexSymbols={'NIFTY 50':'NSE:NIFTY','BANK NIFTY':'NSE:BANKNIFTY','SENSEX':'BSE:SENSEX','INDIA VIX':'NSE:INDIAVIX'};
function tvSymbol(s){if(s&&s.isIndex)return indexSymbols[String(s.name||s.symbol||'').toUpperCase()]||('NSE:'+String(s.symbol||s.name||'').toUpperCase().replace(/\s+/g,''));const raw=String((s&&s.symbol)||'').toUpperCase().replace(/\.NS$/,'');return raw?('NSE:'+raw):'NSE:NIFTY'}
function tvChart(symbol){const wrap=document.getElementById('azChartWrap');if(!wrap)return;wrap.innerHTML='';const outer=document.createElement('div');outer.className='az-tv-chart tradingview-widget-container';const widget=document.createElement('div');widget.className='tradingview-widget-container__widget';outer.appendChild(widget);wrap.appendChild(outer);const script=document.createElement('script');script.type='text/javascript';script.src='https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';script.async=true;script.text=JSON.stringify({autosize:true,symbol:symbol,interval:'D',timezone:'exchange',theme:'dark',style:'1',withdateranges:true,hide_side_toolbar:false,allow_symbol_change:true,save_image:false,locale:'en',calendar:false,support_host:'https://www.tradingview.com'});outer.appendChild(script);document.getElementById('azChartStatus').textContent='TradingView · '+symbol+' · live interactive chart'}
window.openInstrument=async function(s){
 const item=s||{};
 try{await legacyOpenInstrument(item)}catch(error){console.warn('Legacy chart skipped:',error)}
 try{currentInstrument=item;const modal=document.getElementById('azModal');if(modal&&!modal.classList.contains('open')){modal.classList.add('open');modal.setAttribute('aria-hidden','false');document.body.style.overflow='hidden'}if(document.getElementById('azTitle'))document.getElementById('azTitle').textContent=item.name||item.symbol||'Instrument';if(document.getElementById('azSubtitle'))document.getElementById('azSubtitle').textContent=(item.name||item.symbol||'')+' · TradingView';if(typeof renderDNA==='function')renderDNA(item);if(typeof renderTrade==='function')renderTrade(item);if(typeof switchTab==='function')switchTab('chart');tvChart(tvSymbol(item))}catch(error){console.error('TradingView chart error:',error);const wrap=document.getElementById('azChartWrap');if(wrap)wrap.innerHTML='<div class="az-error">TradingView chart could not be loaded.<br>'+esc(error.message||error)+'</div>'}}
})();</script>'''
    html = html.replace("</body>", guard_js + step3_js + broker_ui_js + step2_js + tv_chart_js + "</body>")
    return html

@app.route("/api/index-historical/<path:name>")
@login_required
def index_historical(name):
    try:
        key = unquote(name).upper().strip()
        definition = INDEX_DEFINITIONS.get(key)
        if not definition:
            for index_name in INDEX_DEFINITIONS:
                if index_name.upper() == key:
                    definition = INDEX_DEFINITIONS[index_name]
                    key = index_name
                    break
        if not definition:
            return jsonify({"success": False, "message": f"Index not found: {name}", "data": []}), 404
        result = angel_service.get_historical_data(
            definition["tradingsymbol"],
            definition["token"],
            days=400,
            interval="ONE_DAY",
            exchange=definition.get("exchange", "NSE"),
        )
        return jsonify(result), (200 if result.get("success") else 502)
    except Exception as error:
        print("INDEX HISTORICAL API ERROR:", error)
        return jsonify({"success": False, "message": str(error), "data": []}), 500

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
