import os
from datetime import datetime, timedelta

import pandas as pd
import pyotp
from SmartApi import SmartConnect


class AngelOneService:

    def __init__(self):

        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_code = os.getenv("ANGEL_CLIENT_CODE")
        self.password = os.getenv("ANGEL_PASSWORD")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        self.smart_api = None
        self.logged_in = False

    # ==========================================================
    # LOGIN
    # ==========================================================

    def login(self):

        # Already logged in
        if self.logged_in and self.smart_api:

            return {
                "success": True,
                "message": "Angel One session already active."
            }

        # Check credentials
        missing = []

        if not self.api_key:
            missing.append("ANGEL_API_KEY")

        if not self.client_code:
            missing.append("ANGEL_CLIENT_CODE")

        if not self.password:
            missing.append("ANGEL_PASSWORD")

        if not self.totp_secret:
            missing.append("ANGEL_TOTP_SECRET")

        if missing:

            return {
                "success": False,
                "message": (
                    "Missing Angel One environment variables: "
                    + ", ".join(missing)
                )
            }

        try:

            self.smart_api = SmartConnect(
                api_key=self.api_key
            )

            # Generate current TOTP
            totp = pyotp.TOTP(
                self.totp_secret
            ).now()

            # Login
            login_response = self.smart_api.generateSession(
                self.client_code,
                self.password,
                totp
            )

            if not login_response:

                self.smart_api = None
                self.logged_in = False

                return {
                    "success": False,
                    "message": (
                        "Empty response from Angel One login."
                    )
                }

            if not login_response.get("status"):

                message = login_response.get(
                    "message",
                    "Angel One login failed."
                )

                self.smart_api = None
                self.logged_in = False

                return {
                    "success": False,
                    "message": message
                }

            self.logged_in = True

            return {
                "success": True,
                "message": "Angel One login successful."
            }

        except Exception as error:

            self.smart_api = None
            self.logged_in = False

            return {
                "success": False,
                "message": (
                    f"Angel One login error: {str(error)}"
                )
            }

    # ==========================================================
    # MARKET DATA SERVICE
    #
    # Compatibility method used by app.py
    # ==========================================================

    def get_market_data_service(self):

        login_result = self.login()

        if not login_result.get("success"):

            return {
                "success": False,
                "message": login_result.get(
                    "message",
                    "Angel One login failed."
                )
            }

        return {
            "success": True,
            "service": self
        }

    # ==========================================================
    # LIVE MARKET DATA
    # ==========================================================

    def get_quote(
        self,
        symbol,
        token,
        exchange="NSE"
    ):

        login_result = self.login()

        if not login_result.get("success"):

            return login_result

        try:

            response = self.smart_api.getMarketData(
                "FULL",
                {
                    exchange: [str(token)]
                }
            )

            if not response:

                return {
                    "success": False,
                    "message": (
                        "Empty response from Angel One market data."
                    )
                }

            if not response.get("status"):

                return {
                    "success": False,
                    "message": response.get(
                        "message",
                        "Market data request failed."
                    ),
                    "data": response
                }

            return {
                "success": True,
                "symbol": symbol,
                "token": str(token),
                "exchange": exchange,
                "data": response
            }

        except Exception as error:

            return {
                "success": False,
                "message": str(error)
            }

    # ==========================================================
    # LIVE LTP
    # ==========================================================

    def get_ltp(
        self,
        exchange,
        tradingsymbol,
        symboltoken
    ):

        login_result = self.login()

        if not login_result.get("success"):

            return {
                "success": False,
                "message": login_result.get(
                    "message",
                    "Angel One login failed."
                )
            }

        try:

            response = self.smart_api.getMarketData(
                "FULL",
                {
                    exchange: [str(symboltoken)]
                }
            )

            if not response:

                return {
                    "success": False,
                    "message": (
                        "Empty response from Angel One."
                    )
                }

            if not response.get("status"):

                return {
                    "success": False,
                    "message": response.get(
                        "message",
                        "Unable to fetch LTP."
                    ),
                    "data": response
                }

            data = response.get(
                "data",
                {}
            )

            # Angel One market-data response normally
            # contains fetched data under fetchedData.
            fetched_data = data.get(
            "fetched",
            []
    )

            if not fetched_data:

                return {
                    "success": False,
                    "message": (
                        "No LTP data returned by Angel One."
                    ),
                    "data": response
                }

            # Get first instrument result
            quote = fetched_data[0]

            return {
                "success": True,
                "exchange": exchange,
                "tradingsymbol": tradingsymbol,
                "symboltoken": str(symboltoken),
                "ltp": quote.get(
                    "ltp",
                    0
                ),
                "data": quote
            }

        except Exception as error:

            return {
                "success": False,
                "message": str(error)
            }

    # ==========================================================
    # HISTORICAL DATA
    # ==========================================================

    def get_historical_data(
        self,
        symbol,
        token,
        days=200,
        interval="ONE_DAY",
        exchange="NSE"
    ):

        login_result = self.login()

        if not login_result.get("success"):

            return {
                "success": False,
                "message": login_result.get(
                    "message",
                    "Angel One login failed."
                ),
                "data": []
            }

        try:

            days = min(
                int(days),
                2000
            )

            to_date = datetime.now()

            from_date = (
                to_date -
                timedelta(days=days)
            )

            params = {

                "exchange": exchange,

                "symboltoken": str(
                    token
                ),

                "interval": interval,

                "fromdate": from_date.strftime(
                    "%Y-%m-%d %H:%M"
                ),

                "todate": to_date.strftime(
                    "%Y-%m-%d %H:%M"
                )
            }

            response = self.smart_api.getCandleData(
                params
            )

            if not response:

                return {
                    "success": False,
                    "message": (
                        "Empty response from Angel One."
                    ),
                    "data": []
                }

            if not response.get("status"):

                return {
                    "success": False,
                    "message": response.get(
                        "message",
                        "Historical data request failed."
                    ),
                    "data": []
                }

            candles = response.get(
                "data",
                []
            )

            if not candles:

                return {
                    "success": False,
                    "message": (
                        "No historical candles found."
                    ),
                    "data": []
                }

            return {

                "success": True,

                "symbol": symbol,

                "token": str(
                    token
                ),

                "interval": interval,

                "count": len(
                    candles
                ),

                "data": candles
            }

        except Exception as error:

            return {

                "success": False,

                "message": str(
                    error
                ),

                "data": []
            }

    # ==========================================================
    # HISTORICAL DATAFRAME
    # ==========================================================

    def get_historical_dataframe(
        self,
        symbol,
        token,
        days=200,
        interval="ONE_DAY",
        exchange="NSE"
    ):

        result = self.get_historical_data(
            symbol=symbol,
            token=token,
            days=days,
            interval=interval,
            exchange=exchange
        )

        if not result.get("success"):

            return None

        candles = result.get(
            "data",
            []
        )

        if not candles:

            return None

        try:

            df = pd.DataFrame(
                candles,
                columns=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume"
                ]
            )

            df["Datetime"] = pd.to_datetime(
                df["Datetime"]
            )

            numeric_columns = [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume"
            ]

            for column in numeric_columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce"
                )

            df = df.dropna(
                subset=[
                    "Open",
                    "High",
                    "Low",
                    "Close"
                ]
            )

            df = df.set_index(
                "Datetime"
            )

            df = df.sort_index()

            return df

        except Exception as error:

            print(
                "Historical dataframe error:",
                error
            )

            return None
