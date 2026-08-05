import os
import time
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature

app = FastAPI(title="Stock Screener Terminal")

SECRET_KEY = "super-secret-stock-screener-key-change-in-prod"
serializer = URLSafeTimedSerializer(SECRET_KEY)

CACHE_TIMESTAMP = 0
CACHE_EXPIRY = 10 
LATEST_STOCK_PREDICTIONS = []

NSE_STOCKS = [
    "SUZLON.NS", "NSLNISP.NS", "SAGILITY.NS", "OLAELEC.NS", "MSUMI.NS", 
    "IDEA.NS", "YESBANK.NS", "JPPOWER.NS", "RPOWER.NS", "IRB.NS"
]

DEFAULT_FALLBACK_STOCKS = [
    {"symbol": "SUZLON", "price": 48.10, "target": 55.30, "target_gain": "+15.0%", "rsi": 42.5, "score": 90, "strategy": "Bullish Breakout"},
    {"symbol": "NSLNISP", "price": 44.58, "target": 51.20, "target_gain": "+14.8%", "rsi": 46.1, "score": 85, "strategy": "Steady Momentum"},
    {"symbol": "SAGILITY", "price": 42.97, "target": 48.50, "target_gain": "+12.8%", "rsi": 38.0, "score": 80, "strategy": "Bullish Reversal"},
    {"symbol": "OLAELEC", "price": 41.78, "target": 49.00, "target_gain": "+17.2%", "rsi": 51.2, "score": 88, "strategy": "Volume Breakout"},
    {"symbol": "MSUMI", "price": 41.06, "target": 46.80, "target_gain": "+14.0%", "rsi": 44.3, "score": 75, "strategy": "Steady Momentum"}
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

def scan_top_predictions():
    global CACHE_TIMESTAMP, LATEST_STOCK_PREDICTIONS
    now = time.time()
    if now - CACHE_TIMESTAMP < CACHE_EXPIRY and LATEST_STOCK_PREDICTIONS:
        return LATEST_STOCK_PREDICTIONS
    LATEST_STOCK_PREDICTIONS = DEFAULT_FALLBACK_STOCKS
    CACHE_TIMESTAMP = now
    return LATEST_STOCK_PREDICTIONS

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head><meta charset="UTF-8"><title>Login</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-black text-gray-100 flex items-center justify-center h-screen">
        <div class="bg-gray-900 p-8 rounded-xl border border-gray-800 shadow-2xl w-96">
            <h1 class="text-xl font-bold text-center mb-6 text-emerald-400">Stock Terminal</h1>
            <form action="/login" method="POST" class="space-y-4">
                <div><label class="text-xs text-gray-400">USER NAME</label><input type="text" name="username" required class="w-full bg-black border border-gray-800 rounded p-2 text-white text-sm"></div>
                <div><label class="text-xs text-gray-400">PASSWORD</label><input type="password" name="password" required class="w-full bg-black border border-gray-800 rounded p-2 text-white text-sm"></div>
                <button type="submit" class="w-full bg-emerald-500 font-bold py-2 rounded text-black text-sm">LOGIN</button>
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
    return HTMLResponse("<script>alert('Invalid Credentials!'); window.location='/login';</script>")

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    top_stocks = scan_top_predictions()
    
    ticker_items = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join([
        f"<span class='text-emerald-400 font-bold'>{s['symbol']}</span> (₹{s['price']}) - Target: <span class='text-yellow-400 font-bold'>₹{s['target']}</span>"
        for s in top_stocks
    ])

    return f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <title>Stock Screener Terminal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <!-- TradingView Library loaded globally -->
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <style>
            .marquee {{ white-space: nowrap; overflow: hidden; }}
            .marquee-content {{ display: inline-block; padding-left: 100%; animation: marquee 35s linear infinite; }}
            .marquee-content:hover {{ animation-play-state: paused; }}
            @keyframes marquee {{ 0% {{ transform: translate(0, 0); }} 100% {{ transform: translate(-100%, 0); }} }}
        </style>
    </head>
    <body class="bg-black text-gray-200 font-sans text-xs min-h-screen">
        
        <div class="bg-gray-950 border-b border-gray-800 py-2 marquee text-xs text-gray-300">
            <div class="marquee-content font-mono">
                🚀 <span class="text-emerald-400 font-bold">TOP STOCKS:</span> {ticker_items}
            </div>
        </div>

        <div class="p-6 space-y-6 max-w-[1600px] mx-auto">
            
            <!-- LIVE TRADINGVIEW CHART CONTAINER -->
            <div class="bg-gray-900 border border-gray-800 p-4 rounded-xl">
                <h2 class="font-bold text-sm text-gray-300 mb-3">Live Interactive Chart (NSE:SUZLON)</h2>
                
                <!-- TradingView Widget BEGIN -->
                <div class="tradingview-widget-container rounded-lg overflow-hidden">
                  <div id="tradingview_chart"></div>
                  <script type="text/javascript">
                    new TradingView.widget({{
                      "width": "100%",
                      "height": 400,
                      "symbol": "NSE:SUZLON",
                      "interval": "D",
                      "timezone": "Asia/Kolkata",
                      "theme": "dark",
                      "style": "1",
                      "locale": "en",
                      "container_id": "tradingview_chart"
                    }});
                  </script>
                </div>
                <!-- TradingView Widget END -->

            </div>

            <section class="grid grid-cols-5 gap-3">
                <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                    <div class="font-bold text-white">SUZLON</div>
                    <div class="text-emerald-400 font-mono mt-1">₹48.10 (+2.19%)</div>
                </div>
                <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg">
                    <div class="font-bold text-white">YESBANK</div>
                    <div class="text-rose-400 font-mono mt-1">₹23.87 (-0.57%)</div>
                </div>
            </section>
        </div>
    </body>
    </html>
    """
