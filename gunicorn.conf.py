"""Gunicorn configuration for Azad AI Plus.

Keep this file limited to normal Gunicorn settings. Flask routes belong in
app.py; the runtime hooks below only configure Jinja and Phase 1 core APIs.
"""

bind = "0.0.0.0:10000"
workers = 1
worker_class = "sync"
timeout = 180
graceful_timeout = 30
keepalive = 5


def post_worker_init(worker):
    """Run safe application startup hooks after Flask is loaded."""
    app_module = __import__("app")
    flask_app = app_module.app
    # Preserve the existing CSS/Jinja delimiter workaround.
    flask_app.jinja_env.comment_start_string = "{##"

    try:
        from phase1_core import register_phase1_routes
        register_phase1_routes(flask_app)
    except Exception as error:
        print("PHASE 1 ROUTE REGISTRATION WARNING:", error)
