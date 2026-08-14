import os

from SmartApi import SmartConnect


class AngelOneService:

    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_code = os.getenv("ANGEL_CLIENT_CODE")
        self.password = os.getenv("ANGEL_PASSWORD")

        self.smart_api = None

    def connect(self):

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

        try:

            self.smart_api = SmartConnect(
                api_key=self.api_key
            )

            return {
                "success": True,
                "message": "Angel One SmartAPI client created."
            }

        except Exception as error:

            return {
                "success": False,
                "message": str(error)
            }
