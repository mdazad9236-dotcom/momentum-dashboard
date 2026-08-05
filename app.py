from flask import Flask, render_template_string, request, redirect, session, url_for
import random

app = Flask(__name__)
app.secret_key = "admin123_secret_key"  # Badal dena baad me

# DUMMY ADMIN
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# DUMMY 50 STOCKS DATA
STOCKS = [
    {"name": "RELIANCE", "price": 2945, "change": 2.1, "score": 85, "pred": "+18% to +25%"},
    {"name": "TCS", "price": 4012, "change": 1.0, "score": 78, "pred": "+12% to +18%"},
    {"name": "ICIBANK", "price": 1120, "change": -0.5, "score": 88, "pred": "+18% to +25%"},
    {"name": "HDFCBANK", "price": 1650, "change": 1.2, "score": 82, "pred": "+15% to +22%"},
    {"name": "INFY", "price": 1720, "change": 0.8, "score": 75, "pred": "+10% to +16%"},
]
# Tum yaha 50 stocks add kar dena. Abhi 5 demo ke liye

NEWS = [
    "SBIN Q2 Profit up 22% - Moneycontrol",
    "RBI keeps Repo Rate unchanged",
    "Reliance signs new Jio Deal",
    "NIFTY hits new all time high"
]

# HTML TEMPLATE - SAB KUCH YAHI HAI
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Stock Dashboard</title>
<style>
  :root {
    --bg: #0a0a0f; --card: #13131a; --text: #e0e0e0;
    --green: #00ff88; --red: #ff4d4d; --blue: #00aaff;
  }
    * { margin:0; padding:0; box-sizing:border-box; font-family: 'Segoe UI', sans-serif; }
  body { background: var(--bg); color: var(--text); }
  header { position: sticky; top:0; z-index:100; backdrop-filter: blur(10px);
    background: rgba(19,19,26,0.8); padding: 12px 20px; display:flex; 
    justify-content:space-between; align-items:center; border-bottom: 1px solid #222; }
  .logo { font-weight: 700; font-size: 20px; color: var(--blue); }
  nav a { color: var(--text); text-decoration:none; margin:0 12px; font-size:14px; }
  .btn { background: var(--card); border:1px solid #333; padding:6px 12px; border-radius:6px; cursor:pointer; color:var(--text); }
  .ticker { background: var(--card); padding: 8px 0; overflow: hidden; white-space: nowrap; border-bottom: 1px solid #222; }
  .ticker-content { display: inline-block; animation: scroll 40s linear infinite; }
  .ticker span { margin: 0 20px; font-size: 13px; }
  .up { color: var(--green); } .down { color: var(--red); }
  @keyframes scroll { from {transform: translateX(100%);} to {transform: translateX(-100%);} }
  .container { padding: 20px; }
  .stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; margin-top: 20px; }
  .stock-card { background: var(--card); padding: 15px; border-radius: 10px; border: 1px solid #222; transition: 0.3s; }
  .stock-card:hover { border-color: var(--blue); transform: translateY(-3px); }
  .score { font-size: 22px; font-weight: bold; color: var(--green); }
  .login-box { width: 300px; margin: 100px auto; background: var(--card); padding: 30px; border-radius: 10px; }
  .login-box input { width: 100%; padding: 10px; margin: 10px 0; background: #222; border:1px solid #333; color:var(--text); border-radius:5px; }
</style>
</head>
<body>

{% if logged_in %}
<header>
  <button class="btn" onclick="history.back()">← Back</button>
  <div class="logo">AI STOCKS</div>
  <nav><a href="/">Dashboard</a><a href="https://www.nseindia.com/market-data/live-equity-market">More Stocks</a></nav>
  <a href="/logout" class="btn">Logout</a>
</header>

<div class="ticker">
  <div class="ticker-content">
    <span>NIFTY <span class="up">25123 ▲ 1.2%</span></span>
    <span>BANKNIFTY <span class="down">54210 ▼ 0.5%</span></span>
    {% for s in stocks %}
    <span>{{s.name}} <span class="{{'up' if s.change>0 else 'down'}}">{{s.price}} {{'▲' if s.change>0 else '▼'}} {{s.change}}%</span></span>
    {% endfor %}
  </div>
</div>

<div class="ticker">
  <div class="ticker-content">
    {% for n in news %}<span>📰 {{n}}</span>{% endfor %}
  </div>
</div>

<div class="container">
  <h2>Top 50 Stocks - AI Score</h2>
  <a href="https://www.nseindia.com/market-data/live-equity-market" class="btn">Scan More Stocks on NSE</a>
  <div class="stock-grid">
    {% for s in stocks %}
    <div class="stock-card">
      <h3>{{s.name}}</h3>
      <div>Price: ₹{{s.price}}</div>
      <div class="score">Score: {{s.score}}/100</div>
      <div class="prediction">Prediction: {{s.pred}} in 6 Months</div>
    </div>
    {% endfor %}
  </div>
</div>
{% else %}
<div class="login-box">
  <h2>Admin Login</h2>
  <form method="POST">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button class="btn" style="width:100%;">Login</button>
  </form>
  {% if error %}<p style="color:red;">{{error}}</p>{% endif %}
</div>
{% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return render_template_string(HTML, logged_in=True, stocks=STOCKS, news=NEWS)
    
    error = None
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["logged_in"] = True
            return redirect(url_for("login"))
        else:
            error = "Galat Username ya Password"
    return render_template_string(HTML, logged_in=False, error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
