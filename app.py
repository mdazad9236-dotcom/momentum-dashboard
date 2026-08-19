import os
import threading
import time
import requests
from functools import wraps

from flask import Flask, jsonify, render_template, request, redirect, url_for, session

from angel_instruments import AngelInstrumentManager
from angel_service import AngelOneService
from stock_service import StockService
from angel_scanner import AngelScanner

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "x10-marketai-session-key-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "false").lower() == "true"

angel_service = AngelOneService()
stock_service = StockService()
instrument_manager = AngelInstrumentManager()

APP_USER_ID = "Admin"
APP_PASSWORD = "Admin"

SCAN_REFRESH_SECONDS = max(60, int(os.getenv("X10_SCAN_REFRESH_SECONDS", "180")))
_scan_lock = threading.Lock()
_scan_state = {"result": None, "updated_at": 0.0, "refreshing": False, "last_error": None}


def is_authenticated():
    return session.get("authenticated") is True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "authenticated": False, "message": "Authentication required."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def clean_stock(stock):
    fields = ["symbol", "name", "token", "price", "technical_score", "x10_score", "success_probability", "signal", "entry", "entry_low", "entry_high", "stop_loss", "target", "target_1", "target_2", "risk", "reward", "risk_reward", "trailing_stop", "chase_price", "dont_chase", "setup_quality", "trend", "momentum", "rsi", "ema20", "ema50", "ema200", "macd", "macd_signal", "macd_histogram", "adx", "plus_di", "minus_di", "support", "resistance", "volume_ratio", "atr", "52_week_high", "52_week_low", "scan_time"]
    return {field: stock.get(field, 0) for field in fields}


def _run_market_scan():
    with _scan_lock:
        if _scan_state["refreshing"]:
            return False
        _scan_state["refreshing"] = True
    started = time.time()
    try:
        scanner = AngelScanner(batch_size=5, delay=0.03, max_workers=5)
        result = scanner.scan_market(limit=30)
        if not result.get("success"):
            raise RuntimeError(result.get("message", "Angel One scanner failed."))
        stocks = [clean_stock(stock) for stock in result.get("stocks", []) if isinstance(stock, dict)]
        payload = {"success": True, "message": "Market scan completed.", "count": len(stocks), "scanned": result.get("scanned", 0), "successful": result.get("successful", 0), "time_seconds": result.get("time_seconds", round(time.time() - started, 2)), "stocks": stocks, "indices": result.get("indices", []), "updated_at": time.time()}
        with _scan_lock:
            _scan_state["result"] = payload
            _scan_state["updated_at"] = payload["updated_at"]
            _scan_state["last_error"] = None
        return True
    except Exception as error:
        print("BACKGROUND X10 SCANNER ERROR:", error)
        with _scan_lock:
            _scan_state["last_error"] = str(error)
        return False
    finally:
        with _scan_lock:
            _scan_state["refreshing"] = False


def _ensure_scan_refresh(force=False):
    with _scan_lock:
        age = time.time() - _scan_state["updated_at"] if _scan_state["updated_at"] else None
        refreshing = _scan_state["refreshing"]
        stale = age is None or age >= SCAN_REFRESH_SECONDS
    if (force or stale) and not refreshing:
        threading.Thread(target=_run_market_scan, name="x10-market-scan", daemon=True).start()


def _snapshot_response():
    with _scan_lock:
        result = _scan_state["result"]
        updated_at = _scan_state["updated_at"]
        refreshing = _scan_state["refreshing"]
        last_error = _scan_state["last_error"]
    if result:
        payload = dict(result)
        payload["refreshing"] = refreshing
        payload["cache_age_seconds"] = round(max(0, time.time() - updated_at), 1)
        payload["stale"] = payload["cache_age_seconds"] >= SCAN_REFRESH_SECONDS
        return payload
    return {"success": True, "message": "Market scan is warming up in the background.", "count": 0, "scanned": 0, "successful": 0, "time_seconds": 0, "stocks": [], "indices": [], "refreshing": refreshing, "cache_age_seconds": None, "stale": True, "last_error": last_error}


def _background_refresh_loop():
    time.sleep(2)
    while True:
        try:
            _ensure_scan_refresh()
        except Exception as error:
            print("BACKGROUND REFRESH LOOP ERROR:", error)
        time.sleep(15)

threading.Thread(target=_background_refresh_loop, name="x10-refresh-loop", daemon=True).start()


@app.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        if request.form.get("user_id", "") == APP_USER_ID and request.form.get("password", "") == APP_PASSWORD:
            session.clear()
            session["authenticated"] = True
            session["user_id"] = APP_USER_ID
            return redirect(url_for("home"))
        error = "Invalid User ID or Password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/api/analyze/<symbol>")
