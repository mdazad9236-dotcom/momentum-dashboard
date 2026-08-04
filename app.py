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
body{font-family:'Segoe UI', sans-serif;background:#eef2f7;margin:0;padding:20px}
.container{max-width:950px;margin:20px auto;background:white;padding:25px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1)}
h1,h2{color:#1a365d}
.table{width:100%;border-collapse:collapse;margin-top:15px}
.table th{background:#2563eb;color:white;padding:12px;text-align:left;font-size:15px}
.table td{padding:10px;border-bottom:1px solid #e2e8f0}
.table tr:hover{background:#f1f7ff}
.btn{background:#2563eb;color:white;padding:10px 18px;border-radius:6px;text-decoration:none;border:none;cursor:pointer;display:inline-block;margin:5px 0;font-weight:600}
.btn:hover{background:#1d4ed8}
.btn-danger{background:#dc2626}.btn-danger:hover{background:#b91c1c}
.flash{background:#fef3c7;color:#92400e;padding:10px;border-radius:5px;margin-bottom:15px}
.note-green{color:green;font-weight:600}.note-orange{color:orange;font-weight:600}
input{padding:10px;width:95%;border:1px solid #ccc;border-radius:5px;margin-bottom:10px}
</style>
"""

# 5. CORE LOGIC - DATA FETCH
def get_momentum_data():
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    for symbol in NSE_TOP_50:
        try:
            # Step 1: NSE cookie lena zaroori hai
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=headers, timeout=5)

            # Step 2: Stock data lena
            url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
            r = session.get(url, headers=headers, timeout=5).json()

            name = r['info']['companyName']
            price = float(r['priceInfo']['lastPrice'])
            ret_3m = r['priceInfo'].get('pChange3M', 0) # 3 Month change

            results.append({"Stock": name, "Price": round(price,2), "3M Return %": round(ret_3m,2)})
        except:
            continue # Ek stock fail hua to dusra try karo

    # Agar API se data nahi aaya to Demo data
    if len(results) < 3:
        results = DUMMY_DATA
        note = "<p class='note-orange'><b>Note:</b> Live API slow/block hai. Demo data dikh raha hai</p>"
    else:
        note = "<p class='note-green'><b>Note:</b> Live NSE Data</p>"

    df_res = pd.DataFrame(results).sort_values("3M Return %", ascending=False).head(5)
    last_update = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    table_html = df_res.to_html(classes='table', index=False, border=0)
    return note + f"<p><b>Data till:</b> {last_update}</p>" + table_html

# 6. ROUTES
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and check_password_hash(USERS[username], password):
            login_user(User(username))
            return redirect(url_for('menu'))
        flash('Galat Username ya Password')

    login_form = f"{BASE_CSS}<div class=container><h2>Login to Momentum Dashboard</h2><form method=post><input name=username placeholder='Username: azad' required><br><input name=password type=password placeholder='Password: 1234' required><br><button class=btn>Login</button></form></div>"
    return render_template_string(login_form)

@app.route('/menu')
@login_required
def menu():
    menu_page = f"{BASE_CSS}<div class=container><h1>Welcome {current_user.id}</h1><h2>Main Menu</h2><a href=/dashboard class=btn>1. NSE Momentum Dashboard</a><br><a href=/logout class=btn btn-danger>Logout</a></div>"
    return render_template_string(menu_page)

@app.route('/dashboard')
@login_required
def dashboard():
    data_html = get_momentum_data()
    dashboard_page = f"{BASE_CSS}<div class=container><h1>Top 5 NSE Momentum Stocks - Last 3 Months</h1>{data_html}<br><a href=/dashboard class=btn>Refresh Data</a><a href=/menu class=btn>Back to Menu</a></div>"
    return render_template_string(dashboard_page)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
