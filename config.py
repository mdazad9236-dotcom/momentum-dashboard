import os

# ==========================
# Application Configuration
# ==========================

APP_NAME = "Momentum Dashboard Pro"
APP_VERSION = "1.0.0"

# ==========================
# Login Credentials
# ==========================

ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "Admin"

SECRET_KEY = "momentum-dashboard-super-secret-key"

# ==========================
# Yahoo Finance
# ==========================

DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"

# ==========================
# Scanner Settings
# ==========================

MIN_PRICE = 2

MAX_PRICE = 300

BREAKOUT_TARGET_PERCENT = 16

# ==========================
# Technical Indicator Periods
# ==========================

EMA_FAST = 20
EMA_SLOW = 50
EMA_LONG = 200

RSI_PERIOD = 14

ADX_PERIOD = 14

ATR_PERIOD = 14

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ==========================
# Watchlist
# ==========================

DEFAULT_WATCHLIST = [
    "SBIN",
    "SUZLON",
    "IDEA",
    "YESBANK",
    "TCS",
    "INFY",
    "IRCTC",
    "BEL",
    "CGPOWER",
    "TATASTEEL"
]

# ==========================
# Scanner Universe
# ==========================

SCAN_STOCKS = [
    "SBIN",
    "HDFCBANK",
    "ICICIBANK",
    "AXISBANK",
    "KOTAKBANK",
    "TCS",
    "INFY",
    "HCLTECH",
    "TECHM",
    "WIPRO",
    "BEL",
    "BHEL",
    "CGPOWER",
    "SUZLON",
    "IDEA",
    "YESBANK",
    "JPPOWER",
    "RPOWER",
    "IRB",
    "NBCC",
    "NCC",
    "KEC",
    "RECLTD",
    "IRCTC",
    "POWERGRID",
    "NTPC",
    "ONGC",
    "TATASTEEL",
    "TATAMOTORS",
    "ASHOKLEY",
    "M&M",
    "MARUTI",
    "JINDALSTEL",
    "HINDCOPPER",
    "GRANULES",
    "DEEPAKNTR",
    "LEMONTREE",
    "MSUMI",
    "SAGILITY",
    "OLAELEC",
]
