import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import requests
from datetime import datetime

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

NSE_TOP_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICIBANK", "INFY", "HINDUNILVR",
    "SBIN", "ITC", "KOTAKBANK", "LT", "HCLTECH", "AXISBANK", "BAJFINANCE", "MARUTI"
]

def get_momentum_data():
    results = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for symbol in NSE_TOP_50:
        try:
            url = f"https://priceapi.moneycontrol.com/pricefeed/nse/equitycash/{symbol}"
            r = requests.get(url, headers=headers, timeout=3).json()
            data = r['data']
            name = data['companyName']
            price = float(data['pricecurrent'])
            ret_3m = float(data['pricepercentchange3m'])
            results.append({"Stock": name, "Price": round(price,2), "3M Return %": round(ret_3m,2)})
        except:
            continue # Error aaya to skip kar do

    # YE LINE NAYI JODI HAI - Agar results khali hai to demo data do
    if len(results) == 0:
        results = [
            {"Stock": "HDFCBANK", "Price": 1650.25, "3M Return %": 18.4},
            {"Stock": "RELIANCE", "Price": 2950.10, "3M Return %": 15.2},
            {"Stock": "TCS", "Price": 3800.50, "3M Return %": 12.8},
        ]
        note = "<p style='color:orange'><b>Note:</b> Live API block hai. Demo data dikh raha hai</p>"
    else:
        note = ""

    df_res = pd.DataFrame(results).sort_values("3M Return %", ascending=False).head(5)
    last_update = datetime.now().strftime('%d-%m-%Y %H:%M')
    return note + f"<p><b>Data till:</b> {last_update}</p>" + df_res.to_html(classes='table', index=False, border=0)

BASE = "<style>body{font-family:sans-serif;background:#f4f7f9;margin:0}.container{max-width:900px;margin:20px auto;background:white;padding:20px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.1)}.table{width:100%;border-collapse:collapse}.table th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left}.table th{background:#007bff;color:white}.btn{background:#007bff;color:white;padding:10px 15px;border-radius:5px;text-decoration:none;border:none;display:inline-block;margin:5px 0}.btn-danger{background:red}</style>"

@app.route('/')
def home(): return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u,p = request.form['username'], request.form['password']
        if u in USERS and check_password_hash(USERS[u], p): login_user(User(u)); return redirect(url_for('menu'))
        flash('Galat Username ya Password')
    return render_template_string(BASE + "<div class=container><h2>Login</h2><form method=post><input name=username placeholder=Username required style='padding:8px;width:95%'><br><br><input name=password type=password placeholder=Password required style='padding:8px;width:95%'><br><br><button class=btn>Login</button></form></div>")
@app.route('/menu')
@login_required
def menu(): return render_template_string(BASE + "<div class=container><h1>Menu</h1><a href=/dashboard class=btn>1. NSE Momentum Dashboard - LIVE</a><br><a href=/logout class=btn btn-danger>Logout</a></div>")
@app.route('/dashboard')
@login_required
def dashboard(): return render_template_string(BASE + f"<div class=container><h1>Top 5 NSE Momentum Stocks - Last 3 Months</h1>{get_momentum_data()}<br><a href=/menu class=btn>Back to Menu</a></div>")
@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
