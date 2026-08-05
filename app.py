from flask import Flask, render_template_string
import yfinance as yf

app = Flask(__name__)

# List of tickers to track on your dashboard (using .NS for National Stock Exchange of India)
TICKERS = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "INFY": "INFY.NS"
}

# Dummy AI recommendations & scores to match your dashboard style
AI_METRICS = {
    "RELIANCE": {"score": 85, "return": "+18% to +25% (6 Mo)"},
    "TCS": {"score": 78, "return": "+12% to +18% (6 Mo)"},
    "ICICIBANK": {"score": 88, "return": "+18% to +25% (6 Mo)"},
    "HDFCBANK": {"score": 82, "return": "+15% to +22% (6 Mo)"},
    "INFY": {"score": 75, "return": "+10% to +16% (6 Mo)"}
}

def get_live_stock_data():
    stock_data = []
    for name, ticker in TICKERS.items():
        try:
            stock = yf.Ticker(ticker)
            todays_data = stock.history(period="1d")
            
            if not todays_data.empty:
                current_price = todays_data['Close'].iloc[-1]
                prev_close = stock.info.get('previousClose', current_price)
                change = ((current_price - prev_close) / prev_close) * 100
            else:
                current_price = 0.0
                change = 0.0
        except Exception:
            current_price = 0.0
            change = 0.0
            
        stock_data.append({
            "symbol": name,
            "price": round(current_price, 2),
            "change": round(change, 2),
            "score": AI_METRICS[name]["score"],
            "return": AI_METRICS[name]["return"]
        })
    return stock_data

# Single-file HTML template embedded directly into Flask
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Momentum Dashboard - Live Data</title>
    <style>
        body {
            background-color: #121212;
            color: #ffffff;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #e0e0e0;
            font-size: 1.5rem;
            margin-bottom: 20px;
        }
        .ticker-tape {
            background-color: #1e1e1e;
            padding: 10px;
            font-size: 0.9rem;
            white-space: nowrap;
            overflow: hidden;
            margin-bottom: 30px;
            border-radius: 4px;
        }
        .ticker-item {
            margin-right: 30px;
            display: inline-block;
        }
        .positive { color: #4caf50; }
        .negative { color: #f44336; }
        
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 20px;
        }
        .card {
            background-color: #1e1e1e;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .card h3 {
            margin: 0 0 10px 0;
            font-size: 1.1rem;
            color: #ffffff;
        }
        .price {
            font-size: 0.95rem;
            color: #b0b0b0;
            margin-bottom: 8px;
        }
        .score {
            font-size: 1.2rem;
            font-weight: bold;
            color: #4caf50;
            margin-bottom: 8px;
        }
        .est-return {
            font-size: 0.8rem;
            color: #808080;
        }
    </style>
    <!-- Auto-refresh page every 60 seconds to get latest live prices -->
    <script>
        setTimeout(function(){
           window.location.reload(1);
        }, 60000);
    </script>
</head>
<body>

    <h1>Top AI Recommendations (Live Data)</h1>
    
    <div class="ticker-tape">
        {% for stock in stocks %}
            <span class="ticker-item">
                <strong>{{ stock.symbol }}</strong> 
                ₹{{ stock.price }} 
                <span class="{{ 'positive' if stock.change >= 0 else 'negative' }}">
                    {{ '+' if stock.change >= 0 else '' }}{{ stock.change }}%
                </span>
            </span>
        {% endfor %}
    </div>

    <div class="grid-container">
        {% for stock in stocks %}
        <div class="card">
            <h3>{{ stock.symbol }}</h3>
            <div class="price">Price: ₹{{ stock.price }}</div>
            <div class="score">Score: {{ stock.score }}/100</div>
            <div class="est-return">Est. Return: {{ stock.return }}</div>
        </div>
        {% endfor %}
    </div>

</body>
</html>
"""

@app.route("/")
@app.route("/dashboard")
def dashboard():
    stocks = get_live_stock_data()
    return render_template_string(TEMPLATE, stocks=stocks)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
