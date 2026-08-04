import os
os.environ['PYTHONUNBUFFERED'] = '1'

from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import yfinance as yf
import pandas as pd

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

def get_top_momentum_stocks():
    # Sirf 5 stock rakhe hai speed ke liye. Baad me badha dena
    tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    results = []
    for ticker in tickers:
        try:
            data = yf.Ticker(ticker).history(period="3mo")
            if len(data) < 50: continue
            ret_3m = ((data['Close'][-1] / data['Close'][0]) - 1) * 100
            results.append({"Ticker": ticker.replace(".NS",""), "Price": round(data['Close'][-1],2), "3M Return %": round(ret_3m,2)})
        except: pass
    df = pd.DataFrame(results).sort_values("3M Return %", ascending=False)
    return df.to_html(classes='table', index=False, border=0)

# CHART KE LIYE SIMPLE IMG USE KARENGE, PLOTLY NAHI
def get_chart_url(ticker):
    return f"https://finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l"

BASE = "<style>body{font-family:sans-serif;background:#f4f7f9}.container{max-width:900px;margin:20px auto;background:white;padding:20px;border-radius:10px}.table{width:100%}.btn{background:#007bff;color:white;padding:10px;border-radius:5px;text-decoration:none}</style>"

@app.route('/')
def home(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u,p = request.form['username'], request.form['password']
        if u in USERS and check_password_hash(USERS[u], p): login_user(User(u)); return redirect(url_for('menu'))
        flash('Galat Password')
    return render_template_string(BASE + "<div class=container><h2>Login</h2><form method=post><input name=username><br><br><input name=password type=password><br><br><button class=btn>Login</button></form></div>")

@app.route('/menu')
@login_required
def menu(): return render_template_string(BASE + "<div class=container><h1>Menu</h1><a href=/dashboard class=btn>1. Momentum Dashboard</a><br><br><a href=/chart class=btn>2. Stock Chart</a><br><br><a href=/logout class=btn style=background:red>Logout</a></div>")

@app.route('/dashboard')
@login_required
def dashboard():
    table = get_top_momentum_stocks()
    return render_template_string(BASE + f"<div class=container><h1>Top 5 Momentum Stocks</h1>{table}<br><a href=/menu class=btn>Back</a></div>")

@app.route('/chart')
@login_required
def chart():
    ticker = request.args.get('ticker', 'RELIANCE')
    img_url = get_chart_url(ticker)
    return render_template_string(BASE + f"<div class=container><h1>Chart: {ticker}</h1><form><input name=ticker value={ticker}><button class=btn>Go</button></form><img src='{img_url}' width=100%><br><br><a href=/menu class=btn>Back</a></div>")

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))
