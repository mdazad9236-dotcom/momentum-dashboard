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
angel_service = AngelOneService(); stock_service = StockService(); instrument_manager = AngelInstrumentManager()
APP_USER_ID = "Admin"; APP_PASSWORD = "Admin"; SCAN_REFRESH_SECONDS = max(60, int(os.getenv("X10_SCAN_REFRESH_SECONDS", "180")))
_scan_lock=threading.Lock(); _scan_state={"result":None,"updated_at":0.0,"refreshing":False,"last_error":None}; _index_lock=threading.Lock(); _index_state={"indices":[],"updated_at":0.0,"refreshing":False,"last_error":None}
def is_authenticated(): return session.get("authenticated") is True
def login_required(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        if not is_authenticated(): return (jsonify({"success":False,"authenticated":False,"message":"Authentication required."}),401) if request.path.startswith("/api/") else redirect(url_for("login"))
        return view(*args,**kwargs)
    return wrapped
def clean_stock(stock):
    fields=["symbol","name","token","price","technical_score","x10_score","base_x10_score","success_probability","signal","opportunity_rank","ranking_reason","early_momentum_score","momentum_stage","early_momentum_reasons","validation","why_buy","why_not_buy","entry","entry_low","entry_high","stop_loss","target","target_1","target_2","risk","reward","risk_reward","risk_reward_display","risk_reward_value","trailing_stop","chase_price","dont_chase","setup_quality","trend","momentum","rsi","ema20","ema50","ema200","macd","macd_signal","macd_histogram","adx","plus_di","minus_di","support","resistance","volume_ratio","atr","52_week_high","52_week_low","scan_time"]
    return {field:stock.get(field,0) for field in fields}
def _run_index_refresh():
    with _index_lock:
        if _index_state["refreshing"]: return False
        _index_state["refreshing"]=True
    try:
        scanner=AngelScanner(batch_size=5,delay=0.03,max_workers=5); login=scanner.service.login()
        if not login.get("success"): raise RuntimeError(login.get("message","Angel One login failed."))
        indices=scanner._get_index_snapshots()
        if not indices: raise RuntimeError("Angel One returned no index snapshots.")
        with _index_lock: _index_state.update({"indices":indices,"updated_at":time.time(),"last_error":None})
        with _scan_lock:
            if _scan_state["result"] is not None: _scan_state["result"]=dict(_scan_state["result"]); _scan_state["result"]["indices"]=indices
        return True
    except Exception as error: print("BACKGROUND INDEX REFRESH ERROR:",error); _index_state["last_error"]=str(error); return False
    finally: _index_state["refreshing"]=False
def _ensure_index_refresh(force=False):
    age=time.time()-_index_state["updated_at"] if _index_state["updated_at"] else None; refreshing=_index_state["refreshing"]; stale=age is None or age>=SCAN_REFRESH_SECONDS
    if (force or stale) and not refreshing: threading.Thread(target=_run_index_refresh,name="x10-index-refresh",daemon=True).start()
def _publish_scan_payload(result,started):
    stocks=[clean_stock(stock) for stock in result.get("stocks",[]) if isinstance(stock,dict)]; indices=list(_index_state["indices"])
    payload={"success":True,"message":result.get("message","Market scan completed."),"count":len(stocks),"scanned":result.get("scanned",len(stocks)),"successful":result.get("successful",len(stocks)),"manual_count":result.get("manual_count",0),"time_seconds":result.get("time_seconds",round(time.time()-started,2)),"stocks":stocks,"top_opportunities":stocks[:5],"indices":indices,"updated_at":time.time(),"data_source":result.get("data_source","MIXED")}; _scan_state.update({"result":payload,"updated_at":payload["updated_at"],"last_error":None}); return payload
def _run_market_scan():
    with _scan_lock:
        if _scan_state["refreshing"]: return False
        _scan_state["refreshing"]=True
    started=time.time(); executor=ThreadPoolExecutor(max_workers=2)
    try:
        scanner=AngelScanner(batch_size=3,delay=0.03,max_workers=3); fallback_future=executor.submit(scanner._fallback_yfinance_scan,6); broker_future=executor.submit(lambda:scanner.scan_market(limit=12,include_indices=False)); fallback_published=False
        try:
            fallback_results=fallback_future.result(timeout=20)
            if fallback_results: _publish_scan_payload({"success":True,"message":"Live stock scan is running; showing X10 market-data candidates while broker data refreshes.","stocks":fallback_results,"scanned":len(fallback_results),"successful":len(fallback_results),"data_source":"YAHOO FALLBACK"},started); fallback_published=True
        except Exception as error: print("BACKGROUND FALLBACK SCAN ERROR:",error)
        try:
            result=broker_future.result(timeout=45)
            if result and result.get("success") and result.get("stocks"): _publish_scan_payload(result,started)
            elif not fallback_published: raise RuntimeError((result or {}).get("message","Broker scanner returned no stocks."))
        except Exception as error:
            print("BACKGROUND X10 SCANNER ERROR:",error); _scan_state["last_error"]=str(error)
            if not fallback_published:
                try:
                    late_fallback=fallback_future.result(timeout=20)
                    if late_fallback: _publish_scan_payload({"success":True,"message":"Broker scan unavailable; showing X10 market-data candidates.","stocks":late_fallback,"scanned":len(late_fallback),"successful":len(late_fallback),"data_source":"YAHOO FALLBACK"},started)
                except Exception as fallback_error: print("BACKGROUND LATE FALLBACK ERROR:",fallback_error)
        return True
    except Exception as error: print("BACKGROUND X10 SCANNER ERROR:",error); _scan_state["last_error"]=str(error); return False
    finally: executor.shutdown(wait=False,cancel_futures=False); _scan_state["refreshing"]=False
def _ensure_scan_refresh(force=False):
    age=time.time()-_scan_state["updated_at"] if _scan_state["updated_at"] else None; refreshing=_scan_state["refreshing"]; stale=age is None or age>=SCAN_REFRESH_SECONDS
    if (force or stale) and not refreshing: threading.Thread(target=_run_market_scan,name="x10-market-scan",daemon=True).start()
def _snapshot_response():
    result=_scan_state["result"]; updated_at=_scan_state["updated_at"]; refreshing=_scan_state["refreshing"]; last_error=_scan_state["last_error"]; index_state=dict(_index_state)
    if result:
        payload=dict(result); payload["indices"]=list(index_state["indices"]) if index_state["indices"] else payload.get("indices",[]); payload.update({"refreshing":refreshing or index_state["refreshing"],"cache_age_seconds":round(max(0,time.time()-updated_at),1),"index_updated_at":index_state["updated_at"],"index_last_error":index_state["last_error"]}); payload["stale"]=payload["cache_age_seconds"]>=SCAN_REFRESH_SECONDS; return payload
    return {"success":True,"message":"Market data is initializing in the background.","count":0,"scanned":0,"successful":0,"time_seconds":0,"stocks":[],"top_opportunities":[],"indices":list(index_state["indices"]),"refreshing":refreshing or index_state["refreshing"],"cache_age_seconds":None,"stale":True,"last_error":last_error,"index_last_error":index_state["last_error"]}
def _background_refresh_loop():
    time.sleep(2)
    while True:
        try: _ensure_index_refresh(); _ensure_scan_refresh()
        except Exception as error: print("BACKGROUND REFRESH LOOP ERROR:",error)
        time.sleep(15)
threading.Thread(target=_background_refresh_loop,name="x10-refresh-loop",daemon=True).start()
@app.route("/api/historical/<path:symbol>")
@login_required
def historical(symbol):
    try:
        instrument=instrument_manager.find_stock(symbol)
        if not instrument:return jsonify({"success":False,"message":f"Angel One instrument not found: {symbol}","data":[]}),404
        result=angel_service.get_historical_data(instrument["symbol"],instrument["token"],days=400,interval="ONE_DAY",exchange=instrument.get("exchange","NSE"));return jsonify(result),(200 if result.get("success") else 502)
    except Exception as error:return jsonify({"success":False,"message":str(error),"data":[]}),500
@app.route("/login",methods=["GET","POST"])
def login():
    if is_authenticated():return redirect(url_for("home"))
    error=None
    if request.method=="POST":
        if request.form.get("user_id","")==APP_USER_ID and request.form.get("password","")==APP_PASSWORD:session.clear();session["authenticated"]=True;session["user_id"]=APP_USER_ID;return redirect(url_for("home"))
        error="Invalid User ID or Password."
    return render_template("login.html",error=error)
@app.route("/logout")
def logout():session.clear();return redirect(url_for("login"))
@app.route("/")
@login_required
def home():
    html=render_template("index.html");html=html.replace("timer=setInterval(()=>{loadScan();loadIndices()},30000);","timer=setInterval(()=>{loadScan();loadIndices()},60000);")
    guard_js='''<script>(function(){const originalLoadScan=window.loadScan,originalLoadIndices=window.loadIndices;let scanBusy=false,indexBusy=false;window.loadScan=async function(){if(scanBusy||document.hidden)return;scanBusy=true;try{return await originalLoadScan()}finally{scanBusy=false}};window.loadIndices=async function(){if(indexBusy||document.hidden)return;indexBusy=true;try{return await originalLoadIndices()}finally{indexBusy=false}};if(window.timer)clearInterval(window.timer);window.timer=setInterval(function(){if(!document.hidden){window.loadScan();window.loadIndices()}},60000);document.addEventListener('visibilitychange',function(){if(!document.hidden){window.loadScan();window.loadIndices()}})})();</script>'''
    tv_chart_js='''<style>.az-tv-chart{height:100%;width:100%;min-height:360px;background:#07111f;border-radius:12px;overflow:hidden}.az-tv-chart .tradingview-widget-container,.az-tv-chart .tradingview-widget-container__widget{height:100%!important;width:100%!important}.az-tv-chart .tradingview-widget-copyright{display:none}</style><script>(function(){const legacyOpenInstrument=window.openInstrument;const indexSymbols={'NIFTY 50':'NSE:NIFTY','BANK NIFTY':'NSE:BANKNIFTY','SENSEX':'BSE:SENSEX','INDIA VIX':'NSE:INDIAVIX'};function tvSymbol(s){if(s&&s.isIndex)return indexSymbols[String(s.name||s.symbol||'').toUpperCase()]||('NSE:'+String(s.symbol||s.name||'').toUpperCase().replace(/\s+/g,''));const raw=String((s&&s.symbol)||'').toUpperCase().replace(/\.NS$/,'');return raw?('NSE:'+raw):'NSE:NIFTY'}function tvChart(symbol){const wrap=document.getElementById('azChartWrap');if(!wrap)return;wrap.innerHTML='';const outer=document.createElement('div');outer.className='az-tv-chart tradingview-widget-container';const widget=document.createElement('div');widget.className='tradingview-widget-container__widget';outer.appendChild(widget);wrap.appendChild(outer);const script=document.createElement('script');script.type='text/javascript';script.src='https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';script.async=true;script.text=JSON.stringify({autosize:true,symbol:symbol,interval:'D',timezone:'exchange',theme:'dark',style:'1',withdateranges:true,hide_side_toolbar:false,allow_symbol_change:true,save_image:false,locale:'en',calendar:false,support_host:'https://www.tradingview.com'});outer.appendChild(script);document.getElementById('azChartStatus').textContent='TradingView · '+symbol+' · live interactive chart'}window.openInstrument=async function(s){const item=s||{};try{if(item.isIndex){currentInstrument=item;const modal=document.getElementById('azModal');modal.classList.add('open');modal.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';document.getElementById('azTitle').textContent=item.name||item.symbol||'Instrument';document.getElementById('azSubtitle').textContent=(item.name||item.symbol||'')+' · TradingView · INDEX';if(typeof renderDNA==='function')renderDNA(item);if(typeof renderTrade==='function')renderTrade(item);if(typeof switchTab==='function')switchTab('chart');tvChart(tvSymbol(item));return}await legacyOpenInstrument(item);setTimeout(function(){tvChart(tvSymbol(item))},50)}catch(error){console.error('TradingView chart error:',error);const wrap=document.getElementById('azChartWrap');if(wrap)wrap.innerHTML='<div class="az-error">TradingView chart could not be loaded.<br>'+esc(error.message||error)+'</div>}}})();</script>'''
    html=html.replace("</body>",guard_js+tv_chart_js+"</body>");return html
@app.route("/api/index-historical/<path:name>")
@login_required
def index_historical(name):
    try:
        key=unquote(name).upper().strip();definition=INDEX_DEFINITIONS.get(key)
        if not definition:
            for index_name in INDEX_DEFINITIONS:
                if index_name.upper()==key:definition=INDEX_DEFINITIONS[index_name];key=index_name;break
        if not definition:return jsonify({"success":False,"message":f"Index not found: {name}","data":[]}),404
        result=angel_service.get_historical_data(definition["tradingsymbol"],definition["token"],days=400,interval="ONE_DAY",exchange=definition.get("exchange","NSE"));return jsonify(result),(200 if result.get("success") else 502)
    except Exception as error:return jsonify({"success":False,"message":str(error),"data":[]}),500
@app.route("/api/analyze/<symbol>")
@login_required
def analyze_stock(symbol):
    try:
        result=stock_service.get_stock_analysis(symbol.upper().strip())
        if not result:return jsonify({"success":False,"message":"No analysis result returned."}),500
        return jsonify(result)
    except Exception as error:return jsonify({"success":False,"message":str(error)}),500
@app.route("/api/scan")
@login_required
def scan():_ensure_index_refresh();_ensure_scan_refresh();return jsonify(_snapshot_response())
@app.route("/api/scan/refresh")
@login_required
def scan_refresh():_ensure_index_refresh(force=True);_ensure_scan_refresh(force=True);return jsonify({"success":True,"message":"X10 scan and index refresh started in background.","refreshing":True})
@app.route("/api/indices")
@login_required
def indices_endpoint():
    _ensure_index_refresh()
    return jsonify({"success":True,"indices":list(_index_state["indices"]),"cached":bool(_index_state["indices"]),"refreshing":_index_state["refreshing"],"updated_at":_index_state["updated_at"],"last_error":_index_state["last_error"]})
@app.route("/api/instruments")
@login_required
def instruments_endpoint():
    try:
        result=instrument_manager.load_cache()
        if not result.get("success"):return jsonify(result),500
        stocks=instrument_manager.get_nse_equities();return jsonify({"success":True,"count":len(stocks),"stocks":stocks})
    except Exception as error:return jsonify({"success":False,"message":str(error),"stocks":[]}),500
@app.route("/api/instruments/refresh")
@login_required
def refresh_instruments_endpoint():
    try:
        result=instrument_manager.refresh()
        if not result.get("success"):return jsonify(result),500
        stocks=instrument_manager.get_nse_equities();return jsonify({"success":True,"count":len(stocks),"message":"Angel One instrument master refreshed.","stocks":stocks})
    except Exception as error:return jsonify({"success":False,"message":str(error),"stocks":[]}),500
@app.route("/api/instrument/<symbol>")
@login_required
def instrument_endpoint(symbol):
    try:
        stock=instrument_manager.find_stock(symbol)
        if not stock:return jsonify({"success":False,"message":"Stock not found."}),404
        return jsonify({"success":True,"stock":stock})
    except Exception as error:return jsonify({"success":False,"message":str(error)}),404
