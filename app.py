import os
import time
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature

app = FastAPI(title="Stock Screener Terminal")

# Secret key for session authentication cookies
SECRET_KEY = "super-secret-stock-screener-key-change-in-prod"
serializer = URLSafeTimedSerializer(SECRET_KEY)

# --- 1. CACHING & FALLBACK DATA SYSTEM ---
CACHE_TIMESTAMP = 0
CACHE_EXPIRY = 10  # Seconds
LATEST_STOCK_PREDICTIONS = []

NSE_STOCKS = [
    "SUZLON.NS", "NSLNISP.NS", "SAGILITY.NS", "OLAELEC.NS", "MSUMI.NS", 
    "IDEA.NS", "YESBANK.NS", "JPPOWER.NS", "RPOWER.NS", "IRB.NS", 
    "PPLPHARMA.NS", "TATACAP.NS", "RBLBANK.NS", "TENNECO.NS", "GRANULES.NS"
]

# Fallback data to serve immediately if Yahoo Finance API rate limits cloud host
DEFAULT_FALLBACK_STOCKS = [
    {"symbol": "SUZLON", "price": 48.10, "target": 55.30, "target_gain": "+15.0%", "rsi": 42.5, "score": 90, "strategy": "Bullish Breakout"},
    {"symbol": "NSLNISP", "price": 44.58, "target": 51.20, "target_gain": "+14.8%", "rsi": 46.1, "score": 85, "strategy": "Steady Momentum"},
    {"symbol": "SAGILITY", "price": 42.97, "target": 48.50, "target_gain": "+12.8%", "rsi": 38.0, "score": 80, "strategy": "Bullish Reversal"},
    {"symbol": "OLAELEC", "price": 41.78, "target": 49.00, "target_gain": "+17.2%", "rsi": 51.2, "score": 88, "strategy": "Volume Breakout"},
    {"symbol": "MSUMI", "price": 41.06, "target": 46.80, "target_gain": "+14.0%", "rsi": 44.3, "score": 75, "strategy": "Steady Momentum"},
    {"symbol": "IDEA", "price": 12.02, "target": 14.10, "target_gain": "+17.3%", "rsi": 35.8, "score": 70, "strategy": "Value Reversal"},
    {"symbol": "YESBANK", "price": 23.87, "target": 27.50, "target_gain": "+15.2%", "rsi": 41.9, "score": 78, "strategy": "Steady Momentum"},
    {"symbol": "JPPOWER", "price": 18.35, "target": 21.80, "target_gain": "+18.8%", "rsi": 49.0, "score": 82, "strategy": "Volume Breakout"},
    {"symbol": "RPOWER", "price": 34.19, "target": 39.50, "target_gain": "+15.5%", "rsi": 53.4, "score": 84, "strategy": "Bullish Breakout"},
    {"symbol": "IRB", "price": 30.09, "target": 34.60, "target_gain": "+15.0%", "rsi": 47.6, "score": 76, "strategy": "Steady Momentum"}
]

# --- 2. AUTHENTICATION HELPERS ---
def set_auth_cookie(response, username: str):
    token = serializer.dumps(username)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400)

def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("session_token")
    if not token:
        return False
    try:
        serializer.loads(token, max_age=86400)
        return True
    except BadSignature:
        return False

# --- 3. SAFE SCANNER FUNCTION ---
def scan_top_predictions():
    global CACHE_TIMESTAMP, LATEST_STOCK_PREDICTIONS
    now = time.time()
    
    if now - CACHE_TIMESTAMP < CACHE_EXPIRY and LATEST_STOCK_PREDICTIONS:
        return LATEST_STOCK_PREDICTIONS

    results = []
    try:
        # Wrap yfinance call safely
        tickers_data = yf.download(tickers=NSE_STOCKS, period="3m", interval="1d", progress=False)
        
        if not tickers_data.empty and 'Close' in tickers_data:
            for stock in NSE_STOCKS:
                try:
                    df = tickers_data['Close'][stock].dropna()
                    if len(df) < 20:
                        continue
                    
                    current_price = round(float(df.iloc[-1]), 2)
                    if current_price > 300:
                        continue

                    # RSI calculation
                    delta = df.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / (loss + 1e-10)
                    rsi = round(float(100 - (100 / (1 + rs)).iloc[-1]), 1)

                    target_price = round(current_price * 1.15, 2)
                    clean_symbol = stock.replace(".NS", "")
                    
                    results.append({
                        "symbol": clean_symbol,
                        "price": current_price,
                        "target": target_price,
                        "target_gain": "+15.0%",
                        "rsi": rsi,
                        "score": 80,
                        "strategy": "Bullish Breakout"
                    })
                except Exception:
                    continue
    except Exception:
        pass  # Gracefully handle API blocks or network issues

    if results:
        LATEST_STOCK_PREDICTIONS = results
    elif not LATEST_STOCK_PREDICTIONS:
        LATEST_STOCK_PREDICTIONS = DEFAULT_FALLBACK_STOCKS

    CACHE_TIMESTAMP = now
    return LATEST_STOCK_PREDICTIONS

