# app.py
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "Stock Analysis App is live"
    })
from config import APP_NAME
from stock_service import actual_function_name
from analysis import analyze_stock


def main():
    print("=" * 50)
    print(APP_NAME)
    print("=" * 50)

    # Example stock symbol
    symbol = "RELIANCE"

    print(f"\nFetching data for: {symbol}")

    # Get stock data
    stock_data = get_stock_data(symbol)

    if not stock_data:
        print("Unable to fetch stock data.")
        return

    print("\nStock data received.")

    # Analyze stock
    result = analyze_stock(stock_data)

    print("\nAnalysis Result:")
    print("-" * 50)

    for key, value in result.items():
        print(f"{key}: {value}")

    print("-" * 50)


if __name__ == "__main__":
    main()
    # app.py

from config import APP_NAME
from stock_service import get_stock_data
from analysis import analyze_stock


def display_header():
    print("=" * 50)
    print(APP_NAME)
    print("=" * 50)


def get_user_symbol():
    symbol = input("\nEnter stock symbol: ").strip().upper()

    if not symbol:
        print("Invalid symbol entered.")
        return None

    return symbol


def process_stock(symbol):
    print(f"\nFetching data for: {symbol}")

    try:
        stock_data = get_stock_data(symbol)

        if not stock_data:
            print("No stock data found.")
            return None

        print("Stock data received.")

        result = analyze_stock(stock_data)

        return result

    except Exception as error:
        print(f"Error occurred: {error}")
        return None


def display_result(result):
    if not result:
        print("\nNo analysis available.")
        return

    print("\nAnalysis Result")
    print("-" * 50)

    for key, value in result.items():
        print(f"{key}: {value}")

    print("-" * 50)


def main():
    display_header()

    symbol = get_user_symbol()

    if not symbol:
        return

    result = process_stock(symbol)

    display_result(result)


if __name__ == "__main__":
    main()

# app.py

from config import APP_NAME
from stock_service import get_stock_data
from analysis import analyze_stock


def display_header():
    print("\n" + "=" * 50)
    print(APP_NAME)
    print("=" * 50)


def get_user_symbol():
    symbol = input("\nEnter stock symbol (or type EXIT): ").strip().upper()

    if symbol == "EXIT":
        return "EXIT"

    if not symbol:
        print("Please enter a valid stock symbol.")
        return None

    return symbol


def process_stock(symbol):
    print(f"\nAnalyzing {symbol}...")

    try:
        stock_data = get_stock_data(symbol)

        if not stock_data:
            print("Unable to retrieve stock information.")
            return None

        analysis_result = analyze_stock(stock_data)

        return analysis_result

    except Exception as error:
        print(f"Processing error: {error}")
        return None


def display_result(symbol, result):
    if not result:
        print("\nNo result available.")
        return

    print("\n" + "-" * 50)
    print(f"Analysis Report: {symbol}")
    print("-" * 50)

    for key, value in result.items():
        print(f"{key}: {value}")

    print("-" * 50)


def run_application():

    display_header()

    while True:

        symbol = get_user_symbol()

        if symbol == "EXIT":
            print("\nClosing application...")
            break

        if not symbol:
            continue

        result = process_stock(symbol)

        display_result(symbol, result)


def main():
    run_application()


if __name__ == "__main__":
    main()

# app.py

from config import APP_NAME
from stock_service import get_stock_data
from analysis import analyze_stock


def create_response(status, data=None, message=None):
    return {
        "status": status,
        "data": data,
        "message": message
    }


def display_header():
    print("\n" + "=" * 50)
    print(APP_NAME)
    print("=" * 50)


def get_user_symbol():

    symbol = input(
        "\nEnter stock symbol (or type EXIT): "
    ).strip().upper()

    if symbol == "EXIT":
        return "EXIT"

    if not symbol:
        return None

    return symbol


def fetch_and_analyze(symbol):

    try:

        stock_data = get_stock_data(symbol)

        if not stock_data:
            return create_response(
                "failed",
                message="Stock data not available"
            )

        analysis_result = analyze_stock(stock_data)

        return create_response(
            "success",
            data=analysis_result,
            message="Analysis completed"
        )

    except Exception as error:

        return create_response(
            "error",
            message=str(error)
        )


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


def run_application():

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


def main():

    try:
        run_application()

    except KeyboardInterrupt:

        print("\n\nApplication interrupted by user.")


if __name__ == "__main__":
    main()

@app.route("/")
def home():
    return "Stock Analysis App Running"
