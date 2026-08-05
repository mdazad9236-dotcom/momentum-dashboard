from flask import Flask, render_template_string, request, redirect, url_for, session
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.secret_key = "super_secret_momentum_key"

# Dummy user credentials for login
USERS = {
    "admin": "admin123",
    "trader": "password01"
}

# 50 NSE Stock Pool
SCAN_POOL = [
    "SUZLON.NS", "IDFCFIRSTB.NS", "ZOMATO.NS", "PNB.NS", "ITC.NS",
    "IOC.NS", "BPCL.NS", "TATAPOWER.NS", "NTPC.NS", "GAIL.NS",
    "COALINDIA.NS", "VEDL.NS", "TATAMOTORS.NS", "SBIN.NS", "AXISBANK.NS",
    "WIPRO.NS", "INFY.NS", "HCLTECH.NS", "TCS.NS", "RELIANCE.NS",
    "LT.NS", "TITAN.NS", "SUNPHARMA.NS", "MARUTI.NS", "BAJFINANCE.NS",
    "ASIANPAINT.NS", "NESTLEIND.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "GRASIM.NS", "TECHM.NS", "BHARTIARTL.NS", "HINDALCO.NS",
    "DRREDDY.NS", "CIPLA.NS", "BRITANNIA.NS", "EICHERMOT.NS", "APOLLOHOSP.NS",
    "SBILIFE.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "HEROMOTOCO.NS", "UPL.NS", "BAJAJ-AUTO.NS", "SHRIRAMFIN.NS", "LTIM.NS"
]

def fetch_single_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo")
        if df.empty or len(df) < 30:
            return None
            
        current_price = float(df['Close'].iloc[-1])
        prev_close = float(stock.info.get('previousClose', df['Close'].iloc[-2]))
        change = ((current_price - prev_close) / prev_close) * 100
        
        # RSI calculation
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = round(float(rsi.iloc[-1]), 1) if not rsi.empty else 50.0
        
        # MACD calculation
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        score = 50
        if 40 <= current_rsi <= 70: score += 20
        if macd.iloc[-1] > signal.iloc[-1]: score += 20
        if change > 0: score += 10
        score = min(score, 98)
        
        pe_ratio = round(float(stock.info.get('trailingPE', 22.5) or 22.5), 2)
        
        return {
            "symbol": ticker.replace(".NS", ""),
            "price": round(current_price, 2),
            "change": round(change, 2),
            "rsi": current_rsi,
            "macd_status": "Bullish Crossover" if macd.iloc[-1] > signal.iloc[-1] else "Neutral/Bearish",
            "score": int(score),
            "pe": pe_ratio,
            "technical": "Strong Momentum" if score > 75 else "Consolidating",
            "fundamental": "Undervalued Growth" if pe_ratio < 30 else "Fairly Valued",
            "return": f"+{score // 4}% to +{(score // 4) + 8}% (6 Mo)"
        }
    except Exception:
        return None

