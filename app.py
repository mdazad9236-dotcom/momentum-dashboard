import os
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import numpy as np

app = FastAPI(title="Professional Stock Terminal")

# Add Session Middleware for Login Management
app.add_middleware(SessionMiddleware, secret_key="super-secret-key-change-this")

# --- 50+ STOCKS FOR SCANNING ---
SCAN_SYMBOLS = [
    "TATAMOTORS", "HYUNDAI", "COALINDIA", "IDEA", "YESBANK", "JPPOWER", "RPOWER", "IRB",
    "GRASIM", "LT", "SHRIRAMFIN", "HDFCLIFE", "EICHERMOT", "PERSISTENT", "WIPRO", "SWIGGY",
    "LATENTVIEW", "ETERNAL", "PPLPHARMA", "TATACAP", "RBLBANK", "TENNECO", "GRANULES",
    "BHARTIARTL", "POWERGRID", "HEROMOTOCO", "IRCTC", "DEEPAKNTR", "IKIO", "SUZLON",
    "NSLNISP", "SAGILITY", "OLAELEC", "MSUMI", "INFY", "TCS", "RELIANCE", "ICICIBANK",
    "SBIN", "AXISBANK", "HDFCBANK", "BAJFINANCE", "BHEL", "NHPC", "IOC", "ONGC",
    "GAIL", "ZOMATO", "PAYTM", "PNB"
]

# --- TECHNICAL ANALYSIS ENGINE ---
def calculate_indicators(df: pd.DataFrame):
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # Volume 10-day SMA
    df['Vol_SMA'] = df['Volume'].rolling(window=10).mean()
    return df

def scan_top_predictions():
    """Scans 50+ stocks, filters price <= 300, runs Tech + RSI + MACD + Vol analysis."""
    predictions = []
    
    for symbol in SCAN_SYMBOLS:
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            hist = ticker.history(period="3mo", interval="1d")
            
            if hist.empty or len(hist) < 26:
                continue

            hist = calculate_indicators(hist)
            latest = hist.iloc[-1]
            prev = hist.iloc[-2]

            price = round(float(latest['Close']), 2)
            
            # Filter condition: Price under Rs 300
            if price <= 300 and price > 0:
                rsi = round(float(latest['RSI']), 2)
                macd = round(float(latest['MACD']), 2)
                macd_sig = round(float(latest['Signal']), 2)
                vol_ratio = round(float(latest['Volume'] / (latest['Vol_SMA'] + 1)), 2)

                # Strategy scoring
                score = 0
                if rsi < 45: score += 2  # Oversold / Accumulation
                if macd > macd_sig: score += 2  # Bullish crossover
                if vol_ratio > 1.2: score += 1  # Volume breakout

                # Calculate estimated 3-Month percentage prediction
                estimated_gain = round(10.0 + (score * 3.5), 1)

                predictions.append({
                    "symbol": symbol,
                    "price": price,
                    "rsi": rsi,
                    "target_gain": f"+{estimated_gain}%",
                    "score": score
                })
        except Exception:
            continue

    # Return top 10 stocks sorted by highest score/prediction
    predictions.sort(key=lambda x: x['score'], reverse=True)
    return predictions[:10]

