import os
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import yfinance as yf
import time
import csv
import io

app = Flask(__name__)
app.secret_key = 'momentum_secret_key_change_this_2026'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# USERS
USERS = {"azad": generate_password_hash("1234"), "admin": generate_password_hash("admin123")}

class User(UserMixin):
    def __init__(self, id): self.id = id
@login_manager.user_loader
def load_user(user_id): return User(user_id) if user_id in USERS else None

# NSE UNIVERSE
NSE_UNIVERSE = ["RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK", "HINDUNILVR", "INFY", "SBIN", "ITC", "KOTAKBANK",
"LT", "AXISBANK", "BAJFINANCE", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "WIPRO",
"LEMON TREE", "LEMONTREE", "IRFC", "ZOMATO", "PAYTM", "NYKAA", "DMART", "TRENT", "PIDILITIND", "DIVISLAB"]
NSE_UNIVERSE = [s.replace(" ", "") + ".NS" for s in NSE_UNIVERSE]

# CSS
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
:root{--bg:#f4f7fc;--card:#fff;--text:#1f2937;--primary:#2563eb}
body.dark{--bg:#111827;--card:#1f2937;--text:#f9fafb;--primary:#3b82f6}
body{font-family:'Poppins', sans-serif;background:var(--bg);color:var(--text);margin:0}
.header{background:linear-gradient(90deg, var(--primary), #1d4ed8);color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center}
.container{max-width:1100px;margin:25px auto;background:var(--card);padding:25px;border-radius:16px}
.top-card{background:linear-gradient(135deg, #10b981, #059669);color:white;padding:20px;border-radius:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.table{width:100%;border-collapse:collapse;margin-top:15px}
.table th{background:var(--primary);color:white;padding:14px;text-align:left}
.table td{padding:12px;border-bottom:1px solid #e5e7eb}
.table tr:hover{background:#f3f4f6} body.dark.table tr:hover{background:#374151}
.positive{color:#059669;font-weight:700}.negative{color:#dc2626;font-weight:700}
.btn{background:var(--primary);color:white;padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-weight:600;text-decoration:none}
.btn-danger{background:#dc2626}.btn-success{background:#059669}.btn-orange{background:#d97706}
input{padding:10px;border-radius:8px;border:1px solid #ccc} body.dark input{background:#374151;border:1px solid #4b5563;color:var(--text)}
.chart{height:40px;width:100px} a{color:var(--primary);text-decoration:none;font-weight:600}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
function toggleDark(){document.body.classList.toggle('dark');localStorage.setItem('dark', document.body.classList.contains('dark'));}
window.onload = () => {if(localStorage.getItem('dark') === 'true') document.body.classList.add('dark');}
</script>
"""

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
    except: return None

def get_momentum_data(period="3mo", search="", watchlist=[]):
    p = period
    results = []
    stocks_to_fetch = list(set(watchlist + NSE_UNIVERSE[:15])) # 30 se 15 kiya, speed ke liye
    
    for symbol in stocks_to_fetch:
        data = fetch_stock(symbol, p)
        if data: results.append(data)
        time.sleep(0.1)

    # Agar data nahi mila to Demo data dikhao
    if not results:
        demo = [
            {"Stock": "RELIANCE", "Price": 2980, "Return %": 15.2, "Chart": [2600,2750,2900,2980], "Symbol": "RELIANCE.NS"},
            {"Stock": "LEMON TREE HOTEL", "Price": 145, "Return %": 22.5, "Chart": [110,120,135,145], "Symbol": "LEMONTREE.NS"},
            {"Stock": "IRFC", "Price": 88, "Return %": 18.1, "Chart": [70,75,85,88], "Symbol": "IRFC.NS"},
        ]
        results = demo
    
    results.sort(key=lambda x: x["Return %"], reverse=True)
    top = results[0] if results else {"Stock": "N/A", "Return %": 0}
    
    # Baki code same
    table_rows = ""
    for i,row in enumerate(results[:10]):
        color_class = "positive" if row['Return %'] > 0 else "negative"
        chart_data = ",".join(map(str,row["Chart"]))
        add_btn = f"<a href='/add/{row['Symbol']}' class='btn btn-success' style='padding:5px 10px;font-size:12px'>+ Watchlist</a>"
        stock_link = f"<a href='/stock/{row['Symbol']}'>{row['Stock']}</a>"
        table_rows += f"<tr><td>{stock_link} {add_btn}</td><td>₹{row['Price']}</td><td class='{color_class}'>{row['Return %']}%</td><td><canvas id='chart{i}' class='chart'></canvas></td></tr><script>new Chart(document.getElementById('chart{i}'), {{type: 'line',data: {{labels:['','','',''], datasets:[{{data:[{chart_data}], borderColor:'#10b981', borderWidth:2, fill:false, tension:0.4}}]}},options:{{plugins:{{legend:{{display:false}}}}, scales:{{x:{{display:false}},y:{{display:false}}}}}}}});</script>"
    table_html = f"<table class='table'><tr><th>Stock</th><th>Price</th><th>Return %</th><th>Trend</th></tr>{table_rows}</table>"
    last_update = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    return top, f"<p><b>Data till:</b> {last_update}</p>" + table_html, results

# ROUTES
@app.route('/')
def home(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and check_password_hash(USERS[username], password):
            login_user(User(username))
            if 'watchlist' not in session: session['watchlist'] = []
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template_string(f"{BASE_CSS}<div class=container style='max-width:400px;margin-top:80px'><h1>Login</h1><form method=post><input type=text name=username placeholder=Username><input type=password name=password placeholder=Password><button class=btn style='width:100%;margin-top:10px'>Login</button></form></div>")

@app.route('/add/<symbol>')
@login_required
def add_watchlist(symbol):
    if symbol not in session['watchlist']: session['watchlist'].append(symbol)
    return redirect(url_for('dashboard'))

@app.route('/stock/<symbol>')
@login_required
def stock_detail(symbol):
    data = fetch_stock(symbol, "1y")
    if not data: return "Stock not found"
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="1y")
    chart_data = ",".join(map(str, [round(x,2) for x in hist['Close'][-60:]])) # last 60 days

    return render_template_string(f"""{BASE_CSS}
    <div class="header"><h1>📊 {data['Stock']}</h1><a href=/dashboard class=btn>Back</a></div>
    <div class=container>
        <h2>Price: ₹{data['Price']} <span class='{'positive' if data['Return %']>0 else 'negative'}'>{data['Return %']}% 1Y</span></h2>
        <canvas id="bigChart" style="height:400px"></canvas>
        <script>
        new Chart(document.getElementById('bigChart'), {{
            type: 'line',
            data: {{labels:[], datasets:[{{label:'Price',data:[{chart_data}], borderColor:'#2563eb', borderWidth:2, fill:true}}]}},
            options:{{responsive:true, maintainAspectRatio:false}}
        }});
        </script>
    </div>""")

@app.route('/export')
@login_required
def export_csv():
    period = request.args.get('period', '3mo')
    _, _, results = get_momentum_data(period, "", session.get('watchlist', []))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Stock', 'Price', 'Return %'])
    for r in results: cw.writerow([r['Stock'], r['Price'], r['Return %']])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-disposition":"attachment; filename=momentum_data.csv"})

@app.route('/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', '3mo')
    search = request.args.get('search', '')
    watchlist = session.get('watchlist', [])
    top_gainer, data_html, _ = get_momentum_data(period, search, watchlist)

    return render_template_string(f"""{BASE_CSS}
    <div class="header"><h1>📈 Momentum Dashboard</h1><div><button onclick="toggleDark()" class="btn">🌙/☀️</button><a href=/logout class="btn btn-danger">Logout</a></div></div>
    <div class=container>
        <div class="top-card"><div><h2>Top Gainer - Last {period.upper()}</h2><p>{top_gainer['Stock']}</p></div><div style="font-size:28px;font-weight:700">{top_gainer['Return %']}%</div></div>
        <h1>Top Momentum Stocks</h1>
        <form method="get" style="display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap">
            <select name="period" onchange="this.form.submit()" style="padding:8px;border-radius:6px">
                <option value="1mo" {"selected" if period=="1mo" else ""}>1 Month</option>
                <option value="3mo" {"selected" if period=="3mo" else ""}>3 Months</option>
                <option value="6mo" {"selected" if period=="6mo" else ""}>6 Months</option>
                <option value="1y" {"selected" if period=="1y" else ""}>1 Year</option>
            </select>
            <input type="text" name="search" placeholder="Search: LEMON TREE, IRFC..." value="{search}">
            <button class="btn">Search</button>
            <a href="/export?period={period}" class="btn btn-orange">📥 Export Excel</a>
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
