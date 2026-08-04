import os
os.environ['PYTHONUNBUFFERED'] = '1'

from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from nsepython import nse_quote, nse_eq
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'momentum_secret_2026'
DATA_FILE = 'data.csv'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

USERS = {"azad": generate_password_hash("1234")}

class User(UserMixin):
    def __init__(self, id): self.id = id

@login_manager.user_loader
def load_user(user_id): return User(user_id)

STOCKS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICIBANK"]

def fetch_and_save_data():
    results = []
    for symbol in STOCKS:
        try:
            data = nse_eq(symbol)
            if not data or 'data' not in data: continue
            df = pd.DataFrame(data['data'])
            df['CHG'] = pd.to_numeric(df['CHG'], errors='coerce')
            df = df.dropna(subset=['CHG'])
            ret_3m = ((df['CHG'].iloc[-1] / df['CHG'].iloc[0]) - 1) * 100
            quote = nse_quote(symbol)
            ltp = quote['priceInfo']['lastPrice']
            results.append({"Stock": symbol, "Price": round(ltp,2), "3M Return %": round(ret_3m,2)})
        except: pass

    if results:
        df_res = pd.DataFrame(results).sort_values("3M Return %", ascending=False)
        df_res.to_csv(DATA_FILE, index=False)
        return True
    return False

def get_momentum_data():
    # Agar file nahi hai to abhi data fetch karo
    if not os.path.exists(DATA_FILE):
        fetch_and_save_data()

    try:
        df_res = pd.read_csv(DATA_FILE)
        last_update = datetime.fromtimestamp(os.path.getmtime(DATA_FILE)).strftime('%d-%m-%Y %H:%M')
        table = df_res.to_html(classes='table', index=False, border=0)
        return f"<p><b>Last Updated:</b> {last_update}</p>" + table
    except:
        return "<p style='color:red'>Data load nahi ho raha. 9:15 AM ke baad refresh karo.</p>"

BASE = "<style>body{font-family:sans-serif;background:#f4f7f9}.container{max-width:900px;margin:20px auto;background:white;padding:20px;border-radius:10px}.table{width:100%}.table th,td{padding:8px;border-bottom:1px solid #ddd}.btn{background:#007bff;color:white;padding:10px 15px;border-radius:5px;text-decoration:none;border:none}</style>"

@app.route('/')
def home(): return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u,p = request.form['username'], request.form['password']
        if u in USERS and check_password_hash(USERS[u], p): login_user(User(u)); return redirect(url_for('menu'))
        flash('Galat Username ya Password')
    return render_template_string(BASE + "<div class=container><h2>Login</h2><form method=post><input name=username placeholder=Username required><br><br><input name=password type=password placeholder=Password required><br><br><button class=btn>Login</button></form></div>")
@app.route('/menu')
@login_required
def menu(): return render_template_string(BASE + "<div class=container><h1>Menu</h1><a href=/dashboard class=btn>1. NSE Momentum Dashboard</a><br><a href=/refresh class=btn style=background:green>2. Refresh Data Now</a><br><br><a href=/logout class=btn style=background:red>Logout</a></div>")
@app.route('/dashboard')
@login_required
def dashboard(): return render_template_string(BASE + f"<div class=container><h1>Top 5 NSE Momentum Stocks</h1>{get_momentum_data()}<br><a href=/menu class=btn>Back</a></div>")
@app.route('/refresh')
@login_required
def refresh():
    fetch_and_save_data()
    return redirect(url_for('dashboard'))
@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
