"""Phase 1 X10 core layer.

Keeps backend contracts, caching, diagnostics and JARVIS-facing APIs in one
place without changing the Phase 2 dashboard UI or X10 scoring rules.
"""

from __future__ import annotations

import importlib
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Dict

from flask import jsonify


_CACHE_LOCK = threading.RLock()
_STOCK_CACHE: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_CACHE_TTL = max(15, int(os.getenv("X10_ANALYSIS_CACHE_TTL", "120")))
_CACHE_MAX = max(10, int(os.getenv("X10_ANALYSIS_CACHE_MAX", "64")))


def _as_number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number == number else default
    except (TypeError, ValueError):
        return default


def canonical_stock_payload(symbol: str, analysis: Dict[str, Any], x10: Dict[str, Any]) -> Dict[str, Any]:
    """Return one stable analysis contract for Web, JARVIS and future mobile clients."""
    trade = {
        "entry": x10.get("entry", 0),
        "entry_low": x10.get("entry_low", 0),
        "entry_high": x10.get("entry_high", 0),
        "stop_loss": x10.get("stop_loss", 0),
        "target_1": x10.get("target_1", x10.get("target", 0)),
        "target_2": x10.get("target_2", 0),
        "trailing_stop": x10.get("trailing_stop", 0),
        "risk": x10.get("risk", 0),
        "reward": x10.get("reward", 0),
        "risk_reward": x10.get("risk_reward_value", x10.get("risk_reward", 0)),
        "risk_reward_display": x10.get("risk_reward_display", x10.get("risk_reward", "1:0")),
        "dont_chase": bool(x10.get("dont_chase", False)),
    }
    technical = {
        "trend": analysis.get("trend", "Neutral"),
        "momentum": analysis.get("momentum", "Neutral"),
        "rsi": analysis.get("rsi", 0),
        "ema20": analysis.get("ema20", 0),
        "ema50": analysis.get("ema50", 0),
        "ema200": analysis.get("ema200", 0),
        "macd": analysis.get("macd", 0),
        "macd_signal": analysis.get("macd_signal", 0),
        "macd_histogram": analysis.get("macd_histogram", 0),
        "adx": analysis.get("adx", 0),
        "plus_di": analysis.get("plus_di", 0),
        "minus_di": analysis.get("minus_di", 0),
        "support": analysis.get("support", 0),
        "resistance": analysis.get("resistance", 0),
        "volume_ratio": analysis.get("volume_ratio", 0),
        "atr": analysis.get("atr", 0),
        "52_week_high": analysis.get("52_week_high", 0),
        "52_week_low": analysis.get("52_week_low", 0),
    }
    return {
        "contract_version": "phase1.v1",
        "symbol": symbol.upper().strip(),
        "price": analysis.get("price", 0),
        "technical_score": analysis.get("technical_score", 0),
        "x10": {
            "score": x10.get("x10_score", 0),
            "base_score": x10.get("base_x10_score", 0),
            "signal": x10.get("signal", "AVOID"),
            "success_probability": x10.get("x10_score", 0),
            "setup_quality": x10.get("setup_quality", "WEAK"),
            "early_momentum_score": x10.get("early_momentum_score", 0),
            "momentum_stage": x10.get("momentum_stage", "NOT EARLY"),
            "early_momentum_reasons": x10.get("early_momentum_reasons", []),
            "validation": x10.get("validation", []),
            "why_buy": x10.get("why_buy", ""),
            "why_not_buy": x10.get("why_not_buy", ""),
        },
        "technical": technical,
        "trade_plan": trade,
        "meta": {
            "source": "X10 CORE",
            "generated_at": time.time(),
        },
    }


def _get_cached(symbol: str) -> dict | None:
    now = time.time()
    with _CACHE_LOCK:
        item = _STOCK_CACHE.get(symbol)
        if not item:
            return None
        created, payload = item
        if now - created >= _CACHE_TTL:
            _STOCK_CACHE.pop(symbol, None)
            return None
        _STOCK_CACHE.move_to_end(symbol)
        return dict(payload)


def _put_cached(symbol: str, payload: dict) -> None:
    with _CACHE_LOCK:
        _STOCK_CACHE[symbol] = (time.time(), dict(payload))
        _STOCK_CACHE.move_to_end(symbol)
        while len(_STOCK_CACHE) > _CACHE_MAX:
            _STOCK_CACHE.popitem(last=False)


def clear_phase1_cache() -> None:
    with _CACHE_LOCK:
        _STOCK_CACHE.clear()


def _auth_required(app_module) -> bool:
    return bool(getattr(app_module, "is_authenticated", lambda: False)())


def _analyze_stock(symbol: str, app_module) -> dict:
    clean = symbol.upper().strip().replace(".NS", "").replace(".BO", "")
    cached = _get_cached(clean)
    if cached is not None:
        cached["meta"] = {**cached.get("meta", {}), "cache": "HIT", "generated_at": time.time()}
        return cached

    instrument_manager = app_module.instrument_manager
    angel_service = app_module.angel_service
    instrument = instrument_manager.find_stock(clean)
    if not instrument:
        raise LookupError(f"Angel One instrument not found: {clean}")

    from analysis import TechnicalAnalyzer
    from x10_engine import X10Engine

    dataframe = angel_service.get_historical_dataframe(
        instrument["symbol"],
        instrument["token"],
        days=100,
        interval="ONE_DAY",
        exchange=instrument.get("exchange", "NSE"),
    )
    if dataframe is None or dataframe.empty:
        raise RuntimeError(f"No historical data available for {clean}")

    technical = TechnicalAnalyzer(dataframe).calculate()
    if not technical:
        raise RuntimeError(f"Technical analysis unavailable for {clean}")
    x10 = X10Engine().analyze({**technical, "price": technical.get("price", 0)})
    if not x10:
        raise RuntimeError(f"X10 analysis unavailable for {clean}")

    payload = canonical_stock_payload(clean, technical, x10)
    payload["meta"] = {
        **payload["meta"],
        "cache": "MISS",
        "data_source": "ANGEL ONE",
        "instrument_token": str(instrument.get("token", "")),
    }
    _put_cached(clean, payload)
    return payload


