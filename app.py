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

        # Phase 1: calculate and publish the X10 shortlist without waiting for
        # slower index historical analysis. The existing X10 scoring is unchanged.
        result = scanner.scan_market(limit=30, include_indices=False)
        if not result.get("success"):
            raise RuntimeError(result.get("message", "Angel One scanner failed."))

        stocks = [clean_stock(stock) for stock in result.get("stocks", []) if isinstance(stock, dict)]
        payload = {
            "success": True,
            "message": "X10 shortlist ready. Index analysis is updating in the background.",
            "count": len(stocks),
            "scanned": result.get("scanned", 0),
            "successful": result.get("successful", 0),
            "time_seconds": result.get("time_seconds", round(time.time() - started, 2)),
            "stocks": stocks,
            "indices": [],
            "updated_at": time.time(),
        }
        with _scan_lock:
            _scan_state["result"] = payload
            _scan_state["updated_at"] = payload["updated_at"]
            _scan_state["last_error"] = None

        # Phase 2: keep the index work off the critical path. The shortlist is
        # already visible to the frontend while these requests are running.
        try:
            indices = scanner._get_index_snapshots()
            with _scan_lock:
                if _scan_state["result"] is not None:
                    _scan_state["result"] = dict(_scan_state["result"])
                    _scan_state["result"]["indices"] = indices
                    _scan_state["result"]["message"] = "Market scan completed."
        except Exception as error:
            print("BACKGROUND INDEX ANALYSIS ERROR:", error)
            with _scan_lock:
                if _scan_state["result"] is not None:
                    _scan_state["result"] = dict(_scan_state["result"])
                    _scan_state["result"]["message"] = "X10 shortlist ready. Index analysis is temporarily unavailable."
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

