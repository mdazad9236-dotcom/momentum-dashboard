import os
os.environ['PYTHONUNBUFFERED'] = '1'

from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from smartapi import SmartConnect
import pyotp
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv() #.env file read karega

app = Flask(__name__)
app.secret_key = 'momentum_secret_2026'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

USERS = {"azad": generate_password_hash("1234")}

class User(UserMixin):
    def __init__(self, id): self.id = id

@login_manager.user_loader
def load_user(user_id): return User(user_id)

# ===== ANGLEONE LOGIN =====
def get_angel_client():
    try:
        api_key = os.environ.get("ymEm01h7")
        client_code = os.environ.get("M1025612")
        password = os.environ.get("7439")
        totp_secret = os.environ.get("UC27CK2C4YYKOEHKPT543XHOYI")

        smartApi = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        data = smartApi.generateSession(client_code, password, totp)
        return smartApi
    except Exception as e:
        print("Angel Login Error:", e)
        return None

# ===== MOMENTUM DATA =====
STOCKS = {
    "RELIANCE": "3045",
    "TCS": "11536",
    "INFY": "1594",
    "HDFCBANK": "1333",
    "ICIBANK": "4963"
}

def get_momentum_data():
    smartApi = get_angel_client()
    if not smartApi: return "<p>AngleOne Login Failed..env check karo</p>"

    to_date = datetime.now()
    from_date = to_date - timedelta(days=90)

    results = []
    for name, token in STOCKS.items():
        try:
            data = smartApi.getCandleData({
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "ONE_DAY",
                "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
                "todate": to_date.strftime("%Y-%m-%d %H:%M")
            })
            df = pd.DataFrame(data['data'], columns=['time','o','h','l','c','v'])
            ret_3m = ((df['c'].iloc[-1] / df['c'].iloc[0]) - 1) * 100
            results.append({"Stock": name, "Price": round(df['c'].iloc[-1],2), "3M Return %": round(ret_3m,2)})
        except: pass

    df_res = pd.DataFrame(results).sort_values("3M Return %", ascending=False)
    return df_res.to_html(classes='table', index=False, border=0)

# ===== CHART URL =====
def get_chart_url(ticker):
    return f"https://charting.tradingview.com/chart.html?symbol=NSE:{ticker}"

BASE = "<style>body{font-family:sans-serif;background:#f4f7f9}.container{max-width:900px;margin:20px auto;background:white;padding:20px;border-radius:10px}.table{width:100%}.table th,td{padding:8px}.btn{background:#007bff;color:white;padding:10px;border-radius:5px;text-decoration:none}</style>"

@app.route('/')
def home(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u,p = request.form['username'], request.form['password']
        if u in USERS and check_password_hash(USERS[u], p): login_user(User(u)); return redirect(url_for('menu'))
        flash('Galat Password')
    return render_template_string(BASE + "<div class=container><h2>Login</h2><form method=post><input name=username placeholder=Username><br><br><input name=password type=password placeholder=Password><br><br><button class=btn>Login</button></form></div>")

@app.route('/menu')
@login_required
def menu(): return render_template_string(BASE + "<div class=container><h1>Menu</h1><a href=/dashboard class=btn>1. Momentum Dashboard</a><br><br><a href=/chart class=btn>2. Stock Chart</a><br><br><a href=/logout class=btn style=background:red>Logout</a></div>")

@app.route('/dashboard')
@login_required
def dashboard():
    table = get_momentum_data()
    return render_template_string(BASE + f"<div class=container><h1>Top 5 Momentum Stocks</h1>{table}<br><a href=/menu class=btn>Back</a></div>")

@app.route('/chart')
@login_required
def chart():
    ticker = request.args.get('ticker', 'RELIANCE')
    img_url = get_chart_url(ticker)
    return render_template_string(BASE + f"<div class=container><h1>Chart: {ticker}</h1><form><input name=ticker value={ticker} placeholder='RELIANCE'><button class=btn>Go</button></form><iframe src='{img_url}' width=100% height=500></iframe><br><a href=/menu class=btn>Back</a></div>")

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run()
