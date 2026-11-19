web: gunicorn --workers 1 --threads 4 --timeout 120 --graceful-timeout 30 --keep-alive 5 --max-requests 500 --max-requests-jitter 50 app:app
