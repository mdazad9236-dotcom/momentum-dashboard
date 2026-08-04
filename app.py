    from flask import Flask, render_template_string, request, redirect, url_for
    from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
    from werkzeug.security import generate_password_hash, check_password_hash
    import yfinance as yf
    import pandas as pd
    from datetime import datetime

    app = Flask(__name__)
    app.secret_key = 'momentum_secret_key_123_change_kar_dena'

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    # YAHAN APNE USERS ADD KAR - username: password
    USERS = {
        "azad": generate_password_hash("1234"),
        "rahul": generate_password_hash("5678"),
    }

    class User(UserMixin):
        def __init__(self, id):
            self.id = id

    @login_manager.user_loader
    def load_user(user_id):
        return User(user_id)

    NIFTY_50 = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS","BHARTIARTL.NS", "SBIN.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS","AXISBANK.NS", "HCLTECH.NS", "ASIANPAINT.NS", "MARUTI.NS", "BAJFINANCE.NS","ADANIPORTS.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "NESTLEIND.NS","WIPRO.NS", "ONGC.NS", "POWERGRID.NS", "NTPC.NS", "JSWSTEEL.NS"]

    def get_rsi(data, period=14):
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs.iloc[-1]))

    def get_momentum_data(symbol):
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
            if len(hist) < 20: return None
            current_price = hist['Close'].iloc[-1]
            price_1m_ago = hist['Close'].iloc[-21] if len(hist) >= 21 else hist['Close'].iloc[0]
            low_3m = hist['Low'].min()
            momentum_1m = ((current_price - price_1m_ago) / price_1m_ago) * 100
            from_low = ((current_price - low_3m) / low_3m) * 100
            rsi = get_rsi(hist)
            score = (momentum_1m * 0.5) + (from_low * 0.3) + ((rsi-30) * 0.2)
            return {"symbol": symbol.replace(".NS",""), "price": round(current_price,2), "momentum_1m": round(momentum_1m,2), "from_low": round(from_low,2), "rsi": round(rsi,2), "score": round(score,2)}
        except: return None

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            if username in USERS and check_password_hash(USERS[username], password):
                login_user(User(username))
                return redirect(url_for('menu'))
        return '<body style="background:#0e1117;color:white;font-family:Arial;text-align:center;padding-top:100px;"><h2>🔒 Login</h2><form method="post"><input name="username" placeholder="Username"><br><br><input name="password" type="password" placeholder="Password"><br><br><button>Login</button></form></body>'

    @app.route('/menu')
    @login_required
    def menu():
        return f'<body style="background:#0e1117;color:white;font-family:Arial;padding:20px;"><h1>Welcome {current_user.id} 👑</h1><a href="/dashboard" style="color:gold;">1. Momentum Dashboard</a><br><br><a href="/logout" style="color:red;">Logout</a></body>'

    @app.route('/dashboard')
    @login_required
    def dashboard():
        all_data = []
        for sym in NIFTY_50:
            data = get_momentum_data(sym)
            if data: all_data.append(data)
        top_25 = sorted(all_data, key=lambda x: x['score'], reverse=True)[:25]
        html = """<body style="background:#0e1117;color:white;font-family:Arial;padding:20px;"><a href="/menu" style="color:gold;">← Back to Menu</a><h1>🚀 Top 25 Momentum Stocks</h1><p>Last Updated: {{time}}</p><table width="100%"><tr><th>Rank</th><th>Stock</th><th>Price</th><th>Score</th></tr>{% for i, s in enumerate(top_25) %}<tr><td>{{i+1}}</td><td><b>{{s.symbol}}</b></td><td>{{s.price}}</td><td>{{s.score}}</td></tr>{% endfor %}</table></body>"""
        return render_template_string(html, top_25=top_25, enumerate=enumerate, time=datetime.now().strftime("%H:%M:%S"))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)
