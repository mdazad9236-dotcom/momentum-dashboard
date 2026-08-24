import os
import threading
import time
import requests
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

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
_index_lock = threading.Lock()
_index_state = {"indices": [], "updated_at": 0.0, "refreshing": False, "last_error": None}

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
    fields = [
        "symbol", "name", "token", "price", "technical_score", "x10_score", "base_x10_score",
        "success_probability", "signal", "opportunity_rank", "ranking_reason",
        "early_momentum_score", "momentum_stage", "early_momentum_reasons", "validation",
        "why_buy", "why_not_buy", "entry", "entry_low", "entry_high", "stop_loss", "target",
        "target_1", "target_2", "risk", "reward", "risk_reward", "risk_reward_display",
        "risk_reward_value", "trailing_stop", "chase_price", "dont_chase", "setup_quality",
        "trend", "momentum", "rsi", "ema20", "ema50", "ema200", "macd", "macd_signal",
        "macd_histogram", "adx", "plus_di", "minus_di", "support", "resistance", "volume_ratio",
        "atr", "52_week_high", "52_week_low", "scan_time"
    ]
    return {field: stock.get(field, 0) for field in fields}

def _run_index_refresh():
    with _index_lock:
        if _index_state["refreshing"]:
            return False
        _index_state["refreshing"] = True
    try:
        scanner = AngelScanner(batch_size=5, delay=0.03, max_workers=5)
        login = scanner.service.login()
        if not login.get("success"):
            raise RuntimeError(login.get("message", "Angel One login failed."))
        indices = scanner._get_index_snapshots()
        if not indices:
            raise RuntimeError("Angel One returned no index snapshots.")
        with _index_lock:
            _index_state["indices"] = indices
            _index_state["updated_at"] = time.time()
            _index_state["last_error"] = None
        with _scan_lock:
            if _scan_state["result"] is not None:
                _scan_state["result"] = dict(_scan_state["result"])
                _scan_state["result"]["indices"] = indices
        return True
    except Exception as error:
        print("BACKGROUND INDEX REFRESH ERROR:", error)
        with _index_lock:
            _index_state["last_error"] = str(error)
        return False
    finally:
        with _index_lock:
            _index_state["refreshing"] = False

def _ensure_index_refresh(force=False):
    with _index_lock:
        age = time.time() - _index_state["updated_at"] if _index_state["updated_at"] else None
        refreshing = _index_state["refreshing"]
        stale = age is None or age >= SCAN_REFRESH_SECONDS
    if (force or stale) and not refreshing:
        threading.Thread(target=_run_index_refresh, name="x10-index-refresh", daemon=True).start()

def _publish_scan_payload(result, started):
    stocks = [clean_stock(stock) for stock in result.get("stocks", []) if isinstance(stock, dict)]
    with _index_lock:
        indices = list(_index_state["indices"])
    payload = {
        "success": True,
        "message": result.get("message", "Market scan completed."),
        "count": len(stocks),
        "scanned": result.get("scanned", len(stocks)),
        "successful": result.get("successful", len(stocks)),
        "manual_count": result.get("manual_count", 0),
        "time_seconds": result.get("time_seconds", round(time.time() - started, 2)),
        "stocks": stocks,
        "top_opportunities": stocks[:5],
        "indices": indices,
        "updated_at": time.time(),
        "data_source": result.get("data_source", "MIXED"),
    }
    with _scan_lock:
        _scan_state["result"] = payload
        _scan_state["updated_at"] = payload["updated_at"]
        _scan_state["last_error"] = None
    return payload

def _run_market_scan():
    with _scan_lock:
        if _scan_state["refreshing"]:
            return False
        _scan_state["refreshing"] = True
    started = time.time()
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        scanner = AngelScanner(batch_size=3, delay=0.03, max_workers=3)
        fallback_future = executor.submit(scanner._fallback_yfinance_scan, 6)
        broker_future = executor.submit(lambda: scanner.scan_market(limit=12, include_indices=False))
        fallback_published = False
        try:
            fallback_results = fallback_future.result(timeout=20)
            if fallback_results:
                _publish_scan_payload({
                    "success": True,
                    "message": "Live stock scan is running; showing X10 market-data candidates while broker data refreshes.",
                    "stocks": fallback_results,
                    "scanned": len(fallback_results),
                    "successful": len(fallback_results),
                    "data_source": "YAHOO FALLBACK",
                }, started)
                fallback_published = True
        except Exception as error:
            print("BACKGROUND FALLBACK SCAN ERROR:", error)
        try:
            result = broker_future.result(timeout=45)
            if result and result.get("success") and result.get("stocks"):
                _publish_scan_payload(result, started)
            elif not fallback_published:
                raise RuntimeError((result or {}).get("message", "Broker scanner returned no stocks."))
        except Exception as error:
            print("BACKGROUND X10 SCANNER ERROR:", error)
            with _scan_lock:
                _scan_state["last_error"] = str(error)
            if not fallback_published:
                try:
                    late_fallback = fallback_future.result(timeout=20)
                    if late_fallback:
                        _publish_scan_payload({
                            "success": True,
                            "message": "Broker scan unavailable; showing X10 market-data candidates.",
                            "stocks": late_fallback,
                            "scanned": len(late_fallback),
                            "successful": len(late_fallback),
                            "data_source": "YAHOO FALLBACK",
                        }, started)
                except Exception as fallback_error:
                    print("BACKGROUND LATE FALLBACK ERROR:", fallback_error)
        return True
    except Exception as error:
        print("BACKGROUND X10 SCANNER ERROR:", error)
        with _scan_lock:
            _scan_state["last_error"] = str(error)
        return False
    finally:
        executor.shutdown(wait=False, cancel_futures=False)
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
    with _index_lock:
        index_state = dict(_index_state)
    if result:
        payload = dict(result)
        if index_state["indices"]:
            payload["indices"] = list(index_state["indices"])
        payload["refreshing"] = refreshing or index_state["refreshing"]
        payload["cache_age_seconds"] = round(max(0, time.time() - updated_at), 1)
        payload["stale"] = payload["cache_age_seconds"] >= SCAN_REFRESH_SECONDS
        payload["index_updated_at"] = index_state["updated_at"]
        payload["index_last_error"] = index_state["last_error"]
        return payload
    return {"success": True, "message": "Market data is initializing in the background.", "count": 0, "scanned": 0, "successful": 0, "time_seconds": 0, "stocks": [], "top_opportunities": [], "indices": list(index_state["indices"]), "refreshing": refreshing or index_state["refreshing"], "cache_age_seconds": None, "stale": True, "last_error": last_error, "index_last_error": index_state["last_error"]}

