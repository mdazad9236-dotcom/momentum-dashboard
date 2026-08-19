"""Gunicorn configuration for Azad AI Plus.

Keep this file limited to normal Gunicorn settings. Flask routes and response
hooks belong in app.py so application startup is deterministic on Render.
"""

bind = "0.0.0.0:10000"
workers = 1
worker_class = "sync"
timeout = 180
graceful_timeout = 30
keepalive = 5
