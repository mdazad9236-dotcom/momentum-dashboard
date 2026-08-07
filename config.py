import os

# Application
APP_NAME = "Momentum Dashboard"
VERSION = "2.0.0"

# Admin Login
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

# Security
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY"
)

# Stock Settings
DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"

# Dashboard
REFRESH_SECONDS = 30

# AI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
