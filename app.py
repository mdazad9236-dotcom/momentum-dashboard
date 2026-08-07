# app.py
from flask import Flask, jsonify, request
from config import APP_NAME
from stock_service import get_stock_data, StockService
from analysis import analyze_stock

app = Flask(__name__)
service = StockService()


def create_response(status, data=None, message=None):
    return {
        "status": status,
        "data": data,
        "message": message
    }


def fetch_and_analyze(symbol):
    try:
        stock_data = get_stock_data(symbol)
        if stock_data is None:
            return create_response("failed", message="Stock data not available")

        analysis_result = analyze_stock(stock_data)
        return create_response("success", data=analysis_result, message="Analysis completed")
    except Exception as error:
        return create_response("error", message=str(error))


# --- API Routes ---

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "app": APP_NAME,
        "message": "Stock Analysis App API is live"
    })


@app.route("/api/analyze/<symbol>", methods=["GET"])
def analyze_endpoint(symbol):
    res = service.get_stock_analysis(symbol)
    if res["success"]:
        return jsonify(create_response("success", data=res))
    return jsonify(create_response("failed", message=res["message"])), 400


# --- CLI Execution ---

def display_header():
    print("\n" + "=" * 50)
    print(APP_NAME)
    print("=" * 50)


def get_user_symbol():
    symbol = input("\nEnter stock symbol (or type EXIT): ").strip().upper()
    if symbol == "EXIT":
        return "EXIT"
    if not symbol:
        return None
    return symbol


def display_result(symbol, response):
    print("\n" + "-" * 50)
    print(f"Stock: {symbol}")
    print("-" * 50)
    print("Status:", response["status"])

    if response["message"]:
        print("Message:", response["message"])

    if response["data"]:
        print("\nAnalysis:")
        for key, value in response["data"].items():
            print(f"{key}: {value}")
    print("-" * 50)


def run_cli_application():
    display_header()
    while True:
        symbol = get_user_symbol()
        if symbol == "EXIT":
            print("\nApplication closed.")
            break
        if not symbol:
            print("Invalid input.")
            continue

        response = fetch_and_analyze(symbol)
        display_result(symbol, response)


if __name__ == "__main__":
    import sys
    # If run with '--cli', starts the interactive terminal mode
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli_application()
    else:
        # Defaults to running the Flask API server
        app.run(host="0.0.0.0", port=5000, debug=True)
