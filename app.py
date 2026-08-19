import os
import threading
import time
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

# ---------------------------------------------------------------------------
# Background market cache
# ---------------------------------------------------------------------------
# The X10 engine and Angel One scanner remain unchanged.  The dashboard no
# longer has to wait for a complete market scan on every page request.
SCAN_REFRESH_SECONDS = max(60, int(os.getenv("X10_SCAN_REFRESH_SECONDS", "180")))
_scan_lock = threading.Lock()
_scan_state = {
    "result": None,
    "updated_at": 0.0,
    "refreshing": False,
    "last_error": None,
}


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


def _run_market_scan():
    """Run one X10 scan in the background and publish it atomically."""
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
        payload = {
            "success": True,
            "message": "Market scan completed.",
            "count": len(stocks),
            "scanned": result.get("scanned", 0),
            "successful": result.get("successful", 0),
            "time_seconds": result.get("time_seconds", round(time.time() - started, 2)),
            "stocks": stocks,
            "indices": result.get("indices", []),
            "updated_at": time.time(),
        }
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
    """Start a scan without blocking the HTTP request."""
    with _scan_lock:
        age = time.time() - _scan_state["updated_at"] if _scan_state["updated_at"] else None
        refreshing = _scan_state["refreshing"]
        stale = age is None or age >= SCAN_REFRESH_SECONDS

    if (force or stale) and not refreshing:
        thread = threading.Thread(target=_run_market_scan, name="x10-market-scan", daemon=True)
        thread.start()


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

    return {
        "success": True,
        "message": "Market scan is warming up in the background.",
        "count": 0,
        "scanned": 0,
        "successful": 0,
        "time_seconds": 0,
        "stocks": [],
        "indices": [],
        "refreshing": refreshing,
        "cache_age_seconds": None,
        "stale": True,
        "last_error": last_error,
    }


def _background_refresh_loop():
    # Wait briefly so Flask can finish booting before the first broker call.
    time.sleep(2)
    while True:
        try:
            _ensure_scan_refresh()
        except Exception as error:
            print("BACKGROUND REFRESH LOOP ERROR:", error)
        time.sleep(15)


# Start one daemon worker per Python process. It never blocks page rendering.
threading.Thread(target=_background_refresh_loop, name="x10-refresh-loop", daemon=True).start()


@app.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        user_id = request.form.get("user_id", "")
        password = request.form.get("password", "")
        if user_id == APP_USER_ID and password == APP_PASSWORD:
            session.clear()
            session["authenticated"] = True
            session["user_id"] = APP_USER_ID
            return redirect(url_for("home"))
        error = "Invalid User ID or Password."
    return render_template("login.html", error=error)


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET"])
@login_required
def home():
    return render_template("index.html")


@app.route("/api/analyze/<symbol>", methods=["GET"])
@login_required
def analyze_stock(symbol):
    try:
        result = stock_service.get_stock_analysis(symbol.upper().strip())
        if not result:
            return jsonify({"success": False, "message": "No analysis result returned."}), 500
        return jsonify(result)
    except Exception as error:
        print("STOCK ANALYSIS API ERROR:", error)
        return jsonify({"success": False, "message": str(error)}), 500


@app.route("/api/angel-test", methods=["GET"])
@login_required
def angel_test():
    try:
        result = angel_service.login()
        return jsonify({"status": "success" if result.get("success") else "failed", "message": result.get("message", "Angel One login failed.")}), (200 if result.get("success") else 400)
    except Exception as error:
        return jsonify({"status": "failed", "message": str(error)}), 500


@app.route("/api/market-test", methods=["GET"])
@login_required
def market_test():
    try:
        result = angel_service.get_market_data_service()
        return jsonify({"status": "success" if result.get("success") else "failed", "message": result.get("message", "Market data service failed.")}), (200 if result.get("success") else 400)
    except Exception as error:
        return jsonify({"status": "failed", "message": str(error)}), 500


@app.route("/api/ltp-test", methods=["GET"])
@login_required
def ltp_test():
    try:
        result = angel_service.get_ltp("NSE", "RELIANCE-EQ", "2885")
        return jsonify({"status": "success" if result.get("success") else "failed", "data": result}), (200 if result.get("success") else 400)
    except Exception as error:
        return jsonify({"status": "failed", "message": str(error)}), 500


def clean_stock(stock):
    fields = ["symbol", "name", "token", "price", "technical_score", "x10_score", "success_probability", "signal",
              "entry", "entry_low", "entry_high", "stop_loss", "target", "target_1", "target_2", "risk", "reward",
              "risk_reward", "trailing_stop", "chase_price", "dont_chase", "setup_quality", "trend", "momentum", "rsi",
              "ema20", "ema50", "ema200", "macd", "macd_signal", "macd_histogram", "adx", "plus_di", "minus_di",
              "support", "resistance", "volume_ratio", "atr", "52_week_high", "52_week_low", "scan_time"]
    return {field: stock.get(field, 0) for field in fields}


@app.route("/api/scan", methods=["GET"])
@login_required
def scan():
    # Fast path: return the latest completed scan and refresh stale data in the
    # background. This preserves the scanner while removing its latency from
    # every browser request.
    _ensure_scan_refresh()
    return jsonify(_snapshot_response())


@app.route("/api/scan/refresh", methods=["GET"])
@login_required
def scan_refresh():
    _ensure_scan_refresh(force=True)
    return jsonify({"success": True, "message": "X10 scan refresh started in background.", "refreshing": True})


@app.route("/api/indices", methods=["GET"])
@login_required
def indices_endpoint():
    # Prefer the same completed scan snapshot so indices don't trigger a
    # second Angel One login/history workload immediately after page load.
    _ensure_scan_refresh()
    snapshot = _snapshot_response()
    if snapshot.get("indices"):
        return jsonify({"success": True, "indices": snapshot["indices"], "cached": True, "refreshing": snapshot.get("refreshing", False)})
    return jsonify({"success": True, "indices": [], "cached": True, "refreshing": snapshot.get("refreshing", False)})


@app.route("/api/historical/<symbol>", methods=["GET"])
@login_required
def historical_endpoint(symbol):
    try:
        requested = symbol.upper().strip()
        stock = instrument_manager.find_stock(requested)
        if not stock:
            return jsonify({"success": False, "message": "NSE equity symbol not found in Angel One instrument master."}), 404
        return jsonify(angel_service.get_historical_data(symbol=stock["symbol"], token=stock["token"], days=200, interval="ONE_DAY", exchange="NSE"))
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "data": []}), 500


@app.route("/api/instruments", methods=["GET"])
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


@app.route("/api/instruments/refresh", methods=["GET"])
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


@app.route("/api/instrument/<symbol>", methods=["GET"])
@login_required
def instrument_endpoint(symbol):
    try:
        stock = instrument_manager.find_stock(symbol)
        if not stock:
            return jsonify({"success": False, "message": "Stock not found."}), 404
        return jsonify({"success": True, "stock": stock})
    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Azad AI Plus"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
