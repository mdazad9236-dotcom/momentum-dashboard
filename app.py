from flask import Flask, render_template_string, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = "admin123_secret_key_change_kardo"

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

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
<!DOCTYPE html><html><head><title>Login</title>
<style>
body{background:#0a0a0f;color:#e0e0e0;font-family:Segoe UI}
.login-box{width:300px;margin:100px auto;background:#13131a;padding:30px;border-radius:10px}
.login-box input{width:100%;padding:10px;margin:10px 0;background:#222;border:1px solid #333;color:#e0e0e0;border-radius:5px}
.btn{background:#00aaff;border:none;padding:10px 12px;border-radius:6px;cursor:pointer;color:#fff;width:100%}
</style></head><body>
<div class="login-box">
  <h2>Admin Login</h2>
  <form method="POST">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button class="btn">Login</button>
  </form>
  {% if error %}<p style="color:red;">{{error}}</p>{% endif %}
</div></body></html>
"""

HTML_DASH = """
<!DOCTYPE html><html><head><title>Dashboard</title>
<style>
:root{--bg:#0a0a0f;--card:#13131a;--text:#e0e0e0;--green:#00ff88;--red:#ff4d4d;--blue:#00aaff}
*{margin:0;padding:0;box-sizing:border-box;font-family:Segoe UI}
body{background:var(--bg);color:var(--text)}
header{position:sticky;top:0;background:rgba(19,19,26,0.8);padding:12px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #222}
.logo{font-weight:700;font-size:20px;color:var(--blue)}
.btn{background:var(--card);border:1px solid #333;padding:6px 12px;border-radius:6px;cursor:pointer;color:var(--text);text-decoration:none}
.ticker{background:var(--card);padding:8px 0;overflow:hidden;white-space:nowrap;border-bottom:1px solid #222}
.ticker-content{display:inline-block;animation:scroll 40s linear infinite}
.ticker span{margin:0 20px;font-size:13px}
.up{color:var(--green)}.down{color:var(--red)}
@keyframes scroll{from{transform:translateX(100%)}to{transform:translateX(-100%)}}
.container{padding:20px}
.stock-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:15px;margin-top:20px}
.stock-card{background:var(--card);padding:15px;border-radius:10px;border:1px solid #222}
.score{font-size:22px;font-weight:bold;color:var(--green)}
</style></head><body>
<header>
  <a href="/" class="btn">← Back</a>
  <div class="logo">AI STOCKS</div>
  <nav><a href="/dashboard" class="btn">Dashboard</a><a href="https://www.nseindia.com/market-data/live-equity-market" target="_blank" class="btn">More Stocks</a></nav>
  <a href="/logout" class="btn">Logout</a>
</header>
<div class="ticker"><div class="ticker-content">
  <span>NIFTY <span class="up">25123 ▲ 1.2%</span></span>
  {% for s in stocks %}<span>{{s.name}} <span class="{{'up' if s.change>0 else 'down'}}">{{s.price}} {{'▲' if s.change>0 else '▼'}} {{s.change}}%</span></span>{% endfor %}
</div></div>
<div class="ticker"><div class="ticker-content">{% for n in news %}<span>📰 {{n}}</span>{% endfor %}</div></div>
<div class="container">
  <h2>Top 50 Stocks - AI Score</h2>
  <div class="stock-grid">
    {% for s in stocks %}
    <div class="stock-card"><h3>{{s.name}}</h3><div>Price: ₹{{s.price}}</div><div class="score">Score: {{s.score}}/100</div><div>Prediction: {{s.pred}} in 6 Months</div></div>
    {% endfor %}
  </div>
</div>
</body></html>
"""

@app.route("/", methods=["GET", "POST"])  # Login yahi hoga
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    
    error = None
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "Galat Username ya Password"
    return render_template_string(HTML_LOGIN, error=error)

@app.route("/dashboard", methods=["GET"])  # Dashboard sirf GET
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(HTML_DASH, stocks=STOCKS, news=NEWS)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
