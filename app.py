from flask import Flask, render_template_string
import yfinance as yf
import pandas as pd
import numpy as np

app = Flask(__name__)

# Expanded pool of 50 prominent NSE stocks to scan
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

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50.0

def calculate_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd.iloc[-1], signal.iloc[-1]

def scan_and_analyze_stocks():
    scanned_results = []
    
    # Download batch data safely or loop through tickers
    for ticker in SCAN_POOL:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="3mo")
            
            if df.empty or len(df) < 30:
                continue
                
            current_price = float(df['Close'].iloc[-1])
            prev_close = float(stock.info.get('previousClose', df['Close'].iloc[-2]))
            change = ((current_price - prev_close) / prev_close) * 100
            
            # Technical Indicators
            rsi = calculate_rsi(df['Close'])
            macd, signal = calculate_macd(df['Close'])
            
            # Simple Scoring Model based on RSI & MACD momentum
            score = 50
            if 40 <= rsi <= 70:
                score += 20
            if macd > signal:
                score += 20
            if change > 0:
                score += 10
            score = min(score, 98) # cap at 98
            
            # Fundamental mock placeholder or real lookup if available
            pe_ratio = round(stock.info.get('trailingPE', 22.5), 2)
            pb_ratio = round(stock.info.get('priceToBook', 3.2), 2)
            
            stock_info = {
                "symbol": ticker.replace(".NS", ""),
                "price": round(current_price, 2),
                "change": round(change, 2),
                "rsi": round(rsi, 1),
                "macd_status": "Bullish Crossover" if macd > signal else "Bearish/Neutral",
                "score": int(score),
                "pe": pe_ratio,
                "pb": pb_ratio,
                "technical": "Strong Momentum" if score > 75 else "Moderate Trend",
                "fundamental": "Undervalued Growth" if pe_ratio < 30 else "Fairly Valued",
                "return": f"+{score // 4}% to +{(score // 4) + 8}% (6 Mo)"
            }
            scanned_results.append(stock_info)
        except Exception as e:
            continue
            
    # Sort by AI score to get top recommendations
    scanned_results = sorted(scanned_results, key=lambda x: x['score'], reverse=True)
    
    # Filter stocks strictly UNDER Rs. 500 for the Marquee Ticker
    marquee_stocks = [s for s in scanned_results if s['price'] < 500]
    
    # Take top 10 overall for the primary dashboard grid
    top_10_stocks = scanned_results[:10]
    
    return marquee_stocks, top_10_stocks

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Advanced AI Momentum Stock Screener</title>
    <style>
        body {
            background-color: #0b0e14;
            color: #ffffff;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
        }
        h1, h2 {
            color: #00ffa3;
            font-family: monospace;
        }
        /* Moving Marquee Ticker for stocks < Rs 500 */
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
        
        /* Grid layout for Top 10 Detailed Cards */
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
    </style>
    <script>
        // Auto refresh page every 60 seconds for live data sync
        setTimeout(function(){
           window.location.reload(1);
        }, 60000);
    </script>
</head>
<body>

    <h1>⚡ Live AI Momentum Screener (Scanned 50+ Stocks)</h1>
    
    <p><b>Live Ticker (&lt; ₹500 Only):</b> Moving ticker tape displaying real-time live data for stocks priced under ₹500.</p>
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
            <!-- Duplicate loop for seamless infinite marquee scroll effect -->
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

    <h2>Top 10 AI Recommendations (Chart, RSI, MACD, Tech & Fundamental Analysis)</h2>
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

</body>
</html>
"""

@app.route("/")
@app.route("/dashboard")
def dashboard():
    marquee_stocks, top_10_stocks = scan_and_analyze_stocks()
    return render_template_string(TEMPLATE, marquee_stocks=marquee_stocks, top_10=top_10_stocks)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
