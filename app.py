import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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

# 2. DEMO DATA with fake chart data
ALL_DEMO_DATA = {
    "1mo": [
        {"Stock": "HDFC Bank", "Price": 1680.25, "Return %": 5.2, "Chart": [1650,1660,1670,1680]},
        {"Stock": "Reliance Industries", "Price": 2980.10, "Return %": 4.1, "Chart": [2950,2960,2970,2980]},
        {"Stock": "TCS", "Price": 3850.50, "Return %": 3.8, "Chart": [3800,3820,3840,3850]},
        {"Stock": "Infosys", "Price": 1480.75, "Return %": 3.2, "Chart": [1450,1460,1470,1480]},
        {"Stock": "ICICI Bank", "Price": 1120.30, "Return %": 2.9, "Chart": [1100,1110,1115,1120]},
    ],
    "3mo": [
        {"Stock": "HDFC Bank", "Price": 1650.25, "Return %": 18.4, "Chart": [1400,1450,1550,1650]},
        {"Stock": "Reliance Industries", "Price": 2950.10, "Return %": 15.2, "Chart": [2560,2700,2850,2950]},
        {"Stock": "TCS", "Price": 3800.50, "Return %": 12.8, "Chart": [3370,3500,3650,3800]},
        {"Stock": "Infosys", "Price": 1450.75, "Return %": 10.5, "Chart": [1310,1360,1410,1450]},
        {"Stock": "ICICI Bank", "Price": 1100.30, "Return %": 9.3, "Chart": [1006,1040,1070,1100]},
    ],
    "6mo": [
        {"Stock": "Reliance Industries", "Price": 3100.10, "Return %": 25.6, "Chart": [2470,2650,2900,3100]},
        {"Stock": "HDFC Bank", "Price": 1720.25, "Return %": 22.1, "Chart": [1410,1500,1620,1720]},
        {"Stock": "TCS", "Price": 3950.50, "Return %": 19.4, "Chart": [3310,3500,3750,3950]},
        {"Stock": "ICICI Bank", "Price": 1180.30, "Return %": 17.8, "Chart": [1002,1060,1120,1180]},
        {"Stock": "Infosys", "Price": 1520.75, "Return %": 15.2, "Chart": [1320,1380,1450,1520]},
    ],
    "1y": [
        {"Stock": "TCS", "Price": 4100.50, "Return %": 42.8, "Chart": [2870,3200,3700,4100]},
        {"Stock": "Reliance Industries", "Price": 3300.10, "Return %": 38.9, "Chart": [2375,2600,3000,3300]},
        {"Stock": "HDFC Bank", "Price": 1850.25, "Return %": 35.4, "Chart": [1366,1500,1700,1850]},
        {"Stock": "Infosys", "Price": 1650.75, "Return %": 32.1, "Chart": [1250,1400,1550,1650]},
        {"Stock": "ICICI Bank", "Price": 1250.30, "Return %": 29.7, "Chart": [964,1050,1160,1250]},
    ]
}

# 3. CSS + DARK MODE + CHART CSS
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
:root{--bg:#f4f7fc;--card:#fff;--text:#1f2937;--muted:#6b7280;--primary:#2563eb}
body.dark{--bg:#111827;--card:#1f2937;--text:#f9fafb;--muted:#9ca3af;--primary:#3b82f6}
body{font-family:'Poppins', sans-serif;background:var(--bg);color:var(--text);margin:0;padding:0;transition:0.3s}
.header{background:linear-gradient(90deg, var(--primary), #1d4ed8);color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.container{max-width:1100px;margin:25px auto;background:var(--card);padding:25px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.08)}
.top-card{background:linear-gradient(135deg, #10b981, #059669);color:white;padding:20px;border-radius:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.top-card.value{font-size:28px;font-weight:700}
.controls{display:flex;gap:15px;align-items:center;margin-bottom:20px;flex-wrap:wrap}
.table{width:100%;border-collapse:collapse;margin-top:15px;border-radius:8px;overflow:hidden}
.table th{background:var(--primary);color:white;padding:14px;text-align:left;font-weight:600}
.table td{padding:12px;border-bottom:1px solid #e5e7eb}
body.dark.table td{border-bottom:1px solid #374151}
.table tr:hover{background:#eff6ff}
body.dark.table tr:hover{background:#374151}
.positive{color:#059669;font-weight:700}
.negative{color:#dc2626;font-weight:700}
.btn{background:var(--primary);color:white;padding:10px 20px;border-radius:8px;text-decoration:none;border:none;cursor:pointer;font-weight:600}
.btn:hover{opacity:0.9}
.btn-danger{background:#dc2626}
input[type=text]{padding:10px;border-radius:8px;border:1px solid #ccc;width:250px}
body.dark input{background:#374151;border:1px solid #4b5563;color:var(--text)}
.chart{height:40px;width:100px}
.note-green{color:#059669;font-weight:600}
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

# 4. DATA FUNCTION
def get_momentum_data(period="3mo", search=""):
    results = ALL_DEMO_DATA.get(period, ALL_DEMO_DATA["3mo"])
    if search:
        results = [r for r in results if search.lower() in r["Stock"].lower()]
    results.sort(key=lambda x: x["Return %"], reverse=True)
    top = results[0] if results else {"Stock": "N/A", "Return %": 0}

    table_rows = ""
    for i,row in enumerate(results):
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
    note = f"<p class='note-green'><b>Note:</b> Demo Data - {period.upper()}</p>"
    last_update = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    return top, note + f"<p><b>Data till:</b> {last_update}</p>" + table_html

# 5. ROUTES
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
