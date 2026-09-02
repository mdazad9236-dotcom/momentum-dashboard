import os
import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import pyotp
from SmartApi import SmartConnect


class AngelOneService:
    # Share one authenticated SmartConnect session across all service instances
    # in the Flask process. The app runs index refresh and X10 scan workers in
    # separate threads; creating separate Angel sessions from those workers can
    # trigger Angel One's login-rate limit.
    _session_lock = threading.RLock()
    _shared_api = None
    _shared_logged_in = False
    _shared_client_code = None

    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_code = os.getenv("ANGEL_CLIENT_CODE")
        self.password = os.getenv("ANGEL_PASSWORD")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")
        self.smart_api = None
        self.logged_in = False

    def login(self):
        with AngelOneService._session_lock:
            if (
                AngelOneService._shared_logged_in
                and AngelOneService._shared_api is not None
                and AngelOneService._shared_client_code == self.client_code
            ):
                self.smart_api = AngelOneService._shared_api
                self.logged_in = True
                return {"success": True, "message": "Angel One shared session already active."}

            missing = [
                name for name, value in (
                    ("ANGEL_API_KEY", self.api_key),
                    ("ANGEL_CLIENT_CODE", self.client_code),
                    ("ANGEL_PASSWORD", self.password),
                    ("ANGEL_TOTP_SECRET", self.totp_secret),
                ) if not value
            ]
            if missing:
                return {"success": False, "message": "Missing Angel One environment variables: " + ", ".join(missing)}

            last_error = None
            for attempt in range(1, 3):
                try:
                    self.smart_api = SmartConnect(api_key=self.api_key)
                    self.smart_api.timeout = 20
                    response = self.smart_api.generateSession(
                        self.client_code,
                        self.password,
                        pyotp.TOTP(self.totp_secret).now(),
                    )
                    if response and response.get("status"):
                        AngelOneService._shared_api = self.smart_api
                        AngelOneService._shared_logged_in = True
                        AngelOneService._shared_client_code = self.client_code
                        self.logged_in = True
                        return {"success": True, "message": "Angel One login successful."}

                    message = (response or {}).get("message", "Angel One login failed.")
                    last_error = message
                    if "access denied" in str(message).lower() or "rate" in str(message).lower():
                        if attempt < 2:
                            time.sleep(3)
                            continue
                    break
                except Exception as error:
                    last_error = str(error)
                    if "access denied" in last_error.lower() or "rate" in last_error.lower():
                        if attempt < 2:
                            time.sleep(3)
                            continue
                    break

            self.smart_api = None
            self.logged_in = False
            AngelOneService._shared_api = None
            AngelOneService._shared_logged_in = False
            return {"success": False, "message": f"Angel One login error: {last_error or 'login failed.'}"}

    def get_market_data_service(self):
        login_result = self.login()
        if not login_result.get("success"):
            return login_result
        return {"success": True, "service": self}

    def get_quotes(self, instruments):
        """Fetch multiple quotes in bounded batches and preserve instrument metadata."""
        login_result = self.login()
        if not login_result.get("success"):
            return {"success": False, "message": login_result.get("message", "Angel One login failed."), "quotes": []}
        if not instruments:
            return {"success": True, "quotes": []}
        grouped, lookup = {}, {}
        for item in instruments:
            exchange = str(item.get("exchange", "NSE"))
            token = str(item.get("token", ""))
            if token:
                grouped.setdefault(exchange, []).append(token)
                lookup[(exchange, token)] = item
        try:
            quotes = []
            for exchange, tokens in grouped.items():
                for offset in range(0, len(tokens), 50):
                    response = self.smart_api.getMarketData("FULL", {exchange: tokens[offset:offset + 50]})
                    if not response or not response.get("status"):
                        print(f"Market-data batch failed for {exchange}: {(response or {}).get('message', 'unknown error')}")
                        continue
                    for quote in (response.get("data") or {}).get("fetched") or []:
                        token = str(quote.get("symbolToken", quote.get("symboltoken", "")))
                        quotes.append({**lookup.get((exchange, token), {}), **quote, "token": token, "exchange": exchange})
            return {"success": True, "quotes": quotes}
        except Exception as error:
            return {"success": False, "message": str(error), "quotes": []}

    def get_quote(self, symbol, token, exchange="NSE"):
        result = self.get_quotes([{"symbol": symbol, "token": token, "exchange": exchange}])
        row = result.get("quotes", [{}])[0] if result.get("quotes") else {}
        return {"success": bool(result.get("success")), "symbol": symbol, "token": str(token), "exchange": exchange, "data": {"fetched": [row] if row else []}, "message": result.get("message", "")}

    def get_ltp(self, exchange, tradingsymbol, symboltoken):
        result = self.get_quote(tradingsymbol, symboltoken, exchange)
        fetched = (result.get("data") or {}).get("fetched") or []
        if not result.get("success") or not fetched:
            return {"success": False, "message": result.get("message", "No LTP data returned by Angel One."), "data": result}
        return {"success": True, "exchange": exchange, "tradingsymbol": tradingsymbol, "symboltoken": str(symboltoken), "ltp": fetched[0].get("ltp", 0), "data": fetched[0]}

    def get_historical_data(self, symbol, token, days=200, interval="ONE_DAY", exchange="NSE"):
        login_result = self.login()
        if not login_result.get("success"):
            return {"success": False, "message": login_result.get("message", "Angel One login failed."), "data": []}
        try:
            # Keep interactive chart requests deliberately small. The dashboard
            # only needs a compact working window, while large candle requests
            # can trigger Angel One AB1021 rate limiting and make charts appear
            # blank. The X10 calculations already use their own bounded windows.
            requested_days = min(int(days), 120)
            to_date = datetime.now()
            from_date = to_date - timedelta(days=requested_days)
            response = self.smart_api.getCandleData({"exchange": exchange, "symboltoken": str(token), "interval": interval, "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
            if not response or not response.get("status"):
                return {"success": False, "message": (response or {}).get("message", "Historical data request failed."), "data": []}
            candles = response.get("data") or []
            return {"success": bool(candles), "symbol": symbol, "token": str(token), "interval": interval, "count": len(candles), "data": candles, "message": "" if candles else "No historical candles found."}
        except Exception as error:
            return {"success": False, "message": f"Historical data request failed: {error}", "data": []}

    def get_historical_dataframe(self, symbol, token, days=100, interval="ONE_DAY", exchange="NSE"):
        result = self.get_historical_data(symbol, token, days, interval, exchange)
        if not result.get("success"):
            return None
        try:
            df = pd.DataFrame(result["data"], columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
            df["Datetime"] = pd.to_datetime(df["Datetime"])
            for column in ["Open", "High", "Low", "Close", "Volume"]:
                df[column] = pd.to_numeric(df[column], errors="coerce")
            return df.dropna(subset=["Open", "High", "Low", "Close"]).set_index("Datetime").sort_index()
        except Exception as error:
            print("Historical dataframe error:", error)
            return None
