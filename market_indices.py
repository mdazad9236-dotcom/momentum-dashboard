"""Index definitions and actionable market-analysis helpers."""

INDEX_DEFINITIONS = {
    "NIFTY 50": {"exchange": "NSE", "tradingsymbol": "NIFTY", "token": "99926000"},
    "BANK NIFTY": {"exchange": "NSE", "tradingsymbol": "BANKNIFTY", "token": "99926009"},
    "SENSEX": {"exchange": "BSE", "tradingsymbol": "SENSEX", "token": "99919000"},
    "INDIA VIX": {"exchange": "NSE", "tradingsymbol": "INDIAVIX", "token": "99926017"},
    "NIFTY IT": {"exchange": "NSE", "tradingsymbol": "NIFTY IT", "token": "99926008"},
    "NIFTY AUTO": {"exchange": "NSE", "tradingsymbol": "NIFTYAUTO", "token": "99926001"},
    "NIFTY PHARMA": {"exchange": "NSE", "tradingsymbol": "NIFTYPHARMA", "token": "99926012"},
    "NIFTY METAL": {"exchange": "NSE", "tradingsymbol": "NIFTYMETAL", "token": "99926011"},
}


def _num(value, default=0.0):
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return float(default)


def classify_bias(price, support, resistance, change_percent=0):
    """Return an actionable bias using price structure and daily momentum."""
    price, support, resistance = _num(price), _num(support), _num(resistance)
    change_percent = _num(change_percent)
    if price <= 0:
        return "UNKNOWN"
    score = 0
    if resistance > price and support > 0:
        midpoint = support + ((resistance - support) * 0.5)
        score += 1 if price >= midpoint else -1
    if change_percent > 0.35:
        score += 1
    elif change_percent < -0.35:
        score -= 1
    if resistance and price >= resistance * 0.985:
        score -= 1
    if support and price <= support * 1.015:
        score += 1
    if score >= 2:
        return "BULLISH"
    if score <= -2:
        return "BEARISH"
    return "NEUTRAL"


def _target_zones(price, support, resistance):
    price, support, resistance = map(_num, (price, support, resistance))
    if price <= 0:
        return {"target_1": 0, "target_2": 0, "target_3": 0, "support_1": 0, "support_2": 0}
    span = max(price * 0.01, abs(resistance - support) * 0.25 if resistance > support > 0 else price * 0.01)
    r1 = resistance if resistance > price else price + span
    r2 = max(r1 + span, price + 2 * span)
    r3 = max(r2 + span, price + 3 * span)
    s1 = support if 0 < support < price else price - span
    s2 = min(s1 - span, price - 2 * span)
    return {
        "target_1": round(r1, 2), "target_2": round(r2, 2), "target_3": round(r3, 2),
        "support_1": round(s1, 2), "support_2": round(s2, 2),
    }


def build_index_snapshot(name, price, support=0, resistance=0, change=0, change_percent=0):
    """Create the stable JSON shape used by index cards and detailed analysis."""
    price, support, resistance = _num(price), _num(support), _num(resistance)
    change, change_percent = _num(change), _num(change_percent)
    targets = _target_zones(price, support, resistance)
    return {
        "name": name,
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "target_zones": {
            "target_1": targets["target_1"],
            "target_2": targets["target_2"],
            "target_3": targets["target_3"],
        },
        "downside_zones": {
            "support_1": targets["support_1"],
            "support_2": targets["support_2"],
        },
        "entry_zone": {
            "low": round(min(price, resistance * 0.995) if resistance > price else max(0, price - (price * 0.01)), 2),
            "high": round(price, 2),
        },
        "bias": classify_bias(price, support, resistance, change_percent),
    }
