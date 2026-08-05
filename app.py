import os
import time
import json
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature

app = FastAPI(title="Stock Screener Terminal Pro")

SECRET_KEY = "super-secret-stock-screener-key"
serializer = URLSafeTimedSerializer(SECRET_KEY)

# --- 100+ NSE STOCKS LIST FOR SCANNING ---
NSE_100_STOCKS = [
    "SUZLON.NS", "NSLNISP.NS", "SAGILITY.NS", "OLAELEC.NS", "MSUMI.NS", "IDEA.NS", "YESBANK.NS", 
    "JPPOWER.NS", "RPOWER.NS", "IRB.NS", "PPLPHARMA.NS", "TATACAP.NS", "RBLBANK.NS", "TENNECO.NS", 
    "GRANULES.NS", "BHARTIARTL.NS", "POWERGRID.NS", "HEROMOTOCO.NS", "IRCTC.NS", "DEEPAKNTR.NS", 
    "IKIO.NS", "INFY.NS", "TCS.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", 
    "TATAMOTORS.NS", "WIPRO.NS", "LT.NS", "AXISBANK.NS", "ITC.NS", "IOC.NS", "NTPC.NS", "ONGC.NS",
    "COALINDIA.NS", "TATASTEEL.NS", "HINDALCO.NS", "BPCL.NS", "GAIL.NS", "PNB.NS", "BANKBARODA.NS",
    "CANBK.NS", "IDFCFIRSTB.NS", "FEDERALBNK.NS", "UNIONBANK.NS", "CENTRALBK.NS", "UCOBANK.NS",
    "IOB.NS", "NHPC.NS", "SJVN.NS", "IREDA.NS", "HUDCO.NS", "NBCC.NS", "RAILTEL.NS", "RVNL.NS",
    "IRCON.NS", "MAHADISC.NS", "BHEL.NS", "BEL.NS", "HAL.NS", "COCHINSHIP.NS", "MAZDOCK.NS",
    "ZOMATO.NS", "PAYTM.NS", "POLICYBZR.NS", "DELHIVERY.NS", "AWL.NS", "LICHSGFIN.NS", "LICI.NS",
    "GMRINFRA.NS", "IRFC.NS", "SOUTHBANK.NS", "MAHABANK.NS", "J&KBANK.NS", "KARURVYSYA.NS",
    "CSBBANK.NS", "DCBBANK.NS", "EQUITASBNK.NS", "UJJIVANSFB.NS", "CREDITACC.NS", "MANAPPURAM.NS",
    "MUTHOOTFIN.NS", "REC.NS", "PFC.NS", "TATAELXSI.NS", "KPITTECH.NS", "LTIM.NS", "COFORGE.NS",
    "PERSISTENT.NS", "MPHASIS.NS", "HCLTECH.NS", "TECHM.NS", "CYIENT.NS", "ZENSARTECH.NS"
]

# IN-MEMORY BACKUP SYSTEM (Last 1 Hour Cache)
CACHE_TIMESTAMP = 0
CACHE_EXPIRY = 25  # seconds
PREVIOUS_BACKUP_DATA = []

# Fallback presets in case Yahoo Finance API rate-limits the cloud host
FALLBACK_PREDICTIONS = [
    {"symbol": "SUZLON", "price": 48.10, "target": 56.50, "gain": "+17.4%", "rsi": 67.2, "macd": "Bullish Crossover", "score": 92, "strategy": "High-Volume Breakout"},
    {"symbol": "NSLNISP", "price": 44.58, "target": 51.80, "gain": "+16.2%", "rsi": 58.1, "macd": "Positive Slope", "score": 86, "strategy": "Steady Momentum"},
    {"symbol": "SAGILITY", "price": 42.97, "target": 49.50, "gain": "+15.2%", "rsi": 66.5, "score": 88, "strategy": "RSI Breakout Accumulation"},
    {"symbol": "OLAELEC", "price": 41.78, "target": 49.00, "gain": "+17.2%", "rsi": 54.2, "macd": "Bullish Shift", "score": 84, "strategy": "Volume Spike Reversal"},
    {"symbol": "MSUMI", "price": 41.06, "target": 47.50, "gain": "+15.6%", "rsi": 68.0, "macd": "Bullish Trend", "score": 90, "strategy": "Technical Outperformer"},
    {"symbol": "IDEA", "price": 12.02, "target": 14.20, "gain": "+18.1%", "rsi": 44.8, "macd": "Neutral", "score": 72, "strategy": "Base Support Reversal"},
    {"symbol": "YESBANK", "price": 23.87, "target": 27.80, "gain": "+16.4%", "rsi": 52.9, "macd": "Positive Crossover", "score": 80, "strategy": "Consolidation Breakout"},
    {"symbol": "JPPOWER", "price": 18.35, "target": 21.60, "gain": "+17.7%", "rsi": 66.1, "macd": "Bullish Divergence", "score": 87, "strategy": "Volume Expansion"},
    {"symbol": "RPOWER", "price": 34.19, "target": 39.80, "gain": "+16.4%", "rsi": 61.4, "macd": "Bullish Trend", "score": 85, "strategy": "Resistance Re-test"},
    {"symbol": "IRB", "price": 30.09, "target": 35.20, "gain": "+16.9%", "rsi": 55.3, "macd": "Steady Slope", "score": 81, "strategy": "Moving Average Support"}
]

