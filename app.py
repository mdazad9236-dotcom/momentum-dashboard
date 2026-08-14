from angel_instruments import AngelInstrumentManager

instrument_manager = AngelInstrumentManager()
from flask import Flask, jsonify, render_template
from angel_service import AngelOneService
from stock_service import StockService
from angel_scanner import AngelScanner


# ============================================================
# APP INITIALIZATION
# ============================================================

app = Flask(__name__)

angel_service = AngelOneService()
stock_service = StockService()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template("index.html")


# ============================================================
# STOCK ANALYSIS
# ============================================================

@app.route("/api/analyze/<symbol>", methods=["GET"])
def analyze_endpoint(symbol):

    try:

        result = stock_service.get_stock_analysis(
            symbol
        )

        if result.get("success"):

            return jsonify({
                "status": "success",
                "data": result
            })

        return jsonify({
            "status": "failed",
            "message": result.get(
                "message",
                "Unable to fetch stock data."
            )
        }), 400

    except Exception as error:

        return jsonify({
            "status": "failed",
            "message": str(error)
        }), 500


# ============================================================
# ANGEL ONE LOGIN TEST
# ============================================================

@app.route("/api/angel-test", methods=["GET"])
def angel_test():

    try:

        result = angel_service.login()

        if result:

            return jsonify({
                "status": "success",
                "message": "Angel One login successful."
            })

        return jsonify({
            "status": "failed",
            "message": "Angel One login failed."
        }), 400

    except Exception as error:

        return jsonify({
            "status": "failed",
            "message": str(error)
        }), 500


# ============================================================
# ANGEL ONE MARKET DATA TEST
# ============================================================

@app.route("/api/market-test", methods=["GET"])
def market_test():

    try:

        result = angel_service.get_market_data_service()

        if not result.get("success"):

            return jsonify({
                "status": "failed",
                "message": result.get(
                    "message",
                    "Market data service failed."
                )
            }), 400

        return jsonify({
            "status": "success",
            "message": "Angel One market-data service connected."
        })

    except Exception as error:

        return jsonify({
            "status": "failed",
            "message": str(error)
        }), 500


# ============================================================
# ANGEL ONE LTP TEST
# ============================================================

@app.route("/api/ltp-test", methods=["GET"])
def ltp_test():

    try:

        result = angel_service.get_market_data_service()

        if not result.get("success"):

            return jsonify({
                "status": "failed",
                "message": result.get("message")
            }), 400

        market = result["service"]

        data = market.get_ltp(
            exchange="NSE",
            tradingsymbol="RELIANCE-EQ",
            symboltoken="2885"
        )

        if not data.get("success"):

            return jsonify({
                "status": "failed",
                "message": data.get("message")
            }), 400

        return jsonify({
            "status": "success",
            "data": data
        })

    except Exception as error:

        return jsonify({
            "status": "failed",
            "message": str(error)
        }), 500


# ============================================================
# MARKET SCANNER TEST
# ============================================================

@app.route("/api/scan-test", methods=["GET"])
def scan_test():

    try:

        scanner = AngelScanner()

        result = scanner.scan_market()

        if not result.get("success"):

            return jsonify({
                "status": "failed",
                "message": result.get("message")
            }), 400

        return jsonify({
            "status": "success",
            "count": result.get("count"),
            "stocks": result.get("stocks")
        })

    except Exception as error:

        return jsonify({
            "status": "failed",
            "message": str(error)
        }), 500


# ============================================================
# HISTORICAL DATA
# ============================================================

@app.route("/api/historical/<symbol>", methods=["GET"])
def historical_endpoint(symbol):

    token_map = {

        "RELIANCE-EQ": "2885",
        "TCS-EQ": "11536",
        "INFY-EQ": "1594",
        "HDFCBANK-EQ": "1333",
        "ICICIBANK-EQ": "4963",
        "SBIN-EQ": "3045",
        "BHARTIARTL-EQ": "10604",
        "ITC-EQ": "1660",
        "LT-EQ": "11483",
        "AXISBANK-EQ": "5900",
        "KOTAKBANK-EQ": "1922",
        "TATASTEEL-EQ": "3499",
        "TATAMOTORS-EQ": "3456",
        "MARUTI-EQ": "10999",
        "SUNPHARMA-EQ": "3351",
        "HINDALCO-EQ": "1363",
        "NTPC-EQ": "11630",
        "POWERGRID-EQ": "14977",
        "ONGC-EQ": "2475",
        "COALINDIA-EQ": "20374"
    }

    try:

        symbol = symbol.upper()

        if symbol not in token_map:

            return jsonify({
                "success": False,
                "message": (
                    "Stock symbol not found "
                    "in scanner list."
                )
            }), 404

        result = angel_service.get_historical_data(
            symbol=symbol,
            token=token_map[symbol],
            days=200,
            interval="ONE_DAY",
            exchange="NSE"
        )

        return jsonify(result)

    except Exception as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


# ============================================================
# RUN LOCAL SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
@app.route("/api/instruments", methods=["GET"])
def instruments_endpoint():

    result = instrument_manager.load_cache()

    if not result.get("success"):
        return jsonify(result), 500

    stocks = instrument_manager.get_nse_equities()

    return jsonify({
        "success": True,
        "count": len(stocks),
        "stocks": stocks
    })


@app.route("/api/instruments/refresh", methods=["GET"])
def refresh_instruments_endpoint():

    result = instrument_manager.refresh()

    if not result.get("success"):
        return jsonify(result), 500

    stocks = instrument_manager.get_nse_equities()

    return jsonify({
        "success": True,
        "count": len(stocks),
        "message": "Angel One instrument master refreshed.",
        "stocks": stocks
    })


@app.route("/api/instrument/<symbol>", methods=["GET"])
def instrument_endpoint(symbol):

    stock = instrument_manager.find_stock(symbol)

    if not stock:
        return jsonify({
            "success": False,
            "message": "Stock not found."
        }), 404

    return jsonify({
        "success": True,
        "stock": stock
    })
