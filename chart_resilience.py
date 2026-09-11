"""Chart resilience layer."""
from __future__ import annotations
import importlib
from flask import jsonify

def register_chart_resilience(flask_app) -> None:
    if flask_app.config.get("X10_CHART_RESILIENCE_REGISTERED"):
        return
    flask_app.config["X10_CHART_RESILIENCE_REGISTERED"] = True

    @flask_app.route("/api/chart-data/<path:symbol>")
    def chart_data(symbol):
        app_module = importlib.import_module("app")
        if getattr(app_module, "is_authenticated", lambda: False)() is not True:
            return jsonify({"success": False, "authenticated": False, "message": "Authentication required.", "data": []}), 401
        clean = str(symbol or "").upper().strip().replace(".NS", "").replace(".BO", "")
        if not clean:
            return jsonify({"success": False, "message": "Stock symbol is required.", "data": []}), 400
        try:
            import yfinance as yf
            history = yf.Ticker(f"{clean}.NS").history(period="1y", interval="1d", auto_adjust=False)
            if history is None or history.empty:
                return jsonify({"success": False, "message": f"No fallback chart data found for {clean}.", "data": []}), 404
            rows=[]
            for idx,row in history.iterrows():
                vals=[row.get("Open"),row.get("High"),row.get("Low"),row.get("Close"),row.get("Volume",0)]
                try:
                    nums=[float(x) for x in vals]
                except (TypeError,ValueError):
                    continue
                rows.append([idx.isoformat(),*nums])
            return jsonify({"success": bool(rows),"symbol":clean,"interval":"ONE_DAY","count":len(rows),"data":rows,"data_source":"YAHOO FALLBACK","message":"" if rows else "No fallback candles found."})
        except Exception as error:
            return jsonify({"success": False,"message":f"Fallback chart data failed: {error}","data":[]}),502

def install_fetch_resilience_script(flask_app,response):
    try:
        if "text/html" not in response.headers.get("Content-Type",""):
            return response
        body=response.get_data(as_text=True)
        if "/static/chart_resilience.js" in body or "</body>" not in body:
            return response
        response.set_data(body.replace("</body>",'<script src="/static/chart_resilience.js?v=1" defer></script></body>'))
    except Exception as error:
        print("CHART RESILIENCE HTML INJECTION WARNING:",error)
    return response
