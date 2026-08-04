import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
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

# 2. NSE TOP 50
NSE_TOP_50 = ["RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK", "HINDUNILVR", "INFY", "SBIN", "ITC", "KOTAKBANK"]

# 3. FALLBACK DEMO DATA
FALLBACK_DATA = {
    "1mo": [{"Stock": "HDFC Bank", "Price": 1680.25, "Return %": 5.2, "Chart": [1650,1660,1670,1680]}],
    "3mo": [{"Stock": "HDFC Bank", "Price": 1650.25, "Return %": 18.4, "Chart": [1400,1450,1550,1650]}],
    "6mo": [{"Stock": "Reliance Industries", "Price": 3100.10, "Return %": 25.6, "Chart": [2470,2650,2900,3100]}],
    "1y": [{"Stock": "TCS", "Price": 4100.50, "Return %": 42.8, "Chart": [2870,3200,3700,4100]}]
}
for k in FALLBACK_DATA:
    FALLBACK_DATA[k] = FALLBACK_DATA[k] * 5 # 5 stocks banane ke liye

# 4. CSS SAME AS BEFORE
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
:root{--bg:#f4f7fc;--card:#fff;--text:#1f2937;--muted:#6b7280;--primary:#2563eb}
body.dark{--bg:#111827;--card:#1f2937;--text:#f9fafb;--muted:#9ca3af;--primary:#3b82f6}
body{font-family:'Poppins', sans-serif;background:var(--bg);color:var(--text);margin:0;padding:0;transition:0.3s}
.header{background:linear-gradient(90deg, var(--primary), #1d4ed8);color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center}
.container{max-width:1100px;margin:25px auto;background:var(--card);padding:25px;border-radius:16px}
.top-card{background:linear-gradient(135deg, #10b981, #059669);color:white;padding:20px;border-radius:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.top-card.value{font-size:28px;font-weight:700}
.controls{display:flex;gap:15px;align-items:center;margin-bottom:20px;flex-wrap:wrap}
.table{width:100%;border-collapse:collapse;margin-top:15px;border-radius:8px;overflow:hidden}
.table th{background:var(--primary);color:white;padding:14px;text-align:left;font-weight:600}
.table td{padding:12px;border-bottom:1px solid #e5e7eb}
.positive{color:#059669;font-weight:700}
.negative{color:#dc2626;font-weight:700}
.btn{background:var(--primary);color:white;padding:10px 20px;border-radius:8px;text-decoration:none;border:none;cursor:pointer;font-weight:600}
.btn-danger{background:#dc2626}
input[type=text]{padding:10px;border-radius:8px;border:1px solid #ccc;width:250px}
body.dark input{background:#374151;border:1px solid #4b5563;color:var(--text)}
.chart{height:40px;width:100px}
.note-green{color:#059669;font-weight:600}.note-orange{color:#d97706;font-weight:600}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
function toggleDark(){
    document.body.classList.toggle('dark');
    localStorage.setItem('dark', document.body.classList.contains('dark'));
}
window.onload = () => {
    if(localStorage.getItem('dark') === 'true') document.body.classList.add('dark');
}
</script>
"""

# 5. REAL DATA FUNCTION
def get_momentum_data(period="3mo", search=""):
    period_map = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y"}
    p = period_map.get(period, "3mo")
    results = []
    note_class = "note-green"
    note_text = "Live Data"

    try:
        for symbol in NSE_TOP_50:
            try:
                ticker = yf.Ticker(symbol + ".NS")
                hist = ticker.history(period=p)
                if len(hist) < 5: continue

                price = round(hist['Close'].iloc[-1], 2)
                price_start = hist['Close'].iloc[0]
                ret = round(((price - price_start) / price_start) * 100, 2)
                name = ticker.info.get('longName', symbol)

                # Chart ke liye 4 points
                step = len(hist)//4
                chart = [round(hist['Close'].iloc[i*step],2) for i in range(4)]

                results.append({"Stock": name, "Price": price, "Return %": ret, "Chart": chart})
                time.sleep(0.3) # Rate limit se bachne ke liye
            except:
                continue

        if len(results) < 3: # Agar 3 se kam aaye to fallback
            raise Exception("Not enough data")

    except:
        results = FALLBACK_DATA[p]
        note_class = "note-orange"
        note_text = "Demo Data - API Slow hai"

    if search:
        results = [r for r in results if search.lower() in r["Stock"].lower()]

    results.sort(key=lambda x: x["Return %"], reverse=True)
    top = results[0] if results else {"Stock": "N/A", "Return %": 0}

    table_rows = ""
    for i,row in enumerate(results[:5]):
        color_class = "positive" if row['Return %'] > 0 else "negative"
        chart_data = ",".join(map(str,row["Chart"]))
        table_rows += f"""
        <tr>
            <td>{row['Stock']}</td>
            <td>₹{row['Price']}</td>
            <td class='{color_class}'>{row['Return %']}%</td>
            <td><canvas id="chart{i}" class="chart"></canvas></td>
        </tr>
        <script>
        new Chart(document.getElementById('chart{i}'), {{
            type: 'line',
            data: {{labels:['','','',''], datasets:[{{data:[{chart_data}], borderColor:'#10b981', borderWidth:2, fill:false, tension:0.4}}]}},
            options:{{plugins:{{legend:{{display:false}}}}, scales:{{x:{{display:false}},y:{{display:false}}}}}}
        }});
        </script>
        """

    table_html = f"<table class='table'><tr><th>Stock</th><th>Price</th><th>Return %</th><th>Trend</th></tr>{table_rows}</table>"
    note = f"<p class='{note_class}'><b>Note:</b> {note_text} - {period.upper()}</p>"
    last_update = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    return top, note + f"<p><b>Data till:</b> {last_update}</p>" + table_html

# 6. ROUTES SAME
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and check_password_hash(USERS[username], password):
            user = User(username)
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template_string(f"{BASE_CSS}<div class=container style='max-width:400px;margin-top:80px'><h1>Login</h1><form method=post><input type=text name=username placeholder=Username><input type=password name=password placeholder=Password><button class=btn style='width:100%;margin-top:10px'>Login</button></form></div>")

@app.route('/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', '3mo')
    search = request.args.get('search', '')
    top_gainer, data_html = get_momentum_data(period, search)

    return render_template_string(f"""{BASE_CSS}
    <div class="header">
        <h1>📈 Momentum Dashboard</h1>
        <div>
            <button onclick="toggleDark()" class="btn">🌙/☀️</button>
            <a href=/logout class="btn btn-danger">Logout</a>
        </div>
    </div>
    <div class=container>
        <div class="top-card">
            <div><h2>Top Gainer - Last {period.upper()}</h2><p>{top_gainer['Stock']}</p></div>
            <div class="value">{top_gainer['Return %']}%</div>
        </div>

        <h1>Top 5 NSE Momentum Stocks</h1>

        <form method="get" class="controls">
            <select name="period" onchange="this.form.submit()" style="padding:8px;border-radius:6px">
                <option value="1mo" {"selected" if period=="1mo" else ""}>1 Month</option>
                <option value="3mo" {"selected" if period=="3mo" else ""}>3 Months</option>
                <option value="6mo" {"selected" if period=="6mo" else ""}>6 Months</option>
                <option value="1y" {"selected" if period=="1y" else ""}>1 Year</option>
            </select>
            <input type="text" name="search" placeholder="Search Stock..." value="{search}">
            <button class="btn">Search</button>
        </form>

        {data_html}
        <br>
        <a href=/dashboard class=btn>🔄 Refresh</a>
    </div>""")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
