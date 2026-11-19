"""Index definitions and explainable index-analysis helpers.

Support/resistance values from the live quote are intraday high/low proxies.
They are not presented as confirmed multi-day technical levels.
"""

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


def analyze_index_bias(name, price, support, resistance, change_percent=0):
    """Return a directional read with the factors that produced it."""
    name = str(name or "").upper()
    price, support, resistance = _num(price), _num(support), _num(resistance)
    change_percent = _num(change_percent)

    if price <= 0:
        return {
            "bias": "UNKNOWN",
            "bias_reason": "A valid live index price is not available.",
            "bias_factors": ["Price unavailable"],
            "market_type": "VOLATILITY" if "VIX" in name else "EQUITY_INDEX",
        }

    if "VIX" in name:
        if change_percent >= 0.5:
            bias = "VOLATILITY UP"
            reason = "Implied volatility is rising; this signals higher expected market movement, not a bullish index trend."
        elif change_percent <= -0.5:
            bias = "VOLATILITY EASING"
            reason = "Implied volatility is falling; this signals easing expected market movement, not a bullish index trend."
        else:
            bias = "VOLATILITY STABLE"
            reason = "Implied volatility is relatively unchanged; this is a volatility reading, not a directional market signal."
        return {
            "bias": bias,
            "bias_reason": reason,
            "bias_factors": [f"Daily VIX change {change_percent:+.2f}%"],
            "market_type": "VOLATILITY",
            "volatility_read": bias.replace("VOLATILITY ", "").replace("UP", "RISING").replace("EASING", "FALLING").replace("STABLE", "STABLE"),
        }

    factors = []
    score = 0
    midpoint = 0.0
    breakout = resistance * 1.001 if resistance > 0 else 0.0

    if support > 0 and resistance > support:
        midpoint = support + (resistance - support) * 0.5
        location = (price - support) / (resistance - support)
        if location >= 0.60:
            score += 1
            factors.append("Price is in the upper part of the observed range")
        elif location <= 0.40:
            score -= 1
            factors.append("Price is in the lower part of the observed range")
        else:
            factors.append("Price is in the middle of the observed range")

    if change_percent >= 0.35:
        score += 1
        factors.append(f"Positive daily momentum ({change_percent:+.2f}%)")
    elif change_percent <= -0.35:
        score -= 1
        factors.append(f"Negative daily momentum ({change_percent:+.2f}%)")
    else:
        factors.append(f"Daily momentum is muted ({change_percent:+.2f}%)")

    if resistance > 0 and price >= breakout:
        score += 1
        factors.append("Price is above the breakout-confirmation level")
    elif resistance > 0 and price >= resistance * 0.995:
        factors.append("Price is testing the observed resistance; breakout is not confirmed")

    if support > 0 and price < support * 0.999:
        score -= 2
        factors.append("Price is below the observed support proxy")
    elif support > 0 and price <= support * 1.005:
        factors.append("Price is close to the observed support proxy")

    if score >= 2:
        bias = "BULLISH"
    elif score <= -2:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    if not factors:
        factors.append("Insufficient price-structure information")
    reason = "; ".join(factors) + "."
    return {
        "bias": bias,
        "bias_reason": reason,
        "bias_factors": factors,
        "market_type": "EQUITY_INDEX",
    }


def classify_bias(price, support, resistance, change_percent=0, name=""):
    """Backward-compatible bias label helper."""
    return analyze_index_bias(name, price, support, resistance, change_percent)["bias"]


def _target_zones(price, support, resistance):
    price, support, resistance = map(_num, (price, support, resistance))
    if price <= 0:
        return {
            "target_1": 0, "target_2": 0, "target_3": 0,
            "support_1": 0, "support_2": 0, "breakout_confirmation": 0,
        }

    observed_range = abs(resistance - support) if resistance > support > 0 else 0
    span = max(price * 0.005, observed_range * 0.5)
    breakout = resistance * 1.001 if resistance > price else price + max(price * 0.002, span * 0.25)
    target_1 = breakout + span
    target_2 = target_1 + span
    target_3 = target_2 + span

    support_1 = support if 0 < support < price else price - span
    support_2 = min(support_1 - span, price - 2 * span)
    return {
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "target_3": round(target_3, 2),
        "support_1": round(support_1, 2),
        "support_2": round(support_2, 2),
        "breakout_confirmation": round(breakout, 2),
    }


def build_index_snapshot(name, price, support=0, resistance=0, change=0, change_percent=0):
    """Create the stable JSON shape used by index cards and detailed analysis."""
    price, support, resistance = _num(price), _num(support), _num(resistance)
    change, change_percent = _num(change), _num(change_percent)
    bias_data = analyze_index_bias(name, price, support, resistance, change_percent)
    targets = _target_zones(price, support, resistance)
    is_volatility = bias_data["market_type"] == "VOLATILITY"

    # A narrow pullback-watch band, deliberately distinct from a live-price quote.
    entry_low = round(price * 0.992, 2) if price > 0 else 0
    entry_high = round(price * 0.997, 2) if price > 0 else 0

    snapshot = {
        "name": name,
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "level_basis": "ANGEL ONE INTRADAY HIGH/LOW PROXY",
        "market_type": bias_data["market_type"],
        "bias": bias_data["bias"],
        "bias_reason": bias_data["bias_reason"],
        "bias_factors": bias_data["bias_factors"],
        "target_zones": {} if is_volatility else {
            "target_1": targets["target_1"],
            "target_2": targets["target_2"],
            "target_3": targets["target_3"],
        },
        "downside_zones": {} if is_volatility else {
            "support_1": targets["support_1"],
            "support_2": targets["support_2"],
        },
        "breakout_confirmation": 0 if is_volatility else targets["breakout_confirmation"],
    }
    if not is_volatility:
        snapshot["entry_zone"] = {
            "low": entry_low,
            "high": entry_high,
            "type": "PULLBACK WATCH ZONE",
            "note": "Indicative 0.3%–0.8% pullback band; wait for price-hold confirmation. Not an automatic entry signal.",
        }
    if is_volatility:
        snapshot["volatility_read"] = bias_data.get("volatility_read", "STABLE")
        snapshot["volatility_note"] = "India VIX measures expected volatility; it is not a directional equity-index signal."
    return snapshot
