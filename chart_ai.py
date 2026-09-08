import base64
import os
import requests
from flask import jsonify, request, session

MAX_CHART_AI_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _api_key():
    return (os.getenv("OPENAI_API_KEY") or os.getenv("NEWSDATA") or os.getenv("newsdata") or os.getenv("NEWS_DATA"))


def _extract_output_text(payload):
    if isinstance(payload, dict) and payload.get("output_text"):
        return payload["output_text"]
    parts = []
    for item in (payload.get("output") or []) if isinstance(payload, dict) else []:
        for content in (item.get("content") or []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def _call_ai(prompt):
    api_key = _api_key()
    if not api_key:
        return None, "Chart AI is not configured. Add OPENAI_API_KEY (or the existing NEWSDATA key) to Render."
    model = os.getenv("CHART_AI_MODEL", "gpt-5.6-luna")
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]},
            timeout=90,
        )
        try:
            payload = response.json()
        except Exception:
            payload = {"error": {"message": response.text[:500]}}
        if not response.ok:
            message = ((payload.get("error") or {}).get("message") if isinstance(payload, dict) else None) or "OpenAI Chart AI request failed."
            return None, message
        answer = _extract_output_text(payload)
        if not answer:
            return None, "Chart AI returned no text result."
        return {"answer": answer, "model": model}, None
    except requests.RequestException as error:
        return None, f"Chart AI network error: {error}"
    except Exception as error:
        return None, f"Chart AI error: {error}"


def analyze_chart_data():
    if session.get("authenticated") is not True:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    body = request.get_json(silent=True) or {}
    instrument = body.get("instrument") or {}
    candles = body.get("candles") or []
    if not isinstance(candles, list) or not candles:
        return jsonify({"success": False, "message": "No historical candles were supplied for this instrument."}), 400

    normalized = []
    for row in candles[-100:]:
        if isinstance(row, (list, tuple)) and len(row) >= 6:
            normalized.append({"time": row[0], "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5]})
        elif isinstance(row, dict):
            normalized.append({
                "time": row.get("time") or row.get("Datetime") or row.get("date"),
                "open": row.get("open") or row.get("Open"),
                "high": row.get("high") or row.get("High"),
                "low": row.get("low") or row.get("Low"),
                "close": row.get("close") or row.get("Close"),
                "volume": row.get("volume") or row.get("Volume"),
            })

    prompt = (
        "You are Chart AI inside Azad AI Plus. Analyze the selected instrument using the supplied OHLCV candle data "
        "and the X10/technical context. This is decision support, not a guaranteed trading signal. "
        "Do not invent prices or indicators. Base conclusions on the supplied data.\n\n"
        "Return a concise but useful analysis with these headings:\n"
        "1. CHART STATE — trend, momentum and setup maturity.\n"
        "2. KEY LEVELS — recent support/resistance and breakout/breakdown areas; label them approximate.\n"
        "3. X10 ALIGNMENT — how the chart evidence agrees or conflicts with the supplied X10 fields.\n"
        "4. ACTION ZONE — WATCH, WAIT, or potentially actionable, and why.\n"
        "5. RISK / INVALIDATION — what would weaken or invalidate the setup.\n"
        "6. NEXT CHECK — the most important candle/price/volume confirmation to wait for.\n\n"
        f"Instrument/X10 context:\n{instrument}\n\n"
        f"Recent OHLCV candles (oldest to newest):\n{normalized}"
    )
    result, error = _call_ai(prompt)
    if error:
        return jsonify({"success": False, "message": error}), 502
    return jsonify({"success": True, **result, "symbol": instrument.get("symbol") or instrument.get("name")})


def analyze_chart_attachment():
    if session.get("authenticated") is not True:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"success": False, "message": "Please select an image or PDF."}), 400
    raw = upload.read(MAX_CHART_AI_BYTES + 1)
    if len(raw) > MAX_CHART_AI_BYTES:
        return jsonify({"success": False, "message": "Attachment is too large. Maximum size is 8 MB."}), 413
    mime = (upload.mimetype or "").lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime != "application/pdf" and mime not in ALLOWED_IMAGES:
        return jsonify({"success": False, "message": "Supported attachments: PDF, JPG/JPEG, PNG and WebP."}), 415
    api_key = _api_key()
    if not api_key:
        return jsonify({"success": False, "message": "Chart AI is not configured. Add OPENAI_API_KEY (or the existing NEWSDATA key) to Render."}), 503
    question = (request.form.get("question") or "Analyze this selected chart or document for the current market setup.").strip()
    instrument = (request.form.get("instrument") or "{}").strip()
    prompt = (
        "You are Chart AI inside Azad AI Plus. Analyze only what is actually visible or extractable. "
        "Do not invent prices, candles, indicators, support, resistance, news, or signals. "
        "If the attachment is unclear, say so. Explain evidence, setup maturity, bullish/bearish clues, "
        "risk/invalidation conditions and what the trader should verify next.\n\n"
        f"Current instrument context: {instrument}\n\nUser request: {question}"
    )
    encoded = base64.b64encode(raw).decode("ascii")
    if mime == "application/pdf":
        content = [{"type": "input_text", "text": prompt}, {"type": "input_file", "filename": upload.filename, "file_data": f"data:application/pdf;base64,{encoded}"}]
    else:
        content = [{"type": "input_text", "text": prompt}, {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}", "detail": "high"}]
    model = os.getenv("CHART_AI_MODEL", "gpt-5.6-luna")
    try:
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": model, "input": [{"role": "user", "content": content}]}, timeout=90)
        try:
            payload = response.json()
        except Exception:
            payload = {"error": {"message": response.text[:500]}}
        if not response.ok:
            message = ((payload.get("error") or {}).get("message") if isinstance(payload, dict) else None) or "OpenAI Chart AI request failed."
            return jsonify({"success": False, "message": message}), 502
        answer = _extract_output_text(payload)
        if not answer:
            return jsonify({"success": False, "message": "Chart AI returned no text result."}), 502
        return jsonify({"success": True, "answer": answer, "model": model, "filename": upload.filename})
    except requests.RequestException as error:
        return jsonify({"success": False, "message": f"Chart AI network error: {error}"}), 502
    except Exception as error:
        return jsonify({"success": False, "message": f"Chart AI error: {error}"}), 500


def register_chart_ai_routes(app):
    if "chart_ai_attachment" not in app.view_functions:
        app.add_url_rule("/api/chart-ai", endpoint="chart_ai_attachment", view_func=analyze_chart_attachment, methods=["POST"])
    if "chart_ai_data" not in app.view_functions:
        app.add_url_rule("/api/chart-ai/data", endpoint="chart_ai_data", view_func=analyze_chart_data, methods=["POST"])
