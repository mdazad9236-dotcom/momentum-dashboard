import os
from SmartApi import SmartConnect


class AngelMarketData:

    def __init__(self, smart_api=None):

        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_code = os.getenv("ANGEL_CLIENT_CODE")
        self.password = os.getenv("ANGEL_PASSWORD")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        self.smart_api = smart_api

    # =========================================================
    # SET SMART API CLIENT
    # =========================================================

    def set_client(self, smart_api):

        self.smart_api = smart_api

    # =========================================================
    # GET LTP
    # =========================================================

    def get_ltp(
        self,
        exchange,
        tradingsymbol,
        symboltoken
    ):

        if self.smart_api is None:

            return {
                "success": False,
                "message": "Angel One session is not connected."
            }

        try:

            response = self.smart_api.ltpData(
                exchange,
                tradingsymbol,
                symboltoken
            )

            if not response:

                return {
                    "success": False,
                    "message": "Empty response from Angel One."
                }

            if not response.get("status"):

                return {
                    "success": False,
                    "message": response.get(
                        "message",
                        "Unable to fetch LTP."
                    )
                }

            data = response.get("data", {})

            return {
                "success": True,
                "exchange": exchange,
                "symbol": tradingsymbol,
                "token": symboltoken,
                "ltp": data.get("ltp"),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "close": data.get("close")
            }

        except Exception as error:

            return {
                "success": False,
                "message": str(error)
            }
