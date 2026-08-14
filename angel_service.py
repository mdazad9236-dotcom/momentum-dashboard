import os
from datetime import datetime, timedelta

import pandas as pd
from SmartApi import SmartConnect


class AngelOneService:

    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_code = os.getenv("ANGEL_CLIENT_CODE")
        self.password = os.getenv("ANGEL_PASSWORD")
        self.totp = os.getenv("ANGEL_TOTP")

        self.smart_api = None
        self.logged_in = False

    # ==========================================================
    # LOGIN
    # ==========================================================

    def login(self):

        if self.logged_in and self.smart_api:
            return True

        if not all([
            self.api_key,
            self.client_code,
            self.password,
            self.totp
        ]):
            print("Angel One credentials are missing.")
            return False

        try:

            self.smart_api = SmartConnect(
                api_key=self.api_key
            )

            login_response = self.smart_api.generateSession(
                self.client_code,
                self.password,
                self.totp
            )

            if not login_response:
                print("Angel One login failed.")
                return False

            if not login_response.get("status"):
                print(
                    "Angel One login failed:",
                    login_response.get("message")
                )
                return False

            self.logged_in = True

            print("Angel One login successful.")

            return True

        except Exception as error:

            print(
                "Angel One login error:",
                error
            )

            self.smart_api = None
            self.logged_in = False

            return False

    # ==========================================================
    # LIVE QUOTE
    # ==========================================================

    def get_quote(
        self,
        symbol,
        token,
        exchange="NSE"
    ):

        if not self.login():
            return {
                "success": False,
                "message": "Angel One login failed."
            }

        try:

            response = self.smart_api.getMarketData(
                "FULL",
                {
                    exchange: [str(token)]
                }
            )

            return response

        except Exception as error:

            return {
                "success": False,
                "message": str(error)
            }

    # ==========================================================
    # HISTORICAL CANDLES
    # ==========================================================

    def get_historical_data(
        self,
        symbol,
        token,
        days=200,
        interval="ONE_DAY",
        exchange="NSE"
    ):

        if not self.login():

            return {
                "success": False,
                "message": "Angel One login failed.",
                "data": []
            }

        try:

            # Angel One allows up to 2000 days
            # for ONE_DAY candles.
            days = min(int(days), 2000)

            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)

            params = {
                "exchange": exchange,
                "symboltoken": str(token),
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
                    "message": "Empty response from Angel One.",
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
                    "message": "No historical candles found.",
                    "data": []
                }

            return {
                "success": True,
                "symbol": symbol,
                "token": str(token),
                "interval": interval,
                "count": len(candles),
                "data": candles
            }

        except Exception as error:

            return {
                "success": False,
                "message": str(error),
                "data": []
            }

    # ==========================================================
    # HISTORICAL DATA AS DATAFRAME
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
