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

    # =========================================================
    # LOGIN
    # =========================================================

    def login(self):

        if self.logged_in:
            return True

        if not all([
            self.api_key,
            self.client_code,
            self.password,
            self.totp
        ]):
            raise ValueError(
                "Angel One credentials are not configured."
            )

        self.smart_api = SmartConnect(
            api_key=self.api_key
        )

        session = self.smart_api.generateSession(
            self.client_code,
            self.password,
            self.totp
        )

        if not session:
            raise Exception(
                "Angel One login returned no response."
            )

        if not session.get("status"):
            raise Exception(
                session.get(
                    "message",
                    "Angel One login failed."
                )
            )

        self.logged_in = True

        return True

    # =========================================================
    # HISTORICAL DATA
    # =========================================================

    def get_historical_data(
        self,
        symbol_token,
        exchange="NSE",
        interval="ONE_DAY",
        days=365
    ):

        self.login()

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        params = {
            "exchange": exchange,
            "symboltoken": str(symbol_token),
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
            raise Exception(
                "Angel One returned an empty response."
            )

        if not response.get("status"):
            raise Exception(
                response.get(
                    "message",
                    "Historical data request failed."
                )
            )

        candles = response.get("data")

        if not candles:
            raise Exception(
                "No historical candles returned."
            )

        # Angel One candle format:
        #
        # datetime
        # open
        # high
        # low
        # close
        # volume

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

        df = df.set_index("Datetime")

        df = df.sort_index()

        return df
