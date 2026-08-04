from flask import Flask, render_template_string
import yfinance as yf
import pandas as pd
from datetime import datetime

app = Flask(__name__)

NIFTY_50 = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICIBANK.NS","BHARTIARTL.NS", "SBIN.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS","AXISBANK.NS", "HCLTECH.NS", "ASIANPAINT.NS", "MARUTI.NS", "BAJFINANCE.NS","ADANIPORTS.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "NESTLEIND.NS","WIPRO.NS", "ONGC.NS", "POWERGRID.NS", "NTPC.NS", "JSWSTEEL.NS"]

def get_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs.iloc[-1]))

def get_momentum_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3mo")
        if len(hist) < 20: return None
        current_price = hist['Close'].iloc[-1]
        price_1m_ago = hist['Close'].iloc[-21] if len(hist) >= 21 else hist['Close'].iloc[0]
        low_3m = hist['Low'].min()
        momentum_1m = ((current_price - price_1m_ago) / price_1m_ago) * 100
        from_low = ((current_price - low_3m) / low_3m) * 100
        rsi = get_rsi(hist)
        score = (momentum_1m * 0.5) + (from_low * 0.3) + ((rsi-30) * 0.2)
        return {"symbol": symbol.replace(".NS",""), "price": round(current_price,2), "momentum_1m": round(momentum_1m,2), "from_low": round(from_low,2), "rsi": round(rsi,2), "score": round(score,2)}
    except: return None

@app.route('/')
def dashboard():
    all_data = []
    for sym in NIFTY_50:
        data = get_momentum_data(sym)
        if data: all_data.append(data)
    top_25 = sorted(all_data, key=lambda x: x['score'], reverse=True)[:25]
    html = """<head><meta http-equiv="refresh" content="300"><style>body{background:#0e1117;color:white;font-family:Arial;padding:20px;}table{width:100%;border-collapse:collapse;}th,td{padding:12px;text-align:left;border-bottom:1px solid #333;}th{background:#1a1d23;color:gold;}.top1{background:#2a2618;border-left:4px solid gold;}.score{font-weight:bold;color:#00ff88;}.timer{color:#00ff88;font-size:14px;}</style></head><body><h1>🚀 Top 25 Momentum Stocks for Next 1-2 Months</h1><p class="timer">Auto Refresh: Har 5 min me 🔄 | Last Updated: {{time}}</p><table><tr><th>Rank</th><th>Stock</th><th>Price</th><th>1M Return</th><th>From 3M Low</th><th>RSI</th><th>Score</th></tr>{% for i, s in enumerate(top_25) %}<tr class="{% if i==0 %}top1{% endif %}"><td>{{i+1}} {% if i==0 %}👑{% endif %}</td><td><b>{{s.symbol}}</b></td><td>{{s.price}}</td><td>{{s.momentum_1m}}%</td><td>{{s.from_low}}%</td><td>{{s.rsi}}</td><td class="score">{{s.score}}/100</td></tr>{% endfor %}</table></body>"""
    return render_template_string(html, top_25=top_25, enumerate=enumerate, time=datetime.now().strftime("%H:%M:%S"))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
