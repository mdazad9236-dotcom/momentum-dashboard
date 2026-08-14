from flask import Flask, jsonify, render_template
from angel_service import AngelOneService
from stock_service import StockService


app = Flask(__name__)

service = StockService()


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
