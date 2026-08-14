from flask import Flask, jsonify, render_template
from angel_service import AngelOneService
from stock_service import StockService
@app.route("/api/analyze/<symbol>", methods=["GET"])
from angel_scanner import AngelScanner

app = Flask(__name__)

angel_service = AngelOneService()


@app.route("/")
def home():

    return render_template("index.html")


@app.route("/api/analyze/<symbol>", methods=["GET"])
def analyze_endpoint(symbol):

    result = service.get_stock_analysis(symbol)

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


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
@app.route("/api/angel-test", methods=["GET"])
def angel_test():

    service = AngelOneService()

    result = service.login()

    if result.get("success"):

        return jsonify({
            "status": "success",
            "message": result.get("message")
        })

    return jsonify({
        "status": "failed",
        "message": result.get("message")
    }), 400
@app.route("/api/market-test", methods=["GET"])
def market_test():

    service = AngelOneService()

    result = service.get_market_data_service()

    if not result.get("success"):
        return jsonify({
            "status": "failed",
            "message": result.get("message")
        }), 400

    return jsonify({
        "status": "success",
        "message": "Angel One market-data service connected."
    })
@app.route("/api/ltp-test", methods=["GET"])
def ltp_test():

    service = AngelOneService()

    result = service.get_market_data_service()

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
@app.route("/api/scan-test", methods=["GET"])
def scan_test():

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
@app.route("/api/historical/<symbol>", methods=["GET"])
def historical_endpoint(symbol):
    try:
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

        symbol = symbol.upper()

        if symbol not in token_map:
            return jsonify({
                "success": False,
                "message": "Stock symbol not found in scanner list."
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