@login_required
def analyze_stock(symbol):
    try:
        result = stock_service.get_stock_analysis(symbol.upper().strip())
        if not result:
            return jsonify({"success": False, "message": "No analysis result returned."}), 500
        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


@app.route("/api/scan")
@login_required
def scan():
    _ensure_scan_refresh()
    return jsonify(_snapshot_response())


@app.route("/api/scan/refresh")
@login_required
def scan_refresh():
    _ensure_scan_refresh(force=True)
    return jsonify({"success": True, "message": "X10 scan refresh started in background.", "refreshing": True})


@app.route("/api/indices")
@login_required
def indices_endpoint():
    _ensure_scan_refresh()
    snapshot = _snapshot_response()
    return jsonify({"success": True, "indices": snapshot.get("indices", []), "cached": True, "refreshing": snapshot.get("refreshing", False)})


@app.route("/api/historical/<symbol>")
@login_required
def historical_endpoint(symbol):
    try:
        stock = instrument_manager.find_stock(symbol.upper().strip())
        if not stock:
            return jsonify({"success": False, "message": "NSE equity symbol not found in Angel One instrument master."}), 404
        return jsonify(angel_service.get_historical_data(symbol=stock["symbol"], token=stock["token"], days=200, interval="ONE_DAY", exchange="NSE"))
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "data": []}), 500


@app.route("/api/instruments")
@login_required
def instruments_endpoint():
    try:
        result = instrument_manager.load_cache()
        if not result.get("success"):
            return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities()
        return jsonify({"success": True, "count": len(stocks), "stocks": stocks})
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "stocks": []}), 500


@app.route("/api/instruments/refresh")
@login_required
def refresh_instruments_endpoint():
    try:
        result = instrument_manager.refresh()
        if not result.get("success"):
            return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities()
        return jsonify({"success": True, "count": len(stocks), "message": "Angel One instrument master refreshed.", "stocks": stocks})
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "stocks": []}), 500


@app.route("/api/instrument/<symbol>")
@login_required
def instrument_endpoint(symbol):
    try:
        stock = instrument_manager.find_stock(symbol)
        if not stock:
            return jsonify({"success": False, "message": "Stock not found."}), 404
        return jsonify({"success": True, "stock": stock})
    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


@app.route("/api/ai-assistant", methods=["POST"])
@login_required
def ai_assistant():
    """Market-aware assistant. Uses the current X10 snapshot and OpenAI web search for fresh news."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return jsonify({"success": False, "message": "AI Assistant is not configured yet. Add OPENAI_API_KEY to the Render environment variables."}), 503

    body = request.get_json(silent=True) or {}
    question = str(body.get("message", "")).strip()
    if not question:
        return jsonify({"success": False, "message": "Please enter a stock or market question."}), 400
    if len(question) > 4000:
        question = question[:4000]

    snapshot = _snapshot_response()
    context = {
        "indices": snapshot.get("indices", []),
        "top_stocks": snapshot.get("stocks", [])[:12],
        "updated_at": snapshot.get("updated_at"),
    }
    system_prompt = """You are Azad AI Plus, a concise Indian stock-market research assistant. Answer questions about NSE/BSE stocks, indices, technical analysis, market structure, corporate developments and current market news. For anything time-sensitive, especially current news, today's market, recent events, prices or announcements, use web search and clearly distinguish confirmed facts from interpretation. Use the supplied live X10/Angel One snapshot when relevant. Never invent prices, news, targets or company facts. If the user asks whether to buy, provide a decision-support view with bull case, bear case, key levels and risk; do not present certainty or guaranteed returns. Prefer Indian market terminology and INR. Keep answers practical and easy to read. Mention when information is delayed or requires confirmation from the live broker feed."""
    user_prompt = f"User question:\n{question}\n\nCurrent Azad AI Plus market snapshot:\n{context}\n\nAnswer the user's question directly. If current news is requested, search the web before answering and include the publication/source names and dates in the response."

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        "input": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "tools": [{"type": "web_search"}],
        "max_output_tokens": 1400,
    }
    try:
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=45)
        data = response.json()
        if response.status_code >= 400:
            return jsonify({"success": False, "message": data.get("error", {}).get("message", "AI service request failed.")}), 502
        answer = data.get("output_text", "").strip()
        if not answer:
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in ("output_text", "text"):
                        answer += content.get("text", "")
        if not answer:
            answer = "I couldn't generate an answer right now. Please try again."
        return jsonify({"success": True, "answer": answer, "model": payload["model"]})
    except requests.RequestException as error:
        return jsonify({"success": False, "message": f"AI service connection failed: {error}"}), 502


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Azad AI Plus", "ai_configured": bool(os.getenv("OPENAI_API_KEY"))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
