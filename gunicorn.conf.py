"""Gunicorn configuration for Azad AI Plus.

Keep this file limited to normal Gunicorn settings. Flask routes belong in
app.py; the only runtime hook below adjusts Jinja's comment delimiter because
the static dashboard CSS contains selectors beginning with `{#`.
"""

bind = "0.0.0.0:10000"
workers = 1
worker_class = "sync"
timeout = 180
graceful_timeout = 30
keepalive = 5


def post_worker_init(worker):
    """Prevent Jinja from treating CSS `{#id}` selectors as comments."""
    app_module = __import__("app")
    flask_app = app_module.app
    flask_app.jinja_env.comment_start_string = "{##"
