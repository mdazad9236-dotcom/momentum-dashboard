"""Chart resilience layer with provider-independent Yahoo chart fallback."""
from __future__ import annotations

import importlib
import math
import time

import requests
from flask import jsonify

YAHOO_CHART_HOSTS = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
)
YAHOO_TIMEOUT = (5, 15)


def _clean_symbol(symbol):
    clean = str(symbol or "").upper().strip()
    return clean.replace(".NS", "").replace(".BO", "")


def _number(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _parse_yahoo(payload, clean):
    chart = payload.get("chart") or {}
    result = (chart.get("result") or [None])[0]
    if not isinstance(result, dict):
        error = (chart.get("error") or {}).get("description", "Yahoo returned no chart result.")
        return None, str(error)
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens, highs = quote.get("open") or [], quote.get("high") or []
    lows, closes = quote.get("low") or [], quote.get("close") or []
    volumes = quote.get("volume") or []
    rows = []
    for i, epoch in enumerate(timestamps):
        if i >= len(opens) or i >= len(highs) or i >= len(lows) or i >= len(closes):
            continue
        o, h = _number(opens[i]), _number(highs[i])
        low, c = _number(lows[i]), _number(closes[i])
        v = _number(volumes[i] if i < len(volumes) else 0, 0)
        if None in (o, h, low, c):
            continue
        rows.append([int(epoch), o, h, low, c, v or 0])
    if not rows:
        return None, f"Yahoo returned no usable candles for {clean}."
    return rows, ""


def fetch_yahoo_chart(symbol, period="1y", interval="1d"):
    """Fetch Yahoo's public chart endpoint directly, trying both Yahoo API hosts."""
    clean = _clean_symbol(symbol)
    if not clean:
        return {"success": False, "message": "Stock symbol is required.", "data": []}
    params = {"range": period, "interval": interval, "events": "history", "includeAdjustedClose": "true"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    errors = []
    for host in YAHOO_CHART_HOSTS:
        url = host.format(symbol=f"{clean}.NS")
        for attempt in range(2):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=YAHOO_TIMEOUT)
                response.raise_for_status()
                rows, parse_error = _parse_yahoo(response.json(), clean)
                if rows:
                    return {"success": True, "symbol": clean, "interval": "ONE_DAY", "count": len(rows), "data": rows, "data_source": "YAHOO CHART API", "message": ""}
                errors.append(f"{url.split('/')[2]}: {parse_error}")
                break
            except Exception as error:
                errors.append(f"{url.split('/')[2]}: {error}")
                if attempt == 0:
                    time.sleep(0.4)
    return {"success": False, "message": "Yahoo chart fallback unavailable. " + " | ".join(errors[-4:]), "data": []}


def register_chart_resilience(flask_app) -> None:
    if flask_app.config.get("X10_CHART_RESILIENCE_REGISTERED"):
        return
    flask_app.config["X10_CHART_RESILIENCE_REGISTERED"] = True

    @flask_app.route("/api/chart-data/<path:symbol>")
    def chart_data(symbol):
        app_module = importlib.import_module("app")
        if getattr(app_module, "is_authenticated", lambda: False)() is not True:
            return jsonify({"success": False, "authenticated": False, "message": "Authentication required.", "data": []}), 401
        result = fetch_yahoo_chart(symbol)
        return jsonify(result), 200 if result.get("success") else 502


def install_fetch_resilience_script(flask_app, response):
    try:
        if "text/html" not in response.headers.get("Content-Type", ""):
            return response
        body = response.get_data(as_text=True)
        if "/static/chart_resilience.js" in body or "</body>" not in body:
            return response
        response.set_data(body.replace("</body>", '<script src="/static/chart_resilience.js?v=3" defer></script></body>'))
    except Exception as error:
        print("CHART RESILIENCE HTML INJECTION WARNING:", error)
    return response