def _diagnostics(app_module) -> dict:
    checks: Dict[str, dict] = OrderedDict()

    required_env = ("ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PASSWORD", "ANGEL_TOTP_SECRET")
    missing = [name for name in required_env if not os.getenv(name)]
    checks["angel_one_config"] = {"status": "OK" if not missing else "DEGRADED", "missing": missing}

    try:
        from angel_service import AngelOneService
        session_ok = bool(AngelOneService._shared_logged_in and AngelOneService._shared_api is not None)
        checks["angel_one_session"] = {"status": "OK" if session_ok else "IDLE", "logged_in": session_ok}
    except Exception as error:
        checks["angel_one_session"] = {"status": "ERROR", "error": str(error)}

    scan_state = getattr(app_module, "_scan_state", {})
    index_state = getattr(app_module, "_index_state", {})
    scan_updated = _as_number(scan_state.get("updated_at"), 0)
    index_updated = _as_number(index_state.get("updated_at"), 0)
    now = time.time()
    checks["scanner_cache"] = {
        "status": "OK" if scan_updated else "IDLE",
        "age_seconds": round(now - scan_updated, 1) if scan_updated else None,
        "refreshing": bool(scan_state.get("refreshing")),
        "last_error": scan_state.get("last_error"),
    }
    checks["index_cache"] = {
        "status": "OK" if index_updated else "IDLE",
        "age_seconds": round(now - index_updated, 1) if index_updated else None,
        "refreshing": bool(index_state.get("refreshing")),
        "last_error": index_state.get("last_error"),
    }

    for module_name, label in (("x10_engine", "x10_engine"), ("analysis", "technical_analysis"), ("chart_ai", "chart_ai")):
        try:
            importlib.import_module(module_name)
            checks[label] = {"status": "OK"}
        except Exception as error:
            checks[label] = {"status": "ERROR", "error": str(error)}

    with _CACHE_LOCK:
        checks["phase1_stock_cache"] = {"status": "OK", "entries": len(_STOCK_CACHE), "ttl_seconds": _CACHE_TTL}

    statuses = [item.get("status") for item in checks.values()]
    overall = "OK" if all(s in ("OK", "IDLE") for s in statuses) else "DEGRADED"
    return {"contract_version": "phase1.v1", "status": overall, "generated_at": now, "checks": checks}


def register_phase1_routes(flask_app) -> None:
    """Register Phase 1 APIs after the Flask app exists."""
    if flask_app.config.get("X10_PHASE1_REGISTERED"):
        return
    flask_app.config["X10_PHASE1_REGISTERED"] = True

    def authenticated_module():
        return importlib.import_module("app")

    @flask_app.route("/api/v1/system/health")
    def phase1_health():
        app_module = authenticated_module()
        if not _auth_required(app_module):
            return jsonify({"success": False, "authenticated": False, "message": "Authentication required."}), 401
        try:
            payload = _diagnostics(app_module)
            code = 200 if payload["status"] != "ERROR" else 503
            return jsonify({"success": True, **payload}), code
        except Exception as error:
            return jsonify({"success": False, "contract_version": "phase1.v1", "status": "ERROR", "message": str(error)}), 500

    @flask_app.route("/api/v1/market/snapshot")
    def phase1_snapshot():
        app_module = authenticated_module()
        if not _auth_required(app_module):
            return jsonify({"success": False, "authenticated": False, "message": "Authentication required."}), 401
        try:
            payload = app_module._snapshot_response()
            return jsonify({"success": True, "contract_version": "phase1.v1", "snapshot": payload, "generated_at": time.time()})
        except Exception as error:
            return jsonify({"success": False, "contract_version": "phase1.v1", "message": str(error)}), 500

    @flask_app.route("/api/v1/stock/<path:symbol>")
    def phase1_stock(symbol):
        app_module = authenticated_module()
        if not _auth_required(app_module):
            return jsonify({"success": False, "authenticated": False, "message": "Authentication required."}), 401
        try:
            payload = _analyze_stock(symbol, app_module)
            return jsonify({"success": True, **payload})
        except LookupError as error:
            return jsonify({"success": False, "contract_version": "phase1.v1", "message": str(error)}), 404
        except Exception as error:
            return jsonify({"success": False, "contract_version": "phase1.v1", "message": str(error)}), 502

    @flask_app.route("/api/v1/core/cache/clear", methods=["POST"])
    def phase1_cache_clear():
        app_module = authenticated_module()
        if not _auth_required(app_module):
            return jsonify({"success": False, "authenticated": False, "message": "Authentication required."}), 401
        clear_phase1_cache()
        return jsonify({"success": True, "contract_version": "phase1.v1", "message": "Phase 1 stock-analysis cache cleared."})
