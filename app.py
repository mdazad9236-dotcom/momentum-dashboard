from flask import Flask, jsonify, render_template
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
            "Error fetching stock data"
        )
    }), 400


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "message": "Stock Analysis App API is healthy"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