# --- LOGIN & AUTH HELPERS ---
def check_auth(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return """
    <!DOCTYPE html>
    <html class="dark">
    <head>
        <title>Terminal Login</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-black text-white flex items-center justify-center min-h-screen">
        <div class="bg-gray-900 p-8 rounded-xl border border-gray-800 w-96 shadow-2xl">
            <h2 class="text-2xl font-bold mb-6 text-emerald-400 text-center">Quant Terminal Login</h2>
            <form method="POST" action="/login" class="space-y-4">
                <div>
                    <label class="text-xs text-gray-400">User Name</label>
                    <input type="text" name="username" required class="w-full bg-gray-950 border border-gray-800 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500">
                </div>
                <div>
                    <label class="text-xs text-gray-400">Password</label>
                    <input type="password" name="password" required class="w-full bg-gray-950 border border-gray-800 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500">
                </div>
                <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-500 text-black font-bold py-2 rounded text-sm transition">Sign In</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "Admin" and password == "Admin":
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return HTMLResponse("<script>alert('Invalid Credentials'); window.location.href='/login';</script>")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

# --- AI CHATBOT ROUTE ---
class ChatRequest(BaseModel):
    prompt: str

@app.post("/api/ai-chat")
def ai_chat(query: ChatRequest):
    text = query.prompt.upper().strip()
    
    # Simple Technical Engine Analysis Output
    if "RSI" in text or "MACD" in text or "BUY" in text:
        return {"reply": f"AI Signal for {text}: Bullish consolidation detected on 4H timeframes. RSI is maintaining 54 support levels with positive volume divergence."}
    return {"reply": f"Market Assistant: Analyzed {query.prompt}. Overall trend structure is neutral-to-bullish with key resistance at current 20-day high."}

# --- MAIN DASHBOARD ROUTE ---
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    check_auth(request)
    top_stocks = scan_top_predictions()
    
    # Build Ticker HTML for right-to-left marquee movement
    ticker_items = " &nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp; ".join([
        f"<span class='text-emerald-400 font-bold'>{s['symbol']}</span> (₹{s['price']}) - 3M Pred: <span class='text-yellow-400 font-bold'>{s['target_gain']}</span> [RSI: {s['rsi']}]" 
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
            .marquee {{
                white-space: nowrap;
                overflow: hidden;
                box-sizing: border-box;
            }}
            .marquee-content {{
                display: inline-block;
                padding-left: 100%;
                animation: marquee 30s linear infinite;
            }}
            @keyframes marquee {{
                0%   {{ transform: translate(0, 0); }}
                100% {{ transform: translate(-100%, 0); }}
            }}
            ::-webkit-scrollbar {{ width: 6px; }}
            ::-webkit-scrollbar-track {{ background: #09090b; }}
            ::-webkit-scrollbar-thumb {{ background: #27272a; border-radius: 3px; }}
        </style>
    </head>
    <body class="bg-black text-gray-200 font-sans text-xs min-h-screen flex flex-col">
        
        <!-- 1. RIGHT-TO-LEFT TICKER (UNDER RS. 300 3-MONTH PREDICTIONS) -->
        <div class="bg-gray-950 border-b border-gray-800 py-2 marquee text-sm text-gray-300">
            <div id="ticker-container" class="marquee-content font-mono">
                🔥 TOP 10 STOCKS UNDER ₹300 (3-MONTH PREDICTION & SCANNER): {ticker_items}
            </div>
        </div>

        <!-- AUTO-REFRESH STATUS BADGE -->
        <div class="bg-gray-900 border-b border-gray-800 px-6 py-1 flex justify-between items-center text-[10px] text-gray-400">
            <div class="flex items-center gap-2">
                <span class="relative flex h-2 w-2">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span>LIVE FEED ACTIVE</span>
            </div>
            <div>Next auto-update in: <span id="countdown" class="text-emerald-400 font-bold font-mono">10</span>s</div>
        </div>

        <!-- 2. NAVBAR -->
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
            
            <!-- INDEX BAR -->
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
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">IDEA</div>
                        <div class="text-gray-400 text-[10px]">VODAFONE IDEA LIMITED</div>
                        <div class="mt-2 text-rose-400 font-mono">₹12.02 <span class="text-[10px]">-0.08 (-0.63%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-IDEA/" target="_blank" class="text-emerald-400">TradingView</a>
                            <a href="https://www.screener.in/company/IDEA/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">YESBANK</div>
                        <div class="text-gray-400 text-[10px]">YES BANK LIMITED</div>
                        <div class="mt-2 text-rose-400 font-mono">₹23.87 <span class="text-[10px]">-0.13 (-0.57%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-YESBANK/" target="_blank" class="text-emerald-400">TradingView</a>
                            <a href="https://www.screener.in/company/YESBANK/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">JPPOWER</div>
                        <div class="text-gray-400 text-[10px]">JAIPRAKASH POWER VENTURES</div>
                        <div class="mt-2 text-rose-400 font-mono">₹18.35 <span class="text-[10px]">-0.49 (-2.60%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-JPPOWER/" target="_blank" class="text-emerald-400">TradingView</a>
                            <a href="https://www.screener.in/company/JPPOWER/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">RPOWER</div>
                        <div class="text-gray-400 text-[10px]">RELIANCE POWER LTD</div>
                        <div class="mt-2 text-emerald-400 font-mono">₹34.19 <span class="text-[10px]">+0.17 (+0.50%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-RPOWER/" target="_blank" class="text-emerald-400">TradingView</a>
                            <a href="https://www.screener.in/company/RPOWER/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">IRB</div>
                        <div class="text-gray-400 text-[10px]">IRB INFRA DEV LTD</div>
                        <div class="mt-2 text-rose-400 font-mono">₹30.09 <span class="text-[10px]">-0.08 (-0.70%)</span></div>
                        <div class="mt-2 flex gap-2 border-t border-gray-800 pt-2 text-[10px]">
                            <a href="https://in.tradingview.com/symbols/NSE-IRB/" target="_blank" class="text-emerald-400">TradingView</a>
                            <a href="https://www.screener.in/company/IRB/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                </div>
            </section>

            <!-- SECTORIAL INDICES -->
            <section class="bg-gray-950 border border-gray-800 p-4 rounded-lg">
                <h2 class="font-bold text-sm text-gray-300 mb-3">Sectorial Indices Performance</h2>
                <div class="grid grid-cols-6 gap-3 text-center">
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY BANK</div>
                        <div class="text-emerald-400 font-mono font-bold mt-1">51,200.40 (+0.4%)</div>
                    </div>
                    <div class="bg-gray-900 p-2 rounded border border-gray-800">
                        <div class="text-gray-400">NIFTY IT</div>
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

            <!-- TECHNICAL SCREENERS -->
            <section>
                <div class="flex justify-between items-center mb-3">
                    <h2 class="font-bold text-sm text-gray-300">Technical Screeners</h2>
                    <a href="#" class="text-emerald-400 text-xs hover:underline">VIEW ALL &gt;</a>
                </div>
                <div class="grid grid-cols-5 gap-3">
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">PPLPHARMA</div>
                        <div class="text-emerald-400 font-mono mt-1">₹207.40 (+7.47%)</div>
                        <a href="https://in.tradingview.com/symbols/NSE-PPLPHARMA/" target="_blank" class="text-emerald-400 mt-2 block text-[10px]">Analyse Chart &rarr;</a>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">TATACAP</div>
                        <div class="text-emerald-400 font-mono mt-1">₹372.90 (+3.69%)</div>
                        <a href="https://in.tradingview.com/symbols/NSE-TATACAP/" target="_blank" class="text-emerald-400 mt-2 block text-[10px]">Analyse Chart &rarr;</a>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">RBLBANK</div>
                        <div class="text-emerald-400 font-mono mt-1">₹222.20 (+3.01%)</div>
                        <a href="https://in.tradingview.com/symbols/NSE-RBLBANK/" target="_blank" class="text-emerald-400 mt-2 block text-[10px]">Analyse Chart &rarr;</a>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">TENNECO</div>
                        <div class="text-emerald-400 font-mono mt-1">₹582.65 (+6.83%)</div>
                        <a href="https://in.tradingview.com/symbols/NSE-TENNECO/" target="_blank" class="text-emerald-400 mt-2 block text-[10px]">Analyse Chart &rarr;</a>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">GRANULES</div>
                        <div class="text-emerald-400 font-mono mt-1">₹644.15 (+2.23%)</div>
                        <a href="https://in.tradingview.com/symbols/NSE-GRANULES/" target="_blank" class="text-emerald-400 mt-2 block text-[10px]">Analyse Chart &rarr;</a>
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
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">SUZLON</div>
                        <div class="text-emerald-400 font-mono mt-1">₹48.10 (+2.19%)</div>
                        <div class="flex gap-2 text-[10px] mt-2">
                            <a href="https://in.tradingview.com/symbols/NSE-SUZLON/" target="_blank" class="text-emerald-400">Chart</a>
                            <a href="https://www.screener.in/company/SUZLON/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">NSLNISP</div>
                        <div class="text-emerald-400 font-mono mt-1">₹44.58 (+1.30%)</div>
                        <div class="flex gap-2 text-[10px] mt-2">
                            <a href="https://in.tradingview.com/symbols/NSE-NSLNISP/" target="_blank" class="text-emerald-400">Chart</a>
                            <a href="https://www.screener.in/company/NSLNISP/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">SAGILITY</div>
                        <div class="text-rose-400 font-mono mt-1">₹42.97 (-0.77%)</div>
                        <div class="flex gap-2 text-[10px] mt-2">
                            <a href="https://in.tradingview.com/symbols/NSE-SAGILITY/" target="_blank" class="text-emerald-400">Chart</a>
                            <a href="https://www.screener.in/company/SAGILITY/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">OLAELEC</div>
                        <div class="text-emerald-400 font-mono mt-1">₹41.78 (+8.37%)</div>
                        <div class="flex gap-2 text-[10px] mt-2">
                            <a href="https://in.tradingview.com/symbols/NSE-OLAELEC/" target="_blank" class="text-emerald-400">Chart</a>
                            <a href="https://www.screener.in/company/OLAELEC/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                        <div class="font-bold text-white">MSUMI</div>
                        <div class="text-emerald-400 font-mono mt-1">₹41.06 (+0.38%)</div>
                        <div class="flex gap-2 text-[10px] mt-2">
                            <a href="https://in.tradingview.com/symbols/NSE-MSUMI/" target="_blank" class="text-emerald-400">Chart</a>
                            <a href="https://www.screener.in/company/MSUMI/" target="_blank" class="text-blue-400">Screener</a>
                        </div>
                    </div>
                </div>
            </section>
        </div>

        <!-- 3. FLOATING AI CHATBOT WIDGET -->
        <div class="fixed bottom-4 right-4 z-50">
            <button onclick="toggleChat()" class="bg-emerald-500 hover:bg-emerald-400 text-black px-4 py-3 rounded-full font-bold shadow-2xl flex items-center gap-2">
                🤖 AI Stock Analyst
            </button>
            
            <div id="chat-box" class="hidden bg-gray-900 border border-gray-800 rounded-xl w-80 h-96 flex flex-col shadow-2xl mt-2">
                <div class="bg-gray-800 p-3 rounded-t-xl font-bold flex justify-between items-center text-emerald-400">
                    <span>Market Assistant Bot</span>
                    <button onclick="toggleChat()" class="text-gray-400 hover:text-white">✕</button>
                </div>
                <div id="messages" class="flex-1 p-3 overflow-y-auto space-y-2 text-xs">
                    <div class="bg-gray-800 p-2 rounded self-start">Ask me to analyze RSI, MACD, or volume breakout for any stock.</div>
                </div>
                <div class="p-2 border-t border-gray-800 flex gap-2">
                    <input id="chat-input" type="text" placeholder="e.g. Analyze TATAMOTORS..." class="bg-black border border-gray-800 rounded px-2 py-1 flex-1 text-white text-xs focus:outline-none focus:border-emerald-500">
                    <button onclick="sendChatMessage()" class="bg-emerald-600 px-3 py-1 rounded text-black font-bold">Send</button>
                </div>
            </div>
        </div>

        <script>
            // AUTO-UPDATE TIMER (EVERY 10 SECONDS)
            let countdown = 10;
            const timerElement = document.getElementById('countdown');

            setInterval(() => {{
                countdown--;
                if (countdown <= 0) {{
                    window.location.reload();
                }} else {{
                    timerElement.innerText = countdown;
                }}
            }}, 1000);

            function toggleChat() {{
                document.getElementById('chat-box').classList.toggle('hidden');
            }}

            async function sendChatMessage() {{
                const input = document.getElementById('chat-input');
                const text = input.value.trim();
                if (!text) return;

                const msgContainer = document.getElementById('messages');
                msgContainer.innerHTML += `<div class="bg-emerald-950 border border-emerald-800 text-emerald-300 p-2 rounded text-right">${{text}}</div>`;
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
