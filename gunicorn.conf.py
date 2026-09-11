"""Gunicorn configuration for Azad AI Plus.

Keep this file limited to normal Gunicorn settings and startup hooks. Flask
routes remain in app.py/modules loaded after the application exists.
"""

bind = "0.0.0.0:10000"
workers = 1
worker_class = "sync"
timeout = 180
graceful_timeout = 30
keepalive = 5


def post_worker_init(worker):
    """Apply startup hooks after the Flask app is loaded."""
    app_module = __import__("app")
    flask_app = app_module.app
    flask_app.jinja_env.comment_start_string = "{##}"