def _background_refresh_loop():
    time.sleep(2)
    while True:
        try:
            _ensure_index_refresh()
            _ensure_scan_refresh()
        except Exception as error:
            print("BACKGROUND REFRESH LOOP ERROR:", error)
        time.sleep(15)
threading.Thread(target=_background_refresh_loop, name="x10-refresh-loop", daemon=True).start()

@app.route("/api/historical/<path:symbol>")
@login_required
def historical(symbol):
    try:
        instrument = instrument_manager.find_stock(symbol)
        if not instrument:
            return jsonify({"success": False, "message": f"Angel One instrument not found: {symbol}", "data": []}), 404
        result = angel_service.get_historical_data(instrument["symbol"], instrument["token"], days=400, interval="ONE_DAY", exchange=instrument.get("exchange", "NSE"))
        return jsonify(result), (200 if result.get("success") else 502)
    except Exception as error:
        print("HISTORICAL API ERROR:", error)
        return jsonify({"success": False, "message": str(error), "data": []}), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        if request.form.get("user_id", "") == APP_USER_ID and request.form.get("password", "") == APP_PASSWORD:
            session.clear(); session["authenticated"] = True; session["user_id"] = APP_USER_ID
            return redirect(url_for("home"))
        error = "Invalid User ID or Password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def home():
    return render_template("index.html")

@app.route("/api/analyze/<symbol>")
@login_required
def analyze_stock(symbol):
    try:
        result = stock_service.get_stock_analysis(symbol.upper().strip())
        if not result: return jsonify({"success": False, "message": "No analysis result returned."}), 500
        return jsonify(result)
    except Exception as error: return jsonify({"success": False, "message": str(error)}), 500

@app.route("/api/scan")
@login_required
def scan():
    _ensure_index_refresh(); _ensure_scan_refresh(); return jsonify(_snapshot_response())

@app.route("/api/scan/refresh")
@login_required
def scan_refresh():
    _ensure_index_refresh(force=True); _ensure_scan_refresh(force=True)
    return jsonify({"success": True, "message": "X10 scan and index refresh started in background.", "refreshing": True})

@app.route("/api/indices")
@login_required
def indices_endpoint():
    _ensure_index_refresh();
    with _index_lock:
        return jsonify({"success": True, "indices": list(_index_state["indices"]), "cached": bool(_index_state["indices"]), "refreshing": _index_state["refreshing"], "updated_at": _index_state["updated_at"], "last_error": _index_state["last_error"]})

@app.route("/api/instruments")
@login_required
def instruments_endpoint():
    try:
        result = instrument_manager.load_cache()
        if not result.get("success"): return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities(); return jsonify({"success": True, "count": len(stocks), "stocks": stocks})
    except Exception as error: return jsonify({"success": False, "message": str(error), "stocks": []}), 500

@app.route("/api/instruments/refresh")
@login_required
def refresh_instruments_endpoint():
    try:
        result = instrument_manager.refresh()
        if not result.get("success"): return jsonify(result), 500
        stocks = instrument_manager.get_nse_equities(); return jsonify({"success": True, "count": len(stocks), "message": "Angel One instrument master refreshed.", "stocks": stocks})
    except Exception as error: return jsonify({"success": False, "message": str(error), "stocks": []}), 500

@app.route("/api/instrument/<symbol>")
@login_required
def instrument_endpoint(symbol):
    try:
        stock = instrument_manager.find_stock(symbol)
        if not stock: return jsonify({"success": False, "message": "Stock not found."}), 404
        return jsonify({"success": True, "stock": stock})
    except Exception as error: return jsonify({"success": False, "message": str(error)}), 500
