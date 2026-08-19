"""Index definitions and lightweight market-analysis helpers.

The module is intentionally independent from the existing stock scanner so
index analysis can be added without coupling it to the stock universe scan.
"""

INDEX_DEFINITIONS = {
    "NIFTY 50": {"exchange": "NSE", "tradingsymbol": "NIFTY", "token": "99926000"},
    "BANK NIFTY": {"exchange": "NSE", "tradingsymbol": "BANKNIFTY", "token": "99926009"},
    "SENSEX": {"exchange": "BSE", "tradingsymbol": "SENSEX", "token": "99919000"},
    "INDIA VIX": {"exchange": "NSE", "tradingsymbol": "INDIAVIX", "token": "99926017"},
}


def classify_bias(price, support, resistance):
    """Return a simple actionable bias from price location."""
    if price <= 0:
        return "UNKNOWN"
    if resistance > price and support > 0:
        midpoint = support + ((resistance - support) * 0.5)
        if price >= midpoint:
            return "BULLISH"
        return "NEUTRAL"
    return "NEUTRAL"


def build_index_snapshot(name, price, support=0, resistance=0, change=0, change_percent=0):
    """Create the stable JSON shape used by the dashboard index cards."""
    price = float(price or 0)
    support = float(support or 0)
    resistance = float(resistance or 0)
    return {
        "name": name,
        "price": round(price, 2),
        "change": round(float(change or 0), 2),
        "change_percent": round(float(change_percent or 0), 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "bias": classify_bias(price, support, resistance),
    }
