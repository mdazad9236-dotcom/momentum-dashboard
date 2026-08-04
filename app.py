import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'momentum_secret_key_change_this_2026' # Isko change kar dena

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 1. USERS - Baad me database se jod dena
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

# 2. NSE TOP 50 STOCKS LIST
NSE_TOP_50 = ["RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK", "HINDUNILVR", "INFY", "SBIN", "ITC", "KOTAKBANK",
              "HCLTECH", "LT", "ASIANPAINT", "MARUTI", "AXISBANK", "BAJFINANCE", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO"]

# 3. DEMO DATA - API fail hone par ye chalega
DUMMY_DATA = [
    {"Stock": "HDFC Bank", "Price": 1650.25, "3M Return %": 18.4},
    {"Stock": "Reliance Industries", "Price": 2950.10, "3M Return %": 15.2},
    {"Stock": "TCS", "Price": 3800.50, "3M Return %": 12.8},
    {"Stock": "Infosys", "Price": 1450.75, "3M Return %": 10.5},
    {"Stock": "ICICI Bank", "Price": 1100.30, "3M Return %": 9.3},
]

# 4. CSS - Better UI
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
body{font-family:'Poppins', sans-serif;background:#f4f7fc;margin:0;padding:0}
.header{background:linear-gradient(90deg, #2563eb, #1d4ed8);color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.header h1{margin:0;font-size:20px}
.container{max-width:1100px;margin:25px auto;background:white;padding:25px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.08)}
.top-card{background:linear-gradient(135deg, #10b981, #059669);color:white;padding:20px;border-radius:12px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.top-card h2{margin:0;font-size:18px}
.top-card .value{font-size:28px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;margin-bottom:25px}
.stat-card{background:#f9fafb;padding:15px;border-radius:10px;border-left:4px solid #2563eb}
.stat-card .label{color:#6b7280;font-size:13px}
.stat-card .value{font-size:20px;font-weight:700;color:#1f2937}
.table{width:100%;border-collapse:collapse;margin-top:15px;border-radius:8px;overflow:hidden}
.table th{background:#2563eb;color:white;padding:14px;text-align:left;font-weight:600}
.table td{padding:12px;border-bottom:1px solid #e5e7eb}
.table tr:hover{background:#eff6ff}
.positive{color:#059669;font-weight:700}
.negative{color:#dc2626;font-weight:700}
.btn{background:#2563eb;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;border:none;cursor:pointer;font-weight:600;margin-right:10px}
.btn:hover{background:#1d4ed8}
.btn-danger{background:#dc2626}.btn-danger:hover{background:#b91c1c}
.note-green{color:#059669;font-weight:600}.note-orange{color:#d97706;font-weight:600}
.loader{border:4px solid #f3f3f3;border-top:4px solid #2563eb;border-radius:50%;width:30px;height:30px;animation:spin 1s linear infinite;margin:20px auto}
@keyframes spin {0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); }}
@media(max-width:768px){.container{margin:10px;padding:15px}}
</style>
"""

# 5. CORE LOGIC - DATA FETCH
@app.route('/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', '3mo') # URL se period lega?period=1mo
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
# 6. ROUTES
@app.route('/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', '3mo') # URL se period lega?period=1mo
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
