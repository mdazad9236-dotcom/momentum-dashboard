import os
from flask import Flask, render_template_string, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import yfinance as yf
import time

app = Flask(__name__)
app.secret_key = 'momentum_secret_key_change_this_2026'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 1. USERS
USERS = {
    "azad": generate_password_hash("1234"),
    "admin": generate_password_hash("admin123")
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id in USERS else None

# 2. BIGGER UNIVERSE - NSE 100 + Midcap
NSE_UNIVERSE = [
    "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK", "HINDUNILVR", "INFY", "SBIN", "ITC", "KOTAKBANK",
    "LT", "AXISBANK", "BAJFINANCE", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "WIPRO",
    "POWERGRID", "HCLTECH", "BAJAJFINSV", "TECHM", "M&M", "TATASTEEL", "NTPC", "ADANIENT", "ADANIPORTS", "TATAMOTORS",
    "LEMON TREE", "LEMONTREE", "IRFC", "ZOMATO", "PAYTM", "NYKAA", "DMART", "TRENT", "PIDILITIND", "DIVISLAB"
]
NSE_UNIVERSE = [s.replace(" ", "") + ".NS" for s in NSE_UNIVERSE] #.NS add + space hatao

# 3. CSS SAME
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
:root{--bg:#f4f7fc;--card:#fff;--text:#1f2937;--primary:#2563eb}
body.dark{--bg:#111827;--card:#1f2937;--text:#f9fafb;--primary:#3b82f6}
body{font-family:'Poppins', sans-serif;background:var(--bg);color:var(--text);margin:0;padding:0}
.header{background:linear-gradient(90deg, var(--primary), #1d4ed8);color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center}
.container{max-width:1100px;margin:25px auto;background:var(--card);padding:25px;border-radius:16px}
.top-card{background:linear-gradient(135deg, #10b981, #059669);color:white;padding:20px;border-radius:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.table{width:100%;border-collapse:collapse;margin-top:15px}
.table th{background:var(--primary);color:white;padding:14px;text-align:left}
.table td{padding:12px;border-bottom:1px solid #e5e7eb}
.positive{color:#059669;font-weight:700}
.negative{color:#dc2626;font-weight:700}
.btn{background:var(--primary);color:white;padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-weight:600}
.btn-danger{background:#dc2626}.btn-success{background:#059669}
input{padding:10px;border-radius:8px;border:1px solid #ccc}
.chart{height:40px;width:100px}
.note-orange{color:#d97706;font-weight:600}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
function toggleDark(){document.body.classList.toggle('dark');localStorage.setItem('dark', document.body.classList.contains('dark'));}
window.onload = () => {if(localStorage.getItem('dark') === 'true') document.body.classList.add('dark');}
</script>
"""

# 4. DATA FUNCTION WITH WATCHLIST
def fetch_stock(symbol, period):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if len(hist) < 2: return None
        price = round(hist['Close'].iloc[-1], 2)
        ret = round(((price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100, 2)
        name = ticker.info.get('longName', symbol.replace(".NS",""))
        step = max(1, len(hist)//4)
        chart = [round(hist['Close'].iloc[i*step],2) for i in range(4)]
        return {"Stock": name, "Price": price, "Return %": ret, "Chart": chart, "Symbol": symbol}
    except:
        return None

def get_momentum_data(period="3mo", search="", watchlist=[]):
    period_map = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y"}
    p = period_map.get(period, "3mo")
    results = []
    note = "<p class='note-orange'><b>Note:</b> Live Data - " + period.upper() + "</p>"

    # 1. Pehle Watchlist ke stocks lao
    stocks_to_fetch = list(set(watchlist + NSE_UNIVERSE[:30])) # 30 tak hi, warna slow hoga

    for symbol in stocks_to_fetch:
        data = fetch_stock(symbol, p)
        if data: results.append(data)
        time.sleep(0.2) # block na ho isliye

    if search:
        search_symbol = search.replace(" ", "").upper() + ".NS"
        extra = fetch_stock(search_symbol, p)
        if extra and extra not in results: results.append(extra)

    results.sort(key=lambda x: x["Return %"], reverse=True)
    top = results[0] if results else {"Stock": "N/A", "Return %": 0}

    table_rows = ""
    for i,row in enumerate(results[:10]): # Top 10 dikhao
        color_class = "positive" if row['Return %'] > 0 else "negative"
        chart_data = ",".join(map(str,row["Chart"]))
        add_btn = f"<a href='/add/{row['Symbol']}' class='btn btn-success' style='padding:5px 10px;font-size:12px'>+ Watchlist</a>"
        table_rows += f"<tr><td>{row['Stock']} {add_btn}</td><td>₹{row['Price']}</td><td class='{color_class}'>{row['Return %']}%</td><td><canvas id='chart{i}' class='chart'></canvas></td></tr><script>new Chart(document.getElementById('chart{i}'), {{type: 'line',data: {{labels:['','','',''], datasets:[{{data:[{chart_data}], borderColor:'#10b981', borderWidth:2, fill:false, tension:0.4}}]}},options:{{plugins:{{legend:{{display:false}}}}, scales:{{x:{{display:false}},y:{{display:false}}}}}}}});</script>"

    table_html = f"<table class='table'><tr><th>Stock</th><th>Price</th><th>Return %</th><th>Trend</th></tr>{table_rows}</table>"
    last_update = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    return top, note + f"<p><b>Data till:</b> {last_update}</p>" + table_html

# 5. ROUTES
@app.route('/')
def home(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and check_password_hash(USERS[username], password):
            login_user(User(username))
            session['watchlist'] = []
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template_string(f"{BASE_CSS}<div class=container style='max-width:400px;margin-top:80px'><h1>Login</h1><form method=post><input type=text name=username placeholder=Username><input type=password name=password placeholder=Password><button class=btn style='width:100%;margin-top:10px'>Login</button></form></div>")

@app.route('/add/<symbol>')
@login_required
def add_watchlist(symbol):
    if 'watchlist' not in session: session['watchlist'] = []
    if symbol not in session['watchlist']:
        session['watchlist'].append(symbol)
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', '3mo')
    search = request.args.get('search', '')
    watchlist = session.get('watchlist', [])
    top_gainer, data_html = get_momentum_data(period, search, watchlist)

    return render_template_string(f"""{BASE_CSS}
    <div class="header"><h1>📈 Momentum Dashboard</h1><div><button onclick="toggleDark()" class="btn">🌙/☀️</button><a href=/logout class="btn btn-danger">Logout</a></div></div>
    <div class=container>
        <div class="top-card"><div><h2>Top Gainer - Last {period.upper()}</h2><p>{top_gainer['Stock']}</p></div><div style="font-size:28px;font-weight:700">{top_gainer['Return %']}%</div></div>
        <h1>Top Momentum Stocks</h1>
        <form method="get" style="display:flex;gap:10px;margin-bottom:20px">
            <select name="period" onchange="this.form.submit()" style="padding:8px;border-radius:6px">
                <option value="1mo" {"selected" if period=="1mo" else ""}>1 Month</option>
                <option value="3mo" {"selected" if period=="3mo" else ""}>3 Months</option>
                <option value="6mo" {"selected" if period=="6mo" else ""}>6 Months</option>
                <option value="1y" {"selected" if period=="1y" else ""}>1 Year</option>
            </select>
            <input type="text" name="search" placeholder="Search: LEMON TREE, IRFC..." value="{search}">
            <button class="btn">Search</button>
        </form>
        {data_html}
    </div>""")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