@app.route("/api/historical/<path:symbol>")
@login_required
def historical(symbol):
    """Return Angel One historical candles for an individual stock or index."""
    try:
        instrument = instrument_manager.find_stock(symbol)
        if not instrument:
            return jsonify({"success": False, "message": f"Angel One instrument not found: {symbol}", "data": []}), 404
        result = angel_service.get_historical_data(
            instrument["symbol"],
            instrument["token"],
            days=400,
            interval="ONE_DAY",
            exchange=instrument.get("exchange", "NSE"),
        )
        return jsonify(result), (200 if result.get("success") else 502)
    except Exception as error:
        print("HISTORICAL API ERROR:", error)
        return jsonify({"success": False, "message": str(error), "data": []}), 500

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
function parseCandle(x){if(Array.isArray(x))return{t:x[0],o:+x[1],h:+x[2],l:+x[3],c:+x[4],v:+(x[5]||0)};return{t:x.date||x.timestamp||x.time||x.ts,o:+(x.open??x.Open),h:+(x.high??x.High),l:+(x.low??x.Low),c:+(x.close??x.Close),v:+(x.volume??x.Volume??0)}}
function drawChart(box,candles,symbol){box.innerHTML="";box.style.position="relative";const head=document.createElement("div");head.style.cssText="position:absolute;z-index:2;left:14px;top:10px;font:700 12px Inter,Arial;color:#dce9f5;background:rgba(7,17,31,.72);padding:6px 9px;border-radius:7px";head.textContent="ANGEL ONE · "+symbol+" · DAILY";box.appendChild(head);const canvas=document.createElement("canvas");canvas.style.cssText="width:100%;height:100%;display:block";box.appendChild(canvas);const ctx=canvas.getContext("2d");const resize=()=>{const dpr=devicePixelRatio||1,w=Math.max(320,box.clientWidth),h=Math.max(280,box.clientHeight);canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);const data=candles.slice(-120),pad={l:54,r:18,t:38,b:62},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b,max=Math.max(...data.map(d=>d.h)),min=Math.min(...data.map(d=>d.l)),span=max-min||1,volMax=Math.max(...data.map(d=>d.v||0),1),volH=Math.min(70,ch*.18),priceH=ch-volH-12,py=p=>pad.t+(max-p)/span*priceH,step=cw/data.length,body=Math.max(2,step*.62);ctx.fillStyle="#07111f";ctx.fillRect(0,0,w,h);ctx.strokeStyle="#183149";ctx.fillStyle="#71879b";ctx.font="10px Arial";for(let i=0;i<5;i++){const y=pad.t+priceH*i/4;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillText((max-span*i/4).toFixed(2),7,y+3)}data.forEach((d,i)=>{const x=pad.l+i*step+step/2,up=d.c>=d.o,yO=py(d.o),yC=py(d.c);ctx.strokeStyle=up?"#20d18b":"#ff5d6c";ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x,py(d.h));ctx.lineTo(x,py(d.l));ctx.stroke();ctx.fillRect(x-body/2,Math.min(yO,yC),body,Math.max(1,Math.abs(yC-yO)))});const volTop=pad.t+priceH+12;data.forEach((d,i)=>{const x=pad.l+i*step+step/2,vh=((d.v||0)/volMax)*volH;ctx.fillStyle=d.c>=d.o?"rgba(32,209,139,.45)":"rgba(255,93,108,.45)";ctx.fillRect(x-body/2,volTop+volH-vh,body,vh)});const last=data[data.length-1];ctx.fillStyle=last.c>=last.o?"#20d18b":"#ff5d6c";ctx.font="800 14px Arial";ctx.fillText("₹"+last.c.toFixed(2),w-pad.r-82,pad.t+18)};new ResizeObserver(resize).observe(box);resize()}
window.loadChart=async function(sym){let raw=(sym||(document.getElementById("tv")||{}).value||"NIFTY").toUpperCase().trim().replace(/^NSE:/,"").replace(/[^A-Z0-9_]/g,"");if(!raw)raw="NIFTY";const input=document.getElementById("tv");if(input)input.value=raw;const box=document.getElementById("chartBox");if(!box)return;box.innerHTML='<div class="empty">Loading Angel One candles for '+raw+'…</div>';try{const r=await fetch('/api/historical/'+encodeURIComponent(raw),{cache:'no-store'}),j=await r.json();if(!r.ok||!j.success)throw new Error(j.message||'Angel One historical data unavailable.');const candles=(j.data||[]).map(parseCandle).filter(d=>[d.o,d.h,d.l,d.c].every(Number.isFinite));if(!candles.length)throw new Error('Angel One returned no candle data for '+raw+'.');drawChart(box,candles,raw)}catch(e){box.innerHTML='<div class="empty">Angel One chart error: '+String(e.message||e)+'</div>'}}
window.addEventListener("load",()=>setTimeout(()=>window.loadChart&&window.loadChart("NIFTY"),150));
})();</script>'''
        html=html.replace('</body>',fix+'</body>').replace('TradingView Chart','Angel One Chart').replace('Reliable direct TradingView embed','Angel One OHLC candles')
        response.set_data(html)
    except Exception as error:
        print("ANGEL CHART INJECTION ERROR:",error)
    return response

@app.after_request
def simplify_dashboard_layout(response):
    if request.path != "/" or "text/html" not in response.content_type:
        return response
    try:
        html=response.get_data(as_text=True)
        ui=r'''<style>
