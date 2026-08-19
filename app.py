from flask import Flask, jsonify, render_template

from angel_instruments import AngelInstrumentManager
from angel_service import AngelOneService
from stock_service import StockService
from angel_scanner import AngelScanner

app = Flask(__name__)
angel_service = AngelOneService()
stock_service = StockService()
instrument_manager = AngelInstrumentManager()


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/api/analyze/<symbol>", methods=["GET"])
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
def angel_test():
    try:
        result = angel_service.login()
        return jsonify({"status": "success" if result.get("success") else "failed", "message": result.get("message", "Angel One login failed.")}), (200 if result.get("success") else 400)
    except Exception as error:
        return jsonify({"status": "failed", "message": str(error)}), 500


@app.route("/api/market-test", methods=["GET"])
def market_test():
    try:
        result = angel_service.get_market_data_service()
        return jsonify({"status": "success" if result.get("success") else "failed", "message": result.get("message", "Market data service failed.")}), (200 if result.get("success") else 400)
    except Exception as error:
        return jsonify({"status": "failed", "message": str(error)}), 500


@app.route("/api/ltp-test", methods=["GET"])
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
def scan():
    try:
        scanner = AngelScanner(batch_size=5, delay=0.03, max_workers=5)
        result = scanner.scan_market(limit=30)
        if not result.get("success"):
            return jsonify({"success": False, "message": result.get("message", "Angel One scanner failed."), "stocks": [], "indices": [], "count": 0, "scanned": 0, "successful": 0}), 200
        stocks = [clean_stock(stock) for stock in result.get("stocks", []) if isinstance(stock, dict)]
        return jsonify({"success": True, "message": "Market scan completed.", "count": len(stocks), "scanned": result.get("scanned", 0),
                        "successful": result.get("successful", 0), "time_seconds": result.get("time_seconds", 0),
                        "stocks": stocks, "indices": result.get("indices", [])})
    except Exception as error:
        print("X10 SCANNER API ERROR:", error)
        return jsonify({"success": False, "message": str(error), "stocks": [], "indices": [], "count": 0, "scanned": 0, "successful": 0}), 200


@app.route("/api/indices", methods=["GET"])
def indices_endpoint():
    """Load indices independently from the stock scan so a slow scan cannot blank Market Pulse."""
    try:
        scanner = AngelScanner(max_workers=1)
        login = scanner.service.login()
        if not login.get("success"):
            return jsonify({"success": False, "message": login.get("message", "Angel One login failed."), "indices": []}), 200
        indices = scanner._get_index_snapshots()
        return jsonify({"success": True, "indices": indices})
    except Exception as error:
        return jsonify({"success": False, "message": str(error), "indices": []}), 200


@app.route("/api/historical/<symbol>", methods=["GET"])
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
    return jsonify({"status": "ok", "service": "X10 MarketAI"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