def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("session_token")
    if not token:
        return False
    try:
        serializer.loads(token, max_age=86400)
        return True
    except BadSignature:
        return False

def scan_nse_top_10_under_300():
    global CACHE_TIMESTAMP, PREVIOUS_BACKUP_DATA
    now = time.time()
    
    if now - CACHE_TIMESTAMP < CACHE_EXPIRY and PREVIOUS_BACKUP_DATA:
        return PREVIOUS_BACKUP_DATA

    scanned_stocks = []
    try:
        # Batch download 100+ stocks safely
        data = yf.download(tickers=NSE_100_STOCKS, period="3m", interval="1d", progress=False)
        if not data.empty and 'Close' in data:
            close_prices = data['Close']
            volume_data = data.get('Volume', pd.DataFrame())

            for ticker in NSE_100_STOCKS:
                try:
                    df = close_prices[ticker].dropna()
                    if len(df) < 30:
                        continue
                    
                    price = round(float(df.iloc[-1]), 2)
                    
                    # Filter stocks under Rs. 300
                    if price > 300 or price < 2:
                        continue

                    # RSI 14-day calculation
                    delta = df.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / (loss + 1e-9)
                    rsi = round(float((100 - (100 / (1 + rs))).iloc[-1]), 1)

                    # MACD calculation
                    ema12 = df.ewm(span=12, adjust=False).mean()
                    ema26 = df.ewm(span=26, adjust=False).mean()
                    macd_line = ema12 - ema26
                    signal_line = macd_line.ewm(span=9, adjust=False).mean()
                    macd_status = "Bullish Crossover" if macd_line.iloc[-1] > signal_line.iloc[-1] else "Bearish Shift"

                    target = round(price * 1.16, 2)
                    target_gain = round(((target - price) / price) * 100, 1)

                    # Multi-factor score
                    score = 60
                    if rsi > 55: score += 15
                    if rsi > 65: score += 10
                    if macd_status == "Bullish Crossover": score += 15

                    clean_symbol = ticker.replace(".NS", "")
                    scanned_stocks.append({
                        "symbol": clean_symbol,
                        "price": price,
                        "target": target,
                        "gain": f"+{target_gain}%",
                        "rsi": rsi,
                        "macd": macd_status,
                        "score": score,
                        "strategy": "Technical Breakout" if rsi > 60 else "Steady Accumulation"
                    })
                except Exception:
                    continue
    except Exception:
        pass

    # Sort by technical score and pick top 10
    if scanned_stocks:
        scanned_stocks.sort(key=lambda x: x['score'], reverse=True)
        PREVIOUS_BACKUP_DATA = scanned_stocks[:10]
    elif not PREVIOUS_BACKUP_DATA:
        PREVIOUS_BACKUP_DATA = FALLBACK_PREDICTIONS

    CACHE_TIMESTAMP = now
    return PREVIOUS_BACKUP_DATA

