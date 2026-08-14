import os

import pyotp
from SmartApi import SmartConnect


class AngelOneService:

    def __init__(self):

        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_code = os.getenv("ANGEL_CLIENT_CODE")
        self.password = os.getenv("ANGEL_PASSWORD")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        self.smart_api = None

    # =========================================================
    # LOGIN
    # =========================================================

    def login(self):

        if not self.api_key:
            return {
                "success": False,
                "message": "ANGEL_API_KEY is missing."
            }

        if not self.client_code:
            return {
                "success": False,
                "message": "ANGEL_CLIENT_CODE is missing."
            }

        if not self.password:
            return {
                "success": False,
                "message": "ANGEL_PASSWORD is missing."
            }

        if not self.totp_secret:
            return {
                "success": False,
                "message": "ANGEL_TOTP_SECRET is missing."
            }

        try:

            self.smart_api = SmartConnect(
                api_key=self.api_key
            )

            # Generate the current 6-digit TOTP
            current_totp = pyotp.TOTP(
                self.totp_secret
            ).now()

            session = self.smart_api.generateSession(
                self.client_code,
                self.password,
                current_totp
            )

            if not session:

                return {
                    "success": False,
                    "message": "Empty response from Angel One."
                }

            if not session.get("status"):

                return {
                    "success": False,
                    "message": session.get(
                        "message",
                        "Angel One login failed."
                    )
                }

            return {
                "success": True,
                "message": "Angel One authentication successful.",
                "data": {
                    "client_code": self.client_code
                }
            }

        except Exception as error:

            return {
                "success": False,
                "message": str(error)
            }
    def get_market_data_service(self):
        from angel_market import AngelMarketData

        if self.smart_api is None:
            login_result = self.login()

            if not login_result.get("success"):
                return {
                    "success": False,
                    "message": login_result.get(
                        "message",
                        "Angel One login failed."
                    )
                }

        market = AngelMarketData(self.smart_api)

        return {
            "success": True,
            "service": market
        }