/* Remove duplicate lower chart/analysis blocks: stock details are now opened from stock cards. */
#chart,#analysis{display:none!important}
/* Make the stock chart a first-class action on every stock card/row. */
.op::after{content:'⌁ Open chart + Stock DNA + Trade Plan';display:block;margin-top:10px;padding:7px 9px;border:1px solid rgba(72,167,255,.28);border-radius:8px;background:rgba(72,167,255,.08);color:#8ec8ff;font-size:9px;font-weight:800;text-align:center}
.row::after{content:'▤';margin-left:10px;color:#8ec8ff;font-weight:900}
/* Compact floating AI launcher. */
#assistant{display:none!important}
.az-ai-launcher{position:fixed;right:22px;bottom:22px;z-index:100001;width:50px;height:50px;border-radius:50%;border:1px solid rgba(255,122,24,.55);background:linear-gradient(135deg,#ff8b2b,#ed5d0b);color:#fff;font-size:20px;font-weight:900;box-shadow:0 10px 35px rgba(0,0,0,.45);cursor:pointer}
.az-ai-pop{position:fixed;right:22px;bottom:84px;z-index:100001;width:min(360px,calc(100vw - 24px));height:430px;background:#0b1a2a;border:1px solid #29445d;border-radius:16px;box-shadow:0 25px 80px rgba(0,0,0,.6);display:none;overflow:hidden}
.az-ai-pop.open{display:flex;flex-direction:column}.az-ai-pop-head{height:50px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid #20384f}.az-ai-pop-head b{font-size:13px}.az-ai-pop-head button{border:0;background:transparent;color:#fff;font-size:19px;cursor:pointer}.az-ai-pop-body{flex:1;overflow:auto;padding:10px}.az-ai-pop-msg{max-width:90%;padding:8px 10px;margin:5px 0;border-radius:10px;background:#10263d;border:1px solid #23425d;font-size:11px;line-height:1.4;white-space:pre-wrap}.az-ai-pop-msg.user{margin-left:auto;background:rgba(255,122,24,.16);border-color:rgba(255,122,24,.3)}.az-ai-pop-form{display:flex;gap:6px;padding:9px;border-top:1px solid #20384f}.az-ai-pop-form input{flex:1;min-width:0;height:34px}.az-ai-pop-form button{height:34px;padding:0 12px}.az-ai-quick{display:flex;gap:5px;overflow:auto;padding:7px 9px;border-top:1px solid #20384f}.az-ai-quick button{white-space:nowrap;border:1px solid #20384f;background:#091827;color:#b7c7d8;border-radius:8px;padding:6px 8px;font-size:9px;cursor:pointer}
@media(max-width:700px){.az-ai-launcher{right:14px;bottom:14px}.az-ai-pop{right:12px;bottom:74px;height:58vh}}
</style>
<button class="az-ai-launcher" id="azAiLauncher" title="Azad AI Assistant">✦</button>
<div class="az-ai-pop" id="azAiPop"><div class="az-ai-pop-head"><b>✦ Azad AI Assistant</b><button id="azAiClose">×</button></div><div class="az-ai-pop-body" id="azAiBody"><div class="az-ai-pop-msg">Ask me about a stock, NIFTY, Bank NIFTY, X10 opportunities, technicals or current market news.</div></div><div class="az-ai-quick"><button data-q="What are the most important current Indian stock-market news today?">News</button><button data-q="Explain the current NIFTY and Bank NIFTY market bias and key levels.">NIFTY</button><button data-q="Which affordable X10 stocks currently look strongest and why?">X10</button></div><div class="az-ai-pop-form"><input id="azAiInput" class="input" placeholder="Ask Azad AI…"><button class="btn" id="azAiAsk">Ask</button></div></div>
<script>
(function(){const pop=document.getElementById('azAiPop'),body=document.getElementById('azAiBody'),input=document.getElementById('azAiInput');function add(text,user){const d=document.createElement('div');d.className='az-ai-pop-msg'+(user?' user':'');d.textContent=text;body.appendChild(d);body.scrollTop=body.scrollHeight}async function ask(q){q=(q||input.value||'').trim();if(!q)return;input.value='';add(q,true);add('Thinking…',false);const thinking=body.lastElementChild;try{const r=await fetch('/api/ai-assistant',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q})});const j=await r.json();thinking.remove();add(j.answer||j.message||'No answer available.',false)}catch(e){thinking.remove();add('AI Assistant connection error. Please try again.',false)}}document.getElementById('azAiLauncher').onclick=()=>pop.classList.toggle('open');document.getElementById('azAiClose').onclick=()=>pop.classList.remove('open');document.getElementById('azAiAsk').onclick=()=>ask();input.onkeydown=e=>{if(e.key==='Enter')ask()};document.querySelectorAll('.az-ai-quick button').forEach(b=>b.onclick=()=>ask(b.dataset.q))})();
</script>'''
        html=html.replace('</body>',ui+'</body>')
        response.set_data(html)
    except Exception as error:
        print("DASHBOARD LAYOUT SIMPLIFICATION ERROR:",error)
    return response

@app.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        if request.form.get("user_id", "") == APP_USER_ID and request.form.get("password", "") == APP_PASSWORD:
            session.clear();session["authenticated"]=True;session["user_id"]=APP_USER_ID
            return redirect(url_for("home"))
        error="Invalid User ID or Password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear();return redirect(url_for("login"))

@app.route("/")
@login_required
def home():
    return render_template("index.html")

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
def scan():
    _ensure_scan_refresh();return jsonify(_snapshot_response())

@app.route("/api/scan/refresh")
@login_required
def scan_refresh():
    _ensure_scan_refresh(force=True);return jsonify({"success":True,"message":"X10 scan refresh started in background.","refreshing":True})

@app.route("/api/indices")
@login_required
def indices_endpoint():
    _ensure_scan_refresh();snapshot=_snapshot_response();return jsonify({"success":True,"indices":snapshot.get("indices",[]),"cached":True,"refreshing":snapshot.get("refreshing",False)})

@app.route("/api/historical/<symbol>")
@login_required
def historical_endpoint(symbol):
    try:
        stock=instrument_manager.find_stock(symbol.upper().strip())
        if not stock:return jsonify({"success":False,"message":"NSE equity or supported index symbol not found in Angel One instrument master."}),404
        return jsonify(angel_service.get_historical_data(symbol=stock["symbol"],token=stock["token"],days=200,interval="ONE_DAY",exchange=stock.get("exchange","NSE")))
    except Exception as error:return jsonify({"success":False,"message":str(error),"data":[]}),500

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
    except Exception as error:return jsonify({"success":False,"message":str(error)}),500

@app.route("/api/ai-assistant",methods=["POST"])
@login_required
def ai_assistant():
    api_key=os.getenv("OPENAI_API_KEY","").strip()
    if not api_key:return jsonify({"success":False,"message":"AI Assistant is not configured yet. Add OPENAI_API_KEY to the Render environment variables."}),503
    body=request.get_json(silent=True) or {};question=str(body.get("message","")).strip()
    if not question:return jsonify({"success":False,"message":"Please enter a stock or market question."}),400
    if len(question)>4000:question=question[:4000]
    snapshot=_snapshot_response();context={"indices":snapshot.get("indices",[]),"top_stocks":snapshot.get("stocks",[])[:12],"updated_at":snapshot.get("updated_at")}
    system_prompt="""You are Azad AI Plus, a concise Indian stock-market research assistant. Answer questions about NSE/BSE stocks, indices, technical analysis, market structure, corporate developments and current market news. For anything time-sensitive, especially current news, today's market, recent events, prices or announcements, use web search and clearly distinguish confirmed facts from interpretation. Use the supplied live X10/Angel One snapshot when relevant. Never invent prices, news, targets or company facts. If the user asks whether to buy, provide a decision-support view with bull case, bear case, key levels and risk; do not present certainty or guaranteed returns. Prefer Indian market terminology and INR. Keep answers practical and easy to read. Mention when information is delayed or requires confirmation from the live broker feed."""
    user_prompt=f"User question:\n{question}\n\nCurrent Azad AI Plus market snapshot:\n{context}\n\nAnswer the user's question directly. If current news is requested, search the web before answering and include the publication/source names and dates in the response."
    payload={"model":os.getenv("OPENAI_MODEL","gpt-5.6-luna"),"input":[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],"tools":[{"type":"web_search"}],"max_output_tokens":1400}
    try:
        response=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},json=payload,timeout=45);data=response.json()
        if response.status_code>=400:return jsonify({"success":False,"message":data.get("error",{}).get("message","AI service request failed.")}),502
        answer=data.get("output_text","").strip()
        if not answer:
            for item in data.get("output",[]):
                for content in item.get("content",[]):
                    if content.get("type") in ("output_text","text"):answer+=content.get("text","")
        return jsonify({"success":True,"answer":answer or "I couldn't generate an answer right now. Please try again.","model":payload["model"]})
    except requests.RequestException as error:return jsonify({"success":False,"message":f"AI service connection failed: {error}"}),502

@app.route("/health")
def health():
    return jsonify({"status":"ok","service":"Azad AI Plus","ai_configured":bool(os.getenv("OPENAI_API_KEY"))})

if __name__=="__main__":app.run(host="0.0.0.0",port=5000,debug=False)
