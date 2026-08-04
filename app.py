def get_momentum_data():
    download_data() # Pehli baar call hote hi data download
    try:
        df = pd.read_csv(DATA_FILE)
        
        # YE 2 LINE NAYI DAALO
        if 'Date' not in df.columns:
            df['Date'] = df.iloc[:, 0] # Pehla column hi Date hota hai
        
        df['Date'] = pd.to_datetime(df['Date'])
        results = []
        for symbol in df['Stock'].unique():
            stock_df = df[df['Stock'] == symbol].sort_values('Date')
            if len(stock_df) < 90: continue
            start_price = stock_df['Close'].iloc[-90]
            end_price = stock_df['Close'].iloc[-1]
            ret_3m = ((end_price / start_price) - 1) * 100
            results.append({"Stock": symbol, "Price": round(end_price,2), "3M Return %": round(ret_3m,2)})
        df_res = pd.DataFrame(results).sort_values("3M Return %", ascending=False)
        return df_res.to_html(classes='table', index=False, border=0)
    except Exception as e:
        return f"<p style='color:red'>Error: {e}</p>"
        
        import os
os.environ['PYTHONUNBUFFERED'] = '1'

from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import yfinance as yf

app = Flask(__name__)
app.secret_key = 'momentum_secret_2026'
DATA_FILE = 'nse_data.csv'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

USERS = {"azad": generate_password_hash("1234")}

class User(UserMixin):
    def __init__(self, id): self.id = id
@login_manager.user_loader
def load_user(user_id): return User(user_id)

STOCKS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]

def download_data():
    if not os.path.exists(DATA_FILE):
        print("Downloading data for first time...")
        all_data = []
        for symbol in STOCKS:
            data = yf.download(symbol, period="5y", interval="1d", progress=False)
            data['Stock'] = symbol.replace('.NS','')
            all_data.append(data)
        df = pd.concat(all_data)
        df.reset_index(inplace=True)
        df.to_csv(DATA_FILE, index=False)
        print("Download complete!")

def get_momentum_data():
    download_data() # Pehli baar call hote hi data download
    try:
        df = pd.read_csv(DATA_FILE)
        df['Date'] = pd.to_datetime(df['Date'])
        results = []
        for symbol in df['Stock'].unique():
            stock_df = df[df['Stock'] == symbol].sort_values('Date')
            if len(stock_df) < 90: continue
            start_price = stock_df['Close'].iloc[-90]
            end_price = stock_df['Close'].iloc[-1]
            ret_3m = ((end_price / start_price) - 1) * 100
            results.append({"Stock": symbol, "Price": round(end_price,2), "3M Return %": round(ret_3m,2)})
        df_res = pd.DataFrame(results).sort_values("3M Return %", ascending=False)
        return df_res.to_html(classes='table', index=False, border=0)
    except Exception as e:
        return f"<p style='color:red'>Error: {e}</p>"

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
def menu(): return render_template_string(BASE + "<div class=container><h1>Menu</h1><a href=/dashboard class=btn>1. NSE Momentum Dashboard - Backtest</a><br><br><a href=/logout class=btn style=background:red>Logout</a></div>")
@app.route('/dashboard')
@login_required
def dashboard(): return render_template_string(BASE + f"<div class=container><h1>Top 5 NSE Momentum Stocks - Last 3 Months</h1>{get_momentum_data()}<br><a href=/menu class=btn>Back</a></div>")
@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
