"""Gunicorn runtime hooks for the Azad AI Plus dashboard.

Keeps the existing Flask application intact while adding the individual
instrument historical-data endpoint and the approved single-page popup layout.
"""

import json
import threading


def post_worker_init(worker):
    app_module = __import__("app")
    flask_app = app_module.app

    # Register the historical endpoint once per worker.  The front-end uses
    # this endpoint for both stocks and indices.
    if "historical_external" not in flask_app.view_functions:
        def historical_external(symbol):
            from flask import jsonify
            try:
                if not app_module.is_authenticated():
                    return jsonify({"success": False, "authenticated": False, "message": "Authentication required.", "data": []}), 401
                instrument = app_module.instrument_manager.find_stock(symbol)
                if not instrument:
                    return jsonify({"success": False, "message": f"Angel One instrument not found: {symbol}", "data": []}), 404
                result = app_module.angel_service.get_historical_data(
                    instrument["symbol"],
                    instrument["token"],
                    days=400,
                    interval="ONE_DAY",
                    exchange=instrument.get("exchange", "NSE"),
                )
                return jsonify(result), (200 if result.get("success") else 502)
            except Exception as error:
                print("HISTORICAL API ERROR:", error)
                return jsonify({"success": False, "message": str(error), "data": []}), 500

        flask_app.add_url_rule(
            "/api/historical/<path:symbol>",
            endpoint="historical_external",
            view_func=historical_external,
            methods=["GET"],
        )

    # Make the existing popup a single analysis workspace:
    # chart on the left, Stock/Index DNA and Trade Plan on the right.
    @flask_app.after_request
    def azad_single_page_popup(response):
        if flask_app.request_context if False else False:
            pass
        try:
            from flask import request
            if request.path != "/" or "text/html" not in response.content_type:
                return response
            html = response.get_data(as_text=True)
            css = r"""
<style id="azad-single-analysis-layout">
.az-tabs{display:none!important}
.az-content{display:grid!important;grid-template-columns:minmax(0,1.7fr) minmax(300px,.85fr);grid-template-rows:minmax(0,1fr) minmax(0,1fr);gap:12px;overflow:hidden!important;padding:12px}
#azPanelChart{display:block!important;grid-column:1;grid-row:1 / 3;min-width:0;min-height:0}
#azPanelDna{display:block!important;grid-column:2;grid-row:1;min-width:0;min-height:0;overflow:auto}
#azPanelTrade{display:block!important;grid-column:2;grid-row:2;min-width:0;min-height:0;overflow:auto}
#azPanelChart .az-chart-wrap{height:calc(100% - 92px);min-height:360px}
#azPanelChart .az-chart-toolbar{position:sticky;top:0;z-index:4;background:#071522;padding-bottom:7px}
#azPanelDna .az-grid,#azPanelTrade .az-grid{grid-template-columns:1fr}
@media(max-width:900px){.az-content{grid-template-columns:1fr;grid-template-rows:auto auto auto;overflow:auto!important}#azPanelChart{grid-column:1;grid-row:1}#azPanelDna{grid-column:1;grid-row:2}#azPanelTrade{grid-column:1;grid-row:3}#azPanelChart .az-chart-wrap{height:430px;min-height:0}}
@media(max-width:600px){#azPanelChart .az-chart-wrap{height:360px}.az-content{padding:8px}}
</style>
"""
            if 'id="azad-single-analysis-layout"' not in html:
                html = html.replace("</head>", css + "</head>", 1)
                response.set_data(html)
        except Exception as error:
            print("AZAD POPUP LAYOUT INJECTION ERROR:", error)
        return response