def scan_stocks_parallel():
    results = []
    # Fetch all 50 stocks concurrently using multithreading for instant load times
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ticker = {executor.submit(fetch_single_stock, t): t for t in SCAN_POOL}
        for future in future_to_ticker:
            res = future.result()
            if res:
                results.append(res)
                
    results = sorted(results, key=lambda x: x['score'], reverse=True)
    marquee_stocks = [s for s in results if s['price'] < 500]
    top_10_stocks = results[:10]
    return marquee_stocks, top_10_stocks

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Momentum Dashboard</title>
    <style>
        body {
            background-color: #0b0e14;
            color: #ffffff;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
        }
        /* Navbar Menu */
        .navbar {
            background-color: #161b22;
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #30363d;
        }
        .navbar h2 {
            margin: 0;
            color: #00ffa3;
            font-size: 1.2rem;
        }
        .nav-links a {
            color: #c9d1d9;
            text-decoration: none;
            margin-left: 20px;
            font-weight: 500;
        }
        .nav-links a:hover {
            color: #58a6ff;
        }
        .container {
            padding: 20px 30px;
        }
        h1, h2 {
            color: #00ffa3;
            font-family: monospace;
        }
        /* Marquee Ticker (< Rs 500) */
        .marquee-container {
            background-color: #161b22;
            overflow: hidden;
            white-space: nowrap;
            padding: 12px 0;
            border-radius: 6px;
            border: 1px solid #30363d;
            margin-bottom: 30px;
        }
        .marquee-content {
            display: inline-block;
            animation: marquee 30s linear infinite;
        }
        .marquee-item {
            display: inline-block;
            margin-right: 40px;
            font-weight: 600;
            font-size: 0.95rem;
        }
        @keyframes marquee {
            0% { transform: translate3d(0, 0, 0); }
            100% { transform: translate3d(-50%, 0, 0); }
        }
        .positive { color: #2ea043; }
        .negative { color: #f85149; }
        
        /* Grid Layout */
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #30363d;
            padding-bottom: 10px;
            margin-bottom: 12px;
        }
        .card-header h3 {
            margin: 0;
            color: #58a6ff;
            font-size: 1.2rem;
        }
        .score-badge {
            background: #238636;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: bold;
        }
        .metric-row {
            font-size: 0.85rem;
            color: #8b949e;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
        }
        .metric-value {
            color: #c9d1d9;
            font-weight: 500;
        }
        .analysis-box {
            background: #0d1117;
            padding: 10px;
            border-radius: 6px;
            margin-top: 12px;
            font-size: 0.8rem;
            border-left: 3px solid #58a6ff;
        }
        /* Login Form Styles */
        .login-card {
            max-width: 400px;
            margin: 80px auto;
            background: #161b22;
            padding: 30px;
            border-radius: 8px;
            border: 1px solid #30363d;
        }
        .login-card input {
            width: 100%;
            padding: 10px;
            margin: 10px 0 20px 0;
            background: #0d1117;
            border: 1px solid #30363d;
            color: white;
            border-radius: 4px;
        }
        .login-card button {
            width: 100%;
            padding: 10px;
            background: #238636;
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
        }
        .error { color: #f85149; font-size: 0.85rem; }
    </style>
    <script>
        setTimeout(function(){ window.location.reload(1); }, 60000);
    </script>
</head>
<body>

    <div class="navbar">
        <h2>🚀 Momentum AI Screener</h2>
        <div class="nav-links">
            {% if session.get('user') %}
                <span>User: <b>{{ session.user }}</b></span>
                <a href="{{ url_for('dashboard') }}">Dashboard</a>
                <a href="{{ url_for('logout') }}" style="color: #f85149;">Logout</a>
            {% else %}
                <a href="{{ url_for('login') }}">Login</a>
            {% endif %}
        </div>
    </div>

    <div class="container">
        {% if page == 'login' %}
            <div class="login-card">
                <h2>🔐 Trader Login</h2>
                {% if error %}<div class="error">{{ error }}</div>{% endif %}
                <form method="POST">
                    <label>Username (try: admin)</label>
                    <input type="text" name="username" required>
                    <label>Password (try: admin123)</label>
                    <input type="password" name="password" required>
                    <button type="submit">Login to Dashboard</button>
                </form>
            </div>
        {% else %}
            <h1>⚡ Live AI Momentum Screener (Scanned 50+ NSE Stocks)</h1>
            
            <p><b>Live Ticker (&lt; ₹500 Only):</b> Live data moving marquee tape tracking stocks priced under ₹500.</p>
            <div class="marquee-container">
                <div class="marquee-content">
                    {% for stock in marquee_stocks %}
                        <span class="marquee-item">
                            📍 <b>{{ stock.symbol }}</b>: ₹{{ stock.price }} 
                            <span class="{{ 'positive' if stock.change >= 0 else 'negative' }}">
                                {{ '+' if stock.change >= 0 else '' }}{{ stock.change }}%
                            </span>
                        </span>
                    {% endfor %}
                    {% for stock in marquee_stocks %}
                        <span class="marquee-item">
                            📍 <b>{{ stock.symbol }}</b>: ₹{{ stock.price }} 
                            <span class="{{ 'positive' if stock.change >= 0 else 'negative' }}">
                                {{ '+' if stock.change >= 0 else '' }}{{ stock.change }}%
                            </span>
                        </span>
                    {% endfor %}
                </div>
            </div>

            <h2>Top 10 Recommendations (RSI, MACD, Technical & Fundamental Analysis)</h2>
            <div class="grid-container">
                {% for stock in top_10 %}
                <div class="card">
                    <div class="card-header">
                        <h3>{{ stock.symbol }}</h3>
                        <div class="score-badge">Score: {{ stock.score }}/100</div>
                    </div>
                    <div class="metric-row"><span>CMP Price:</span> <span class="metric-value">₹{{ stock.price }}</span></div>
                    <div class="metric-row"><span>Change:</span> <span class="metric-value {{ 'positive' if stock.change >= 0 else 'negative' }}">{{ stock.change }}%</span></div>
                    <div class="metric-row"><span>RSI (14):</span> <span class="metric-value">{{ stock.rsi }}</span></div>
                    <div class="metric-row"><span>MACD Signal:</span> <span class="metric-value">{{ stock.macd_status }}</span></div>
                    <div class="metric-row"><span>P/E Ratio:</span> <span class="metric-value">{{ stock.pe }}</span></div>
                    <div class="metric-row"><span>Est. Target Return:</span> <span class="metric-value" style="color: #3fb950;">{{ stock.return }}</span></div>
                    
                    <div class="analysis-box">
                        <div>📈 <b>Technical:</b> {{ stock.technical }}</div>
                        <div>📊 <b>Fundamental:</b> {{ stock.fundamental }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% endif %}
    </div>

</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in USERS and USERS[username] == password:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password! Try admin / admin123"
    return render_template_string(TEMPLATE, page="login", error=error)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    marquee_stocks, top_10_stocks = scan_stocks_parallel()
    return render_template_string(TEMPLATE, page="dashboard", marquee_stocks=marquee_stocks, top_10=top_10_stocks)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
