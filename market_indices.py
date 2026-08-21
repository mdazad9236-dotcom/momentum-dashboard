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


def _pct(a, b):
    return ((a - b) / b * 100.0) if b else 0.0


def classify_bias(price, support, resistance, ema20=0, ema50=0, momentum=0, change_percent=0):
    """Classify an index using structure + trend + momentum, not price position alone."""
    price, support, resistance = _num(price), _num(support), _num(resistance)
    ema20, ema50 = _num(ema20), _num(ema50)
    score = 0
    if ema20 and price > ema20:
        score += 1
    elif ema20 and price < ema20:
        score -= 1
    if ema50 and price > ema50:
        score += 1
    elif ema50 and price < ema50:
        score -= 1
    if momentum > 0:
        score += 1
    elif momentum < 0:
        score -= 1
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


def _target_zones(price, support, resistance, atr=0):
    """Create practical upside/downside zones from structure and volatility."""
    price, support, resistance, atr = map(_num, (price, support, resistance, atr))
    if price <= 0:
        return {"upside": [], "downside": []}
    volatility = atr if atr > 0 else price * 0.012
    r1 = resistance if resistance > price else price + volatility
    r2 = max(r1 + volatility, price + 2 * volatility)
    r3 = max(r2 + volatility, price + 3 * volatility)
    s1 = support if 0 < support < price else price - volatility
    s2 = min(s1 - volatility, price - 2 * volatility)
    return {
        "upside": [round(r1, 2), round(r2, 2), round(r3, 2)],
        "downside": [round(s1, 2), round(s2, 2)],
    }


def build_index_snapshot(name, price, support=0, resistance=0, change=0, change_percent=0,
                         ema20=0, ema50=0, atr=0, momentum=0, trend="Neutral"):
    """Stable JSON shape for index cards and detailed analysis."""
    price, support, resistance = _num(price), _num(support), _num(resistance)
    change, change_percent = _num(change), _num(change_percent)
    ema20, ema50, atr, momentum = map(_num, (ema20, ema50, atr, momentum))
    targets = _target_zones(price, support, resistance, atr)
    bias = classify_bias(price, support, resistance, ema20, ema50, momentum, change_percent)
    upside = targets["upside"]
    downside = targets["downside"]
    entry_low = min(price, resistance * 0.995) if resistance > price else price - (atr or price * 0.01)
    entry_high = price if price <= resistance else price + (atr or price * 0.01)
    return {
        "name": name,
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "target_zones": {"target_1": upside[0] if upside else 0, "target_2": upside[1] if len(upside) > 1 else 0, "target_3": upside[2] if len(upside) > 2 else 0},
        "downside_zones": {"support_1": downside[0] if downside else 0, "support_2": downside[1] if len(downside) > 1 else 0},
        "entry_zone": {"low": round(entry_low, 2), "high": round(entry_high, 2)},
        "bias": bias,
        "trend": trend,
        "momentum": "Positive" if momentum > 0 else "Negative" if momentum < 0 else "Neutral",
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "atr": round(atr, 2),
    }
