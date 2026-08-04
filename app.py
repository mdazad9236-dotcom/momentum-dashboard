from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.io as pio

app = Flask(__name__)
app.secret_key = 'momentum_secret_key_2026_change_this'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 1. USERS - yaha aur add kar sakte ho
USERS = {
    "azad": generate_password_hash("1234")
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# 2. MOMENTUM LOGIC
def get_top_momentum_stocks():
    tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICIBANK.NS", 
               "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "HCLTECH.NS"] # Top 10 for speed
    
    results = []
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if len(data) < 50: continue
            
            data['SMA50'] = data['Close'].rolling(window=50).mean()
            data['SMA200'] = data['Close'].rolling(window=200).mean()
            data['ROC'] = data['Close'].pct_change(periods=63) * 100 # 3 month return
            
            latest = data.iloc[-1]
            if latest['Close'] > latest['SMA50'] > latest['SMA200'] and latest['ROC'] > 5:
                results.append({
                    "Ticker": ticker.replace(".NS",""),
                    "Price": round(latest['Close'], 2),
                    "3M Return": round(latest['ROC'], 2),
                    "Volume": int(latest['Volume'])
                })
        except: continue
    
    df = pd.DataFrame(results).sort_values("3M Return", ascending=False).head(25)
    return df.to_html(classes='table', index=False)

def create_chart(ticker="RELIANCE.NS"):
    data = yf.download(ticker, period="3mo", interval="1d")
    fig = go.Figure(data=[go.Candlestick(x=data.index,
                    open=data['Open'], high=data['High'],
                    low=data['Low'], close=data['Close'])])
    fig.update_layout(title=f'{ticker} Chart', xaxis_rangeslider_visible=False)
    return pio.to_html(fig, full_html=False)

# 3. HTML TEMPLATES
BASE_CSS = """<style>
body{font-family:sans-serif;background:#f4f7f9;margin:0;padding:20px}
.container{max-width:1200px;margin:auto;background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
.table{width:100%;border-collapse:collapse}.table th,.table td{padding:10px;border:1px solid #ddd;text-align:center}
.btn{background:#007bff;color:white;padding:10px 15px;border:none;border-radius:5px;text-decoration:none;display:inline-block;margin:5px}
</style>"""

LOGIN_TEMPLATE = BASE_CSS + """
<div class="container" style="max-width:400px;text-align:center">
<h2>Login</h2>
{% with messages = get_flashed_messages() %}{% if messages %}<p style="color:red">{{ messages[0] }}</p>{% endif %}{% endwith %}
<form method="post">
<input name="username" placeholder="Username" required style="width:90%;padding:10px;margin:5px"><br>
<input name="password" type="password" placeholder="Password" required style="width:90%;padding:10px;margin:5px"><br>
<button class="btn">Login</button></form></div>
"""

MENU_TEMPLATE = BASE_CSS + """
<div class="container">
<h1>Welcome {{current_user.id}} 👑</h1>
<a href="{{ url_for('dashboard') }}" class="btn">1. Momentum Dashboard</a>
<a href="{{ url_for('chart') }}" class="btn">2. Stock Chart</a>
<a href="{{ url_for('logout') }}" class="btn" style="background:red">Logout</a>
</div>
"""

DASHBOARD_TEMPLATE = BASE_CSS + """
<div class="container">
<h1>Top Momentum Stocks</h1>
{{ table|safe }}
<br><a href="{{ url_for('menu') }}" class="btn">Back to Menu</a>
</div>
"""

CHART_TEMPLATE = BASE_CSS + """
<div class="container">
<h1>Stock Chart</h1>
<form method="get">
<input name="ticker" placeholder="RELIANCE.NS" value="{{ticker}}">
<button class="btn">Show Chart</button></form>
<div>{{ chart|safe }}</div>
<br><a href="{{ url_for('menu') }}" class="btn">Back to Menu</a>
</div>
"""

# 4. ALL ROUTES
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        if u in USERS and check_password_hash(USERS[u], p):
            login_user(User(u)); return redirect(url_for('menu'))
        flash('Galat Username ya Password')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/menu')
@login_required
def menu(): return render_template_string(MENU_TEMPLATE)

@app.route('/dashboard')
@login_required
def dashboard():
    table = get_top_momentum_stocks()
    return render_template_string(DASHBOARD_TEMPLATE, table=table)

@app.route('/chart')
@login_required
def chart():
    ticker = request.args.get('ticker', 'RELIANCE.NS')
    chart_html = create_chart(ticker)
    return render_template_string(CHART_TEMPLATE, chart=chart_html, ticker=ticker)

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))
