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

# 2. DEMO DATA - Yahi data use hoga. API ki tension nahi
# Maine isme 1M, 3M, 6M, 1Y ke liye data bana diya
ALL_DEMO_DATA = {
    "1mo": [
        {"Stock": "HDFC Bank", "Price": 1680.25, "Return %": 5.2},
        {"Stock": "Reliance Industries", "Price": 2980.10, "Return %": 4.1},
        {"Stock": "TCS", "Price": 3850.50, "Return %": 3.8},
        {"Stock": "Infosys", "Price": 1480.75, "Return %": 3.2},
        {"Stock": "ICICI Bank", "Price": 1120.30, "Return %": 2.9},
    ],
    "3mo": [
        {"Stock": "HDFC Bank", "Price": 1650.25, "Return %": 18.4},
        {"Stock": "Reliance Industries", "Price": 2950.10, "Return %": 15.2},
        {"Stock": "TCS", "Price": 3800.50, "Return %": 12.8},
        {"Stock": "Infosys", "Price": 1450.75, "Return %": 10.5},
        {"Stock": "ICICI Bank", "Price": 1100.30, "Return %": 9.3},
    ],
    "6mo": [
        {"Stock": "Reliance Industries", "Price": 3100.10, "Return %": 25.6},
        {"Stock": "HDFC Bank", "Price": 1720.25, "Return %": 22.1},
        {"Stock": "TCS", "Price": 3950.50, "Return %": 19.4},
        {"Stock": "ICICI Bank", "Price": 1180.30, "Return %": 17.8},
        {"Stock": "Infosys", "Price": 1520.75, "Return %": 15.2},
    ],
    "1y": [
        {"Stock": "TCS", "Price": 4100.50, "Return %": 42.8},
        {"Stock": "Reliance Industries", "Price": 3300.10, "Return %": 38.9},
        {"Stock": "HDFC Bank", "Price": 1850.25, "Return %": 35.4},
        {"Stock": "Infosys", "Price": 1650.75, "Return %": 32.1},
        {"Stock": "ICICI Bank", "Price": 1250.30, "Return %": 29.7},
    ]
}

# 3. CSS
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
body{font-family:'Poppins', sans-serif;background:#f4f7fc;margin:0;padding:0}
.header{background:linear-gradient(90deg, #2563eb, #1d4ed8);color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.header h1{margin:0;font-size:20px}
.container{max-width:1100px;margin:25px auto;background:white;padding:25px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.08)}
.top-card{background:linear-gradient(135deg, #10b981, #059669);color:white;padding:20px;border-radius:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.top-card h2{margin:0;font-size:18px}
.top-card.value{font-size:28px;font-weight:700}
.table{width:100%;border-collapse:collapse;margin-top:15px;border-radius:8px;overflow:hidden}
.table th{background:#2563eb;color:white;padding:14px;text-align:left;font-weight:600}
.table td{padding:12px;border-bottom:1px solid #e5e7eb}
.table tr:hover{background:#eff6ff}
.positive{color:#059669;font-weight:700}
.negative{color:#dc2626;font-weight:700}
.btn{background:#2563eb;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;border:none;cursor:pointer;font-weight:600;margin-right:10px}
.btn:hover{background:#1d4ed8}
.btn-danger{background:#dc2626}.btn-danger:hover{background:#b91c1c}
.note-green{color:#059669;font-weight:600}
@media(max-width:768px){.container{margin:10px;padding:15px}}
</style>
"""

# 4. DATA FUNCTION
def get_momentum_data(period="3mo"):
    results = ALL_DEMO_DATA.get(period, ALL_DEMO_DATA["3mo"])
    results.sort(key=lambda x: x["Return %"], reverse=True)
    top = results[0]

    table_rows = ""
    for row in results:
        color_class = "positive" if row['Return %'] > 0 else "negative"
        table_rows += f"<tr><td>{row['Stock']}</td><td>₹{row['Price']}</td><td class='{color_class}'>{row['Return %']}%</td></tr>"

    table_html = f"<table class='table'><tr><th>Stock</th><th>Price</th><th>Return %</th></tr>{table_rows}</table>"
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
    login_page = f"""{BASE_CSS}
    <div class=container style="max-width:400px;margin-top:80px">
        <h1>Login</h1>
        <form method="post">
            <input type=text name=username placeholder=Username style="width:100%;padding:10px;margin:10px 0;border-radius:6px;border:1px solid #ccc">
            <input type=password name=password placeholder=Password style="width:100%;padding:10px;margin:10px 0;border-radius:6px;border:1px solid #ccc">
            <button class=btn style="width:100%">Login</button>
        </form>
    </div>"""
    return render_template_string(login_page)

@app.route('/menu')
@login_required
def menu():
    menu_page = f"""{BASE_CSS}
    <div class="header">
        <h1>📊 Main Menu</h1>
        <a href=/logout class="btn btn-danger">Logout</a>
    </div>
    <div class=container>
        <h1>Welcome {current_user.id}</h1>
        <a href=/dashboard class=btn>📈 Go to Momentum Dashboard</a>
    </div>"""
    return render_template_string(menu_page)

@app.route('/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', '3mo')
    top_gainer, data_html = get_momentum_data(period)

    dashboard_page = f"""{BASE_CSS}
    <div class="header">
        <h1>📈 Momentum Dashboard</h1>
        <a href=/logout class="btn btn-danger">Logout</a>
    </div>
    <div class=container>
        <div class="top-card">
            <div>
                <h2>Top Gainer - Last {period.upper()}</h2>
                <p>{top_gainer['Stock']}</p>
            </div>
            <div class="value">{top_gainer['Return %']}%</div>
        </div>

        <h1>Top 5 NSE Momentum Stocks</h1>

        <form method="get" style="margin-bottom:20px">
            <label><b>Timeframe:</b> </label>
            <select name="period" onchange="this.form.submit()" style="padding:8px;border-radius:6px;border:1px solid #ccc">
                <option value="1mo" {"selected" if period=="1mo" else ""}>1 Month</option>
                <option value="3mo" {"selected" if period=="3mo" else ""}>3 Months</option>
                <option value="6mo" {"selected" if period=="6mo" else ""}>6 Months</option>
                <option value="1y" {"selected" if period=="1y" else ""}>1 Year</option>
            </select>
        </form>

        {data_html}
        <br>
        <a href=/dashboard class=btn>🔄 Refresh Data</a>
        <a href=/menu class=btn>🏠 Back to Menu</a>
    </div>"""
    return render_template_string(dashboard_page)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
