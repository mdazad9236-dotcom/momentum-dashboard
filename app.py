import os
from flask import Flask, render_template_string, request, redirect, session, url_for

app = Flask(__name__)

# Security: Uses Environment Variables or safe default fallbacks
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_production_key_change_me_123!")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")

STOCKS = [
    {"name": "RELIANCE", "price": 2945, "change": 2.1, "score": 85, "pred": "+18% to +25%"},
    {"name": "TCS", "price": 4012, "change": 1.0, "score": 78, "pred": "+12% to +18%"},
    {"name": "ICICIBANK", "price": 1120, "change": -0.5, "score": 88, "pred": "+18% to +25%"},
    {"name": "HDFCBANK", "price": 1650, "change": 1.2, "score": 82, "pred": "+15% to +22%"},
    {"name": "INFY", "price": 1720, "change": 0.8, "score": 75, "pred": "+10% to +16%"},
]

NEWS = [
    "SBIN Q2 Profit up 22% - Moneycontrol",
    "RBI keeps Repo Rate unchanged",
    "Reliance signs new Jio Deal",
    "NIFTY hits new all time high"
]

HTML_LOGIN = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - AI Stocks</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0a0f; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .login-box { width: 100%; max-width: 360px; background: #13131a; padding: 30px; border-radius: 12px; border: 1px solid #222; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
        .login-box h2 { margin-bottom: 20px; font-weight: 600; text-align: center; color: #00aaff; }
        .login-box input { width: 100%; padding: 12px; margin-bottom: 15px; background: #1c1c24; border: 1px solid #333; color: #e0e0e0; border-radius: 6px; font-size: 14px; outline: none; transition: border 0.3s; }
        .login-box input:focus { border-color: #00aaff; }
        .btn { background: #00aaff; border: none; padding: 12px; border-radius: 6px; cursor: pointer; color: #fff; width: 100%; font-weight: 600; font-size: 14px; transition: background 0.2s; }
        .btn:hover { background: #0088cc; }
        .error-msg { color: #ff4d4d; margin-top: 15px; font-size: 13px; text-align: center; }
    </style>
</head>
<body>
<div class="login-box">
    <h2>Admin Login</h2>
    <form method="POST" action="/">
        <input type="text" name="username" placeholder="Username" required autocomplete="off">
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit" class="btn">Login</button>
    </form>
    {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
</div>
</body>
</html>
"""

HTML_DASH = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Stocks Dashboard</title>
    <style>
        :root { --bg: #0a0a0f; --card: #13131a; --text: #e0e0e0; --green: #00ff88; --red: #ff4d4d; --blue: #00aaff; }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
        body { background: var(--bg); color: var(--text); padding-bottom: 40px; }
        
        header { position: sticky; top: 0; z-index: 100; background: rgba(19, 19, 26, 0.95); backdrop-filter: blur(8px); padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; }
        .logo { font-weight: 700; font-size: 20px; color: var(--blue); letter-spacing: 0.5px; }
        nav { display: flex; gap: 10px; align-items: center; }
        .btn { background: var(--card); border: 1px solid #333; padding: 6px 14px; border-radius: 6px; cursor: pointer; color: var(--text); text-decoration: none; font-size: 13px; transition: all 0.2s; }
        .btn:hover { border-color: var(--blue); color: var(--blue); }
        
        /* Continuous Loop Ticker Styling */
        .ticker-wrapper { background: var(--card); border-bottom: 1px solid #222; overflow: hidden; display: flex; }
        .ticker { display: flex; width: 100%; overflow: hidden; white-space: nowrap; padding: 8px 0; }
        .ticker-content { display: inline-flex; animation: scroll 30s linear infinite; }
        .ticker-content span { margin: 0 15px; font-size: 13px; }
        .up { color: var(--green); }
        .down { color: var(--red); }
        @keyframes scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }

        .container { max-width: 1200px; margin: 0 auto; padding: 25px 20px; }
        .container h2 { font-size: 22px; font-weight: 600; margin-bottom: 20px; }
        .stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 18px; }
        .stock-card { background: var(--card); padding: 18px; border-radius: 10px; border: 1px solid #222; transition: transform 0.2s, border-color 0.2s; }
        .stock-card:hover { transform: translateY(-2px); border-color: #333; }
        .stock-card h3 { font-size: 18px; margin-bottom: 10px; color: #fff; }
        .stock-card .price { font-size: 14px; color: #aaa; margin-bottom: 8px; }
        .stock-card .score { font-size: 20px; font-weight: 700; color: var(--green); margin: 8px 0; }
        .stock-card .pred { font-size: 12px; color: var(--blue); }
    </style>
</head>
<body>
<header>
    <div class="logo">AI STOCKS</div>
    <nav>
        <a href="/dashboard" class="btn">Dashboard</a>
        <a href="https://www.nseindia.com/market-data/live-equity-market" target="_blank" rel="noopener" class="btn">NSE Live</a>
        <a href="/logout" class="btn" style="border-color: #ff4d4d; color: #ff4d4d;">Logout</a>
    </nav>
</header>

<!-- Stock Price Ticker -->
<div class="ticker-wrapper">
    <div class="ticker">
        <div class="ticker-content">
            <span>NIFTY <span class="up">25,123 ▲ 1.2%</span></span>
            {% for s in stocks %}<span>{{s.name}} <span class="{{'up' if s.change>0 else 'down'}}">₹{{s.price}} {{'▲' if s.change>0 else '▼'}} {{s.change}}%</span></span>{% endfor %}
            <!-- Duplicate content ensures infinite loop without visual blank gaps -->
            <span>NIFTY <span class="up">25,123 ▲ 1.2%</span></span>
            {% for s in stocks %}<span>{{s.name}} <span class="{{'up' if s.change>0 else 'down'}}">₹{{s.price}} {{'▲' if s.change>0 else '▼'}} {{s.change}}%</span></span>{% endfor %}
        </div>
    </div>
</div>

<!-- News Ticker -->
<div class="ticker-wrapper">
    <div class="ticker">
        <div class="ticker-content">
            {% for n in news %}<span>📰 {{n}}</span>{% endfor %}
            {% for n in news %}<span>📰 {{n}}</span>{% endfor %}
        </div>
    </div>
</div>

<div class="container">
    <h2>Top AI Recommendations</h2>
    <div class="stock-grid">
        {% for s in stocks %}
        <div class="stock-card">
            <h3>{{s.name}}</h3>
            <div class="price">Price: ₹{{s.price}}</div>
            <div class="score">Score: {{s.score}}/100</div>
            <div class="pred">Est. Return: {{s.pred}} (6 Mo)</div>
        </div>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            # HTTP 303 forces GET request to avoid method errors
            return redirect(url_for("dashboard"), code=303)
        else:
            error = "Galat Username ya Password"

    return render_template_string(HTML_LOGIN, error=error)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    # Fixes 405 Method Not Allowed if browser submits a POST directly to dashboard
    if request.method == "POST":
        return redirect(url_for("dashboard"))

    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    return render_template_string(HTML_DASH, stocks=STOCKS, news=NEWS)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