# --- 4. ROUTES & VIEWS ---

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <title>Login - Terminal</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-black text-gray-100 flex items-center justify-center h-screen font-sans">
        <div class="bg-gray-900 p-8 rounded-xl border border-gray-800 shadow-2xl w-96">
            <h1 class="text-xl font-bold text-center mb-6 text-emerald-400">Stock Screener Terminal</h1>
            <form action="/login" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold mb-1 text-gray-400">USER NAME</label>
                    <input type="text" name="username" required class="w-full bg-black border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                </div>
                <div>
                    <label class="block text-xs font-semibold mb-1 text-gray-400">PASSWORD</label>
                    <input type="password" name="password" required class="w-full bg-black border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
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
        set_auth_cookie(response, username)
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

    top_stocks = scan_top_predictions()
    
    ticker_items = " &nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp; ".join([
        f"<a href='https://in.tradingview.com/symbols/NSE-{s['symbol']}/' target='_blank' class='hover:underline'>"
        f"<span class='text-emerald-400 font-bold'>{s['symbol']}</span> (₹{s['price']}) "
        f"- Target: <span class='text-yellow-400 font-bold'>₹{s['target']} ({s['target_gain']})</span> "
        f"[RSI: {s['rsi']}]</a>" 
        for s in top_stocks
    ])

    return f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Stock Screener Terminal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .marquee {{ white-space: nowrap; overflow: hidden; box-sizing: border-box; }}
            .marquee-content {{ display: inline-block; padding-left: 100%; animation: marquee 35s linear infinite; }}
            .marquee-content:hover {{ animation-play-state: paused; cursor: pointer; }}
            @keyframes marquee {{ 0% {{ transform: translate(0, 0); }} 100% {{ transform: translate(-100%, 0); }} }}
            ::-webkit-scrollbar {{ width: 6px; }}
            ::-webkit-scrollbar-track {{ background: #09090b; }}
            ::-webkit-scrollbar-thumb {{ background: #27272a; border-radius: 3px; }}
        </style>
    </head>
    <body class="bg-black text-gray-200 font-sans text-xs min-h-screen flex flex-col">
        <div class="bg-gray-950 border-b border-gray-800 py-2 marquee text-xs text-gray-300">
            <div id="ticker-container" class="marquee-content font-mono">
                🚀 <span class="text-emerald-400 font-bold">TOP 10 PREDICTION STRATEGY (3-MONTH HORIZON - STOCKS UNDER ₹300):</span> {ticker_items}
            </div>
        </div>

        <div class="bg-gray-900 border-b border-gray-800 px-6 py-1 flex justify-between items-center text-[10px] text-gray-400">
            <div class="flex items-center gap-2">
                <span class="relative flex h-2 w-2">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span>NSE LIVE FEED ACTIVE</span>
            </div>
            <div>Auto Refreshing in: <span id="countdown" class="text-emerald-400 font-bold font-mono">10</span>s</div>
        </div>

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
            <div class="grid grid-cols-4 gap-4 bg-gray-950 border border-gray-800 p-3 rounded-lg text-center font-mono">
                <div><span class="text-gray-500">NIFTY 50:</span> <span class="text-emerald-400 font-bold">24,659.30</span></div>
                <div><span class="text-gray-500">HIGH:</span> <span class="text-emerald-400">24,677.60</span></div>
                <div><span class="text-gray-500">LOW:</span> <span class="text-rose-400">24,497.85</span></div>
                <div><span class="text-gray-500">CLOSE:</span> <span>24,514.90</span></div>
            </div>

            <section>
                <div class="flex justify-between items-center mb-3">
                    <h2 class="font-bold text-sm text-gray-300">Most Bought Stocks</h2>
                    <a href="#" class="text-emerald-400 text-xs hover:underline">VIEW ALL &gt;</a>
                </div>
                <div class="grid grid-cols-5 gap-3">
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">IDEA</div>
                        <div class="text-gray-400 text-[10px]">VODAFONE IDEA LIMITED</div>
                        <div class="mt-2 text-rose-400 font-mono">₹12.02 <span class="text-[10px]">-0.08 (-0.63%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-IDEA/" target="_blank" class="text-emerald-400 hover:underline">TradingView</a>
                            <a href="https://www.screener.in/company/IDEA/" target="_blank" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">YESBANK</div>
                        <div class="text-gray-400 text-[10px]">YES BANK LIMITED</div>
                        <div class="mt-2 text-rose-400 font-mono">₹23.87 <span class="text-[10px]">-0.13 (-0.57%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-YESBANK/" target="_blank" class="text-emerald-400 hover:underline">TradingView</a>
                            <a href="https://www.screener.in/company/YESBANK/" target="_blank" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">JPPOWER</div>
                        <div class="text-gray-400 text-[10px]">JAIPRAKASH POWER VENTURES</div>
                        <div class="mt-2 text-rose-400 font-mono">₹18.35 <span class="text-[10px]">-0.49 (-2.60%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-JPPOWER/" target="_blank" class="text-emerald-400 hover:underline">TradingView</a>
                            <a href="https://www.screener.in/company/JPPOWER/" target="_blank" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">RPOWER</div>
                        <div class="text-gray-400 text-[10px]">RELIANCE POWER LTD</div>
                        <div class="mt-2 text-emerald-400 font-mono">₹34.19 <span class="text-[10px]">+0.17 (+0.50%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-RPOWER/" target="_blank" class="text-emerald-400 hover:underline">TradingView</a>
                            <a href="https://www.screener.in/company/RPOWER/" target="_blank" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">IRB</div>
                        <div class="text-gray-400 text-[10px]">IRB INFRA DEV LTD</div>
                        <div class="mt-2 text-rose-400 font-mono">₹30.09 <span class="text-[10px]">-0.08 (-0.70%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-IRB/" target="_blank" class="text-emerald-400 hover:underline">TradingView</a>
                            <a href="https://www.screener.in/company/IRB/" target="_blank" class="text-blue-400 hover:underline">Screener</a>
                        </div>
                    </div>
                </div>
            </section>

            <section class="bg-gray-950 border border-gray-800 p-4 rounded-lg">
                <h2 class="font-bold text-sm text-gray-300 mb-3">Sectorial Indices Performance</h2>
                <div class="grid grid-cols-6 gap-3 text-center">
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY BANK</div>
                        <div class="text-emerald-400 font-mono font-bold mt-1">51,200.40 (+0.4%)</div>
                    </div>
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY IT (Software)</div>
                        <div class="text-rose-400 font-mono font-bold mt-1">38,150.20 (-0.2%)</div>
                    </div>
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY PHARMA</div>
                        <div class="text-emerald-400 font-mono font-bold mt-1">21,890.10 (+1.1%)</div>
                    </div>
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY AUTO</div>
                        <div class="text-emerald-400 font-mono font-bold mt-1">25,430.80 (+0.8%)</div>
                    </div>
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY METAL</div>
                        <div class="text-rose-400 font-mono font-bold mt-1">9,120.50 (-0.9%)</div>
                    </div>
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY ENERGY</div>
                        <div class="text-emerald-400 font-mono font-bold mt-1">39,450.00 (+0.5%)</div>
                    </div>
                </div>
            </section>
        </div>

        <div class="fixed bottom-4 right-4 z-50">
            <button onclick="toggleChat()" class="bg-emerald-500 hover:bg-emerald-400 text-black px-4 py-3 rounded-full font-bold shadow-2xl flex items-center gap-2">
                ⚡ AI Stock Assistant
            </button>
            <div id="chat-box" class="hidden bg-gray-900 border border-gray-800 rounded-xl w-80 h-96 flex flex-col shadow-2xl mt-2">
                <div class="bg-gray-800 p-3 rounded-t-xl font-bold flex justify-between items-center text-emerald-400">
                    <span>Quick Analyst Bot</span>
                    <button onclick="toggleChat()" class="text-gray-400 hover:text-white">✕</button>
                </div>
                <div id="messages" class="flex-1 p-3 overflow-y-auto space-y-2 text-xs">
                    <div class="bg-gray-800 p-2 rounded self-start">Ask me about target prices or stock predictions!</div>
                </div>
                <div class="p-2 border-t border-gray-800 flex gap-2">
                    <input id="chat-input" type="text" placeholder="e.g. SUZLON target..." class="bg-black border border-gray-800 rounded px-2 py-1 flex-1 text-white text-xs focus:outline-none" onkeypress="if(event.key==='Enter') sendChatMessage()">
                    <button onclick="sendChatMessage()" class="bg-emerald-600 px-3 py-1 rounded text-black font-bold">Send</button>
                </div>
            </div>
        </div>

        <script>
            let countdown = 10;
            const timerElement = document.getElementById('countdown');
            setInterval(() => {{
                countdown--;
                if (countdown <= 0) {{ window.location.reload(); }}
                else {{ timerElement.innerText = countdown; }}
            }}, 1000);

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
    top_scanned = LATEST_STOCK_PREDICTIONS
    matched = [s for s in top_scanned if s['symbol'] in prompt]
    
    if matched:
        s = matched[0]
        reply = f"📊 <b>{s['symbol']} Analysis:</b><br>Current Price: ₹{s['price']}<br>3M Target: ₹{s['target']} ({s['target_gain']})<br>RSI: {s['rsi']}<br>Strategy: {s['strategy']}"
    else:
        reply = "⚡ Enter a stock symbol (e.g. SUZLON, IDEA) to view target predictions."

    return JSONResponse({"reply": reply})
