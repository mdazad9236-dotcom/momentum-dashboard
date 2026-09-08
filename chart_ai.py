import base64
import os
import requests
from flask import jsonify, request, session

MAX_CHART_AI_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _api_key():
    # Keep compatibility with the existing Render setup while also supporting
    # the standard OpenAI variable name. The key never reaches the browser.
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
        "You are Chart AI inside Azad AI Plus, a stock-analysis decision-support system. "
        "The user selected a visual/file as context. Analyze only what is actually visible or extractable. "
        "Do not invent prices, candles, indicators, support, resistance, news, or signals. "
        "If the attachment is unclear, say so. Explain evidence, setup maturity, bullish/bearish clues, "
        "risk/invalidation conditions and what the trader should verify next. This is informational decision support, not a guarantee.\n\n"
        f"Current instrument context: {instrument}\n\nUser request: {question}"
    )

    encoded = base64.b64encode(raw).decode("ascii")
    if mime == "application/pdf":
        content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_file", "filename": upload.filename, "file_data": f"data:application/pdf;base64,{encoded}"},
        ]
    else:
        content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}", "detail": "high"},
        ]

    model = os.getenv("CHART_AI_MODEL", "gpt-5.6-luna")
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": [{"role": "user", "content": content}]},
            timeout=90,
        )
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
    endpoint = "chart_ai_attachment"
    if endpoint not in app.view_functions:
        app.add_url_rule("/api/chart-ai", endpoint=endpoint, view_func=analyze_chart_attachment, methods=["POST"])
