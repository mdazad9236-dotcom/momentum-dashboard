# angel_symbols.py

NSE_STOCKS = [
    {
        "symbol": "RELIANCE-EQ",
        "name": "Reliance Industries",
        "token": "2885"
    },
    {
        "symbol": "TCS-EQ",
        "name": "Tata Consultancy Services",
        "token": "11536"
    },
    {
        "symbol": "INFY-EQ",
        "name": "Infosys",
        "token": "1594"
    },
    {
        "symbol": "HDFCBANK-EQ",
        "name": "HDFC Bank",
        "token": "1333"
    },
    {
        "symbol": "ICICIBANK-EQ",
        "name": "ICICI Bank",
        "token": "4963"
    },
    {
        "symbol": "SBIN-EQ",
        "name": "State Bank of India",
        "token": "3045"
    },
    {
        "symbol": "BHARTIARTL-EQ",
        "name": "Bharti Airtel",
        "token": "10604"
    },
    {
        "symbol": "ITC-EQ",
        "name": "ITC",
        "token": "1660"
    },
    {
        "symbol": "LT-EQ",
        "name": "Larsen & Toubro",
        "token": "11483"
    },
    {
        "symbol": "AXISBANK-EQ",
        "name": "Axis Bank",
        "token": "5900"
    },
    {
        "symbol": "KOTAKBANK-EQ",
        "name": "Kotak Mahindra Bank",
        "token": "1922"
    },
    {
        "symbol": "TATASTEEL-EQ",
        "name": "Tata Steel",
        "token": "3499"
    },
    {
        "symbol": "TATAMOTORS-EQ",
        "name": "Tata Motors",
        "token": "3456"
    },
    {
        "symbol": "MARUTI-EQ",
        "name": "Maruti Suzuki",
        "token": "10999"
    },
    {
        "symbol": "SUNPHARMA-EQ",
        "name": "Sun Pharmaceutical",
        "token": "3351"
    },
    {
        "symbol": "HINDALCO-EQ",
        "name": "Hindalco Industries",
        "token": "1363"
    },
    {
        "symbol": "NTPC-EQ",
        "name": "NTPC",
        "token": "11630"
    },
    {
        "symbol": "POWERGRID-EQ",
        "name": "Power Grid Corporation",
        "token": "14977"
    },
    {
        "symbol": "ONGC-EQ",
        "name": "ONGC",
        "token": "2475"
    },
    {
        "symbol": "COALINDIA-EQ",
        "name": "Coal India",
        "token": "20374"
    }
]


def get_stock_universe():
    """
    Return the complete stock universe.
    """

    return NSE_STOCKS.copy()


def get_stock_by_symbol(symbol):
    """
    Find a stock using its Angel One trading symbol.
    """

    symbol = symbol.upper().strip()

    for stock in NSE_STOCKS:

        if stock["symbol"] == symbol:
            return stock

    return None