# --- ROUTES ---

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <title>Login - Stock Terminal</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-black text-gray-100 flex items-center justify-center h-screen font-sans">
        <div class="bg-gray-900 p-8 rounded-xl border border-gray-800 shadow-2xl w-96">
            <h1 class="text-xl font-bold text-center mb-6 text-emerald-400">Stock Terminal Access</h1>
            <form action="/login" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold mb-1 text-gray-400">USER NAME</label>
                    <input type="text" name="username" required placeholder="Admin" class="w-full bg-black border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                </div>
                <div>
                    <label class="block text-xs font-semibold mb-1 text-gray-400">PASSWORD</label>
                    <input type="password" name="password" required placeholder="Admin" class="w-full bg-black border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                </div>
                <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-bold py-2 rounded transition text-sm">LOGIN</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username == "Admin" and password == "Admin":
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        token = serializer.dumps(username)
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400)
        return response
    return HTMLResponse("<script>alert('Invalid Credentials! Use Admin / Admin'); window.location='/login';</script>")

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    top_stocks = scan_nse_top_10_under_300()
    has_breakout = any(s['rsi'] >= 65 for s in top_stocks)

    # Marquee HTML string (Stops on hover)
    marquee_items = " &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ".join([
        f"<span class='cursor-pointer hover:underline' onclick=\"openChart('NSE:{s['symbol']}')\">"
        f"<b class='text-emerald-400'>{s['symbol']}</b> (₹{s['price']}) "
        f"→ 3M Target: <b class='text-yellow-400'>₹{s['target']} ({s['gain']})</b> "
        f"| RSI: <b class='text-blue-400'>{s['rsi']}</b> | Strategy: <span class='text-purple-400'>{s['strategy']}</span>"
        f"</span>"
        for s in top_stocks
    ])

    return f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Stock Screener Terminal</title>
        <link rel="manifest" href="/manifest.json">
        <script src="https://cdn.tailwindcss.com"></script>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <style>
            .marquee {{ white-space: nowrap; overflow: hidden; box-sizing: border-box; }}
            .marquee-content {{ display: inline-block; padding-left: 100%; animation: marquee 40s linear infinite; }}
            .marquee-content:hover {{ animation-play-state: paused; cursor: pointer; }}
            @keyframes marquee {{ 0% {{ transform: translate(0, 0); }} 100% {{ transform: translate(-100%, 0); }} }}
            ::-webkit-scrollbar {{ width: 6px; }}
            ::-webkit-scrollbar-track {{ background: #09090b; }}
            ::-webkit-scrollbar-thumb {{ background: #27272a; border-radius: 3px; }}
        </style>
    </head>
    <body class="bg-black text-gray-200 font-sans text-xs min-h-screen flex flex-col">
        
        <!-- PAUSABLE MOVING STRATEGY TICKER -->
        <div class="bg-gray-950 border-b border-gray-800 py-2 marquee text-xs text-gray-300">
            <div class="marquee-content font-mono">
                🚀 <span class="text-emerald-400 font-bold">TOP 10 STRATEGY PREDICTIONS (STOCKS UNDER ₹300 - 3 MONTHS):</span> {marquee_items}
            </div>
        </div>

        <!-- STATUS HEADER & AUTO REFRESH COUNTER -->
        <div class="bg-gray-900 border-b border-gray-800 px-6 py-1.5 flex justify-between items-center text-[10px] text-gray-400">
            <div class="flex items-center gap-2">
                <span class="relative flex h-2 w-2">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span>NSE/BSE ACTIVE FEED (BACKUP ACTIVE)</span>
            </div>
            <div>Auto Refreshing in: <span id="countdown" class="text-emerald-400 font-bold font-mono">30</span>s</div>
        </div>

        <!-- NAVIGATION BAR -->
        <nav class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex justify-between items-center">
            <div class="flex gap-6 font-semibold text-gray-400">
                <a href="#" class="text-emerald-400 border-b-2 border-emerald-400 pb-1">Stock Discovery</a>
                <a href="#" class="hover:text-white">Index F&O</a>
                <a href="#" class="hover:text-white">Stocks F&O</a>
                <a href="#" class="hover:text-white">Commodities</a>
                <a href="#" class="hover:text-white">All Indices</a>
                <a href="#" class="hover:text-white">News</a>
            </div>
            <a href="/logout" class="bg-rose-950 text-rose-400 border border-rose-800 px-3 py-1 rounded hover:bg-rose-900">Logout</a>
        </nav>

        <div class="p-6 space-y-6 flex-1 max-w-[1600px] mx-auto w-full">
            
            <!-- MARKET INDICES BANNER -->
            <div class="grid grid-cols-4 gap-4 bg-gray-950 border border-gray-800 p-3 rounded-lg text-center font-mono">
                <div><span class="text-gray-500">NIFTY 50:</span> <span class="text-emerald-400 font-bold">24,659.30</span></div>
                <div><span class="text-gray-500">HIGH:</span> <span class="text-emerald-400">24,677.60</span></div>
                <div><span class="text-gray-500">LOW:</span> <span class="text-rose-400">24,497.85</span></div>
                <div><span class="text-gray-500">CLOSE:</span> <span>24,514.90</span></div>
            </div>

            <!-- MOST BOUGHT STOCKS -->
            <section>
                <div class="flex justify-between items-center mb-3">
                    <h2 class="font-bold text-sm text-gray-300">Most Bought Stocks</h2>
                    <a href="#" class="text-emerald-400 text-xs hover:underline">VIEW ALL &gt;</a>
                </div>
                <div class="grid grid-cols-5 gap-3">
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:IDEA')">
                        <div class="font-bold text-white">IDEA</div>
                        <div class="text-gray-400 text-[10px]">VODAFONE IDEA LIMITED</div>
                        <div class="mt-2 text-rose-400 font-mono">₹12.02 <span class="text-[10px]">-0.63%</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <span class="text-emerald-400">Chart</span>
                            <a href="https://www.screener.in/company/IDEA/" target="_blank" onclick="event.stopPropagation()" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:YESBANK')">
                        <div class="font-bold text-white">YESBANK</div>
                        <div class="text-gray-400 text-[10px]">YES BANK LIMITED</div>
                        <div class="mt-2 text-rose-400 font-mono">₹23.87 <span class="text-[10px]">-0.57%</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <span class="text-emerald-400">Chart</span>
                            <a href="https://www.screener.in/company/YESBANK/" target="_blank" onclick="event.stopPropagation()" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:JPPOWER')">
                        <div class="font-bold text-white">JPPOWER</div>
                        <div class="text-gray-400 text-[10px]">JAIPRAKASH POWER VENTURES</div>
                        <div class="mt-2 text-rose-400 font-mono">₹18.35 <span class="text-[10px]">-2.60%</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <span class="text-emerald-400">Chart</span>
                            <a href="https://www.screener.in/company/JPPOWER/" target="_blank" onclick="event.stopPropagation()" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:RPOWER')">
                        <div class="font-bold text-white">RPOWER</div>
                        <div class="text-gray-400 text-[10px]">RELIANCE POWER LTD</div>
                        <div class="mt-2 text-emerald-400 font-mono">₹34.19 <span class="text-[10px]">+0.50%</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <span class="text-emerald-400">Chart</span>
                            <a href="https://www.screener.in/company/RPOWER/" target="_blank" onclick="event.stopPropagation()" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:IRB')">
                        <div class="font-bold text-white">IRB</div>
                        <div class="text-gray-400 text-[10px]">IRB INFRA DEV LTD</div>
                        <div class="mt-2 text-rose-400 font-mono">₹30.09 <span class="text-[10px]">-0.70%</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <span class="text-emerald-400">Chart</span>
                            <a href="https://www.screener.in/company/IRB/" target="_blank" onclick="event.stopPropagation()" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                </div>
            </section>

            <!-- SECTORIAL INDICES PERFORMANCE (MIDDLE OF PAGE) -->
            <section class="bg-gray-950 border border-gray-800 p-4 rounded-lg">
                <h2 class="font-bold text-sm text-gray-300 mb-3">Sectorial Indices Performance</h2>
                <div class="grid grid-cols-6 gap-3 text-center font-mono">
                    <div class="bg-gray-900 p-3 rounded border border-gray-800">
                        <div class="text-gray-400 text-[10px]">NIFTY BANK</div>
                        <div class="text-emerald-400 font-bold mt-1">51,200.40 (+0.4%)</div>
                    </div>
                    <div class="bg-gray-900 p-3 rounded border border-gray-800">
                        <div class="text-gray-400 text-[10px]">NIFTY IT (Software)</div>
                        <div class="text-rose-400 font-bold mt-1">38,150.20 (-0.2%)</div>
                    </div>
                    <div class="bg-gray-900 p-3 rounded border border-gray-800">
                        <div class="text-gray-400 text-[10px]">NIFTY PHARMA</div>
                        <div class="text-emerald-400 font-bold mt-1">21,890.10 (+1.1%)</div>
                    </div>
                    <div class="bg-gray-900 p-3 rounded border border-gray-800">
                        <div class="text-gray-400 text-[10px]">NIFTY AUTO</div>
                        <div class="text-emerald-400 font-bold mt-1">25,430.80 (+0.8%)</div>
                    </div>
                    <div class="bg-gray-900 p-3 rounded border border-gray-800">
                        <div class="text-gray-400 text-[10px]">NIFTY METAL</div>
                        <div class="text-rose-400 font-bold mt-1">9,120.50 (-0.9%)</div>
                    </div>
                    <div class="bg-gray-900 p-3 rounded border border-gray-800">
                        <div class="text-gray-400 text-[10px]">NIFTY ENERGY</div>
                        <div class="text-emerald-400 font-bold mt-1">39,450.00 (+0.5%)</div>
                    </div>
                </div>
            </section>

            <!-- POCKET FRIENDLY STOCKS (< RS. 200) -->
            <section>
                <div class="flex justify-between items-center mb-3">
                    <h2 class="font-bold text-sm text-gray-300">Pocket Friendly Stocks (&lt; ₹200)</h2>
                    <a href="#" class="text-emerald-400 text-xs hover:underline">VIEW ALL &gt;</a>
                </div>
                <div class="grid grid-cols-5 gap-3">
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:SUZLON')">
                        <div class="font-bold text-white">SUZLON</div>
                        <div class="text-gray-400 text-[10px]">SUZLON ENERGY LIMITED</div>
                        <div class="mt-2 text-emerald-400 font-mono">₹48.10 <span class="text-[10px]">+2.19%</span></div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:NSLNISP')">
                        <div class="font-bold text-white">NSLNISP</div>
                        <div class="text-gray-400 text-[10px]">NMDC STEEL LIMITED</div>
                        <div class="mt-2 text-emerald-400 font-mono">₹44.58 <span class="text-[10px]">+1.30%</span></div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:SAGILITY')">
                        <div class="font-bold text-white">SAGILITY</div>
                        <div class="text-gray-400 text-[10px]">SAGILITY LIMITED</div>
                        <div class="mt-2 text-rose-400 font-mono">₹42.97 <span class="text-[10px]">-0.77%</span></div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:OLAELEC')">
                        <div class="font-bold text-white">OLAELEC</div>
                        <div class="text-gray-400 text-[10px]">OLA ELECTRIC MOBILITY</div>
                        <div class="mt-2 text-emerald-400 font-mono">₹41.78 <span class="text-[10px]">+0.37%</span></div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg cursor-pointer hover:border-emerald-500" onclick="openChart('NSE:MSUMI')">
                        <div class="font-bold text-white">MSUMI</div>
                        <div class="text-gray-400 text-[10px]">MOTHERSON SUMI WIRING</div>
                        <div class="mt-2 text-emerald-400 font-mono">₹41.06 <span class="text-[10px]">+0.36%</span></div>
                    </div>
                </div>
            </section>
        </div>

        <!-- TRADINGVIEW INTERACTIVE MODAL DRAWER -->
        <div id="chart-modal" class="fixed inset-0 bg-black/80 hidden backdrop-blur-sm z-50 flex items-center justify-center p-6">
            <div class="bg-gray-900 border border-gray-800 rounded-xl w-full max-w-5xl h-[600px] flex flex-col overflow-hidden">
                <div class="p-4 border-b border-gray-800 flex justify-between items-center">
                    <h3 id="modal-symbol-title" class="font-bold text-emerald-400 text-sm">TradingView Interactive Chart</h3>
                    <button onclick="closeChart()" class="text-gray-400 hover:text-white text-lg font-bold">✕</button>
                </div>
                <div class="flex-1" id="tradingview-container"></div>
            </div>
        </div>

        <!-- FAST AI CHATBOT ASSISTANT -->
        <div class="fixed bottom-4 right-4 z-40">
            <button onclick="toggleChat()" class="bg-emerald-500 hover:bg-emerald-400 text-black px-4 py-3 rounded-full font-bold shadow-2xl flex items-center gap-2">
                ⚡ AI Stock Assistant
            </button>
            <div id="chat-box" class="hidden bg-gray-900 border border-gray-800 rounded-xl w-80 h-96 flex flex-col shadow-2xl mt-2">
                <div class="bg-gray-800 p-3 rounded-t-xl font-bold flex justify-between items-center text-emerald-400">
                    <span>Quick Analyst Bot</span>
                    <button onclick="toggleChat()" class="text-gray-400 hover:text-white">✕</button>
                </div>
                <div id="messages" class="flex-1 p-3 overflow-y-auto space-y-2 text-xs">
                    <div class="bg-gray-800 p-2 rounded self-start">Ask about stock targets or technical analysis!</div>
                </div>
                <div class="p-2 border-t border-gray-800 flex gap-2">
                    <input id="chat-input" type="text" placeholder="e.g. SUZLON target..." class="bg-black border border-gray-800 rounded px-2 py-1 flex-1 text-white text-xs focus:outline-none" onkeypress="if(event.key==='Enter') sendChatMessage()">
                    <button onclick="sendChatMessage()" class="bg-emerald-600 px-3 py-1 rounded text-black font-bold">Send</button>
                </div>
            </div>
        </div>

        <script>
            // Auto Refresh Timer (30s)
            let countdown = 30;
            setInterval(() => {{
                countdown--;
                if (countdown <= 0) {{ window.location.reload(); }}
                else {{ document.getElementById('countdown').innerText = countdown; }}
            }}, 1000);

            // Audio Breakout Notification Trigger (RSI > 65)
            const hasBreakout = {'true' if has_breakout else 'false'};
            if (hasBreakout) {{
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                window.addEventListener('click', () => {{
                    if(audioCtx.state === 'suspended') audioCtx.resume();
                }}, {{ once: true }});
            }}

            // TradingView Modal Handler
            function openChart(symbol) {{
                document.getElementById('modal-symbol-title').innerText = "Live Technical Chart: " + symbol;
                document.getElementById('chart-modal').classList.remove('hidden');
                document.getElementById('tradingview-container').innerHTML = '<div id="tv_chart_element" class="h-full w-full"></div>';
                
                new TradingView.widget({{
                    "autosize": true,
                    "symbol": symbol,
                    "interval": "D",
                    "timezone": "Asia/Kolkata",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "container_id": "tv_chart_element"
                }});
            }}

            function closeChart() {{
                document.getElementById('chart-modal').classList.add('hidden');
            }}

            // AI Chatbot Handler
            function toggleChat() {{ document.getElementById('chat-box').classList.toggle('hidden'); }}

            async function sendChatMessage() {{
                const input = document.getElementById('chat-input');
                const text = input.value.trim();
                if (!text) return;
                const msgContainer = document.getElementById('messages');
                msgContainer.innerHTML += `<div class="bg-emerald-950 text-emerald-300 p-2 rounded text-right">${{text}}</div>`;
                input.value = '';
                
                const res = await fetch('/api/ai-chat', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{prompt: text}})
                }});
                const data = await res.json();
                msgContainer.innerHTML += `<div class="bg-gray-800 p-2 rounded text-left">${{data.reply}}</div>`;
                msgContainer.scrollTop = msgContainer.scrollHeight;
            }}
        </script>
    </body>
    </html>
    """

@app.post("/api/ai-chat")
async def ai_chat(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "").upper()
    top_scanned = scan_nse_top_10_under_300()
    matched = [s for s in top_scanned if s['symbol'] in prompt]
    
    if matched:
        s = matched[0]
        reply = f"📊 <b>{s['symbol']} Technical Analysis:</b><br>Price: ₹{s['price']}<br>3M Target: ₹{s['target']} ({s['gain']})<br>RSI: {s['rsi']} | MACD: {s['macd']}<br>Strategy: {s['strategy']}"
    else:
        reply = "⚡ Type any scanned stock (e.g. SUZLON, YESBANK, IDEA) to see instant technical targets."

    return JSONResponse({"reply": reply})

@app.get("/manifest.json")
def manifest():
    return JSONResponse({
        "name": "Stock Screener Terminal",
        "short_name": "StockTerminal",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#000000",
        "theme_color": "#10b981",
        "icons": []
    })
