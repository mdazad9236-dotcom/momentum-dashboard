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
            data = yf.download(symbol, period="5y", interval="1d", progress=False, auto_adjust=True)
            data.reset_index(inplace=True)
            data['Stock'] = symbol.replace('.NS','')
            all_data.append(data)
        df = pd.concat(all_data)
        df.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col for col in df.columns] # MultiIndex fix
        df.to_csv(DATA_FILE, index=False)
        print("Download complete!")

def get_momentum_data():
    download_data()
    try:
        df = pd.read_csv(DATA_FILE)
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Agar Adj Close hai to use karo
        if 'Adj Close' in df.columns:
            df['Close'] = df['Adj Close']
        
        results = []
        for symbol in df['Stock'].unique():
            stock_df = df[df['Stock'] == symbol].sort_values('Date')
            if len(stock_df) < 90: continue
            
            stock_df = stock_df.dropna(subset=['Close'])
            
            start_price = stock_df['Close'].iloc[-90]
            end_price = stock_df['Close'].iloc[-1]
            ret_3m = ((end_price / start_price) - 1) * 100
            results.append({"Stock": symbol, "Price": round(end_price,2), "3M Return %": round(ret_3m,2)})
            
        df_res = pd.DataFrame(results).sort_values("3M Return %", ascending=False)
        last_update = pd.to_datetime(df['Date']).max().strftime('%d-%m-%Y')
        return f"<p><b>Data till:</b> {last_update}</p>" + df_res.to_html(classes='table', index=False, border=0)
    except Exception as e:
        return f"<p style='color:red'>Error: {e}</p>"

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
def menu(): return render_template_string(BASE + "<div class=container><h1>Menu</h1><a href=/dashboard class=btn>1. NSE Momentum Dashboard - Backtest</a><br><a href=/logout class=btn btn-danger>Logout</a></div>")
@app.route('/dashboard')
@login_required
def dashboard(): return render_template_string(BASE + f"<div class=container><h1>Top 5 NSE Momentum Stocks - Last 3 Months</h1>{get_momentum_data()}<br><a href=/menu class=btn>Back to Menu</a></div>")
@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
