import json
import os
import requests
from datetime import datetime


# ============================================================
# ANGEL ONE INSTRUMENT MASTER
# ============================================================

INSTRUMENT_URL = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)

CACHE_FILE = "angel_instruments.json"


class AngelInstrumentManager:

    def __init__(self):

        self.instruments = []

    # ==========================================================
    # DOWNLOAD MASTER
    # ==========================================================

    def download_master(self):

        try:

            print(
                "Downloading Angel One instrument master..."
            )

            response = requests.get(
                INSTRUMENT_URL,
                timeout=(10, 90)
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list):

                raise ValueError(
                    "Invalid Angel One instrument data."
                )

            # --------------------------------------------------
            # SAVE CACHE
            # --------------------------------------------------

            with open(
                CACHE_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    data,
                    file
                )

            self.instruments = data

            print(
                "Angel One instruments downloaded:",
                len(data)
            )

            return {

                "success": True,

                "count": len(data),

                "message": (
                    "Instrument master downloaded."
                )
            }

        except requests.exceptions.Timeout:

            print(
                "Instrument download timed out."
            )

            return {

                "success": False,

                "count": 0,

                "message": (
                    "Angel One instrument master "
                    "download timed out."
                )
            }

        except requests.exceptions.RequestException as error:

            print(
                "Instrument download request error:",
                error
            )

            return {

                "success": False,

                "count": 0,

                "message": (
                    "Unable to download Angel One "
                    f"instrument master: {error}"
                )
            }

        except Exception as error:

            print(
                "Instrument download error:",
                error
            )

            return {

                "success": False,

                "count": 0,

                "message": str(error)
            }

    # ==========================================================
    # LOAD CACHE
    # ==========================================================

    def load_cache(self):

        # ------------------------------------------------------
        # ALREADY LOADED IN MEMORY
        # ------------------------------------------------------

        if self.instruments:

            return {

                "success": True,

                "count": len(
                    self.instruments
                ),

                "message": (
                    "Instrument cache already loaded."
                )
            }

        # ------------------------------------------------------
        # CHECK LOCAL CACHE FILE
        # ------------------------------------------------------

        if os.path.exists(CACHE_FILE):

            try:

                with open(
                    CACHE_FILE,
                    "r",
                    encoding="utf-8"
                ) as file:

                    data = json.load(file)

                if not isinstance(data, list):

                    raise ValueError(
                        "Instrument cache is not a list."
                    )

                if not data:

                    raise ValueError(
                        "Instrument cache is empty."
                    )

                self.instruments = data

                print(
                    "Angel One instrument cache loaded:",
                    len(data)
                )

                return {

                    "success": True,

                    "count": len(data),

                    "message": (
                        "Instrument cache loaded."
                    )
                }

            except Exception as error:

                print(
                    "Instrument cache read error:",
                    error
                )

        # ------------------------------------------------------
        # CACHE DOES NOT EXIST / INVALID
        # ------------------------------------------------------

        print(
            "Instrument cache unavailable."
        )

        return self.download_master()

    # ==========================================================
    # REFRESH
    # ==========================================================

    def refresh(self):

        print(
            "Refreshing Angel One instrument master..."
        )

        return self.download_master()

    # ==========================================================
    # NSE EQUITY STOCKS
    # ==========================================================

    def get_nse_equities(self):

        if not self.instruments:

            result = self.load_cache()

            if not result.get("success"):

                return []

        stocks = []

        for item in self.instruments:

            if not isinstance(item, dict):
                continue

            # --------------------------------------------------
            # NSE ONLY
            # --------------------------------------------------

            if item.get("exch_seg") != "NSE":
                continue

            symbol = str(
                item.get(
                    "symbol",
                    ""
                )
            ).strip()

            token = str(
                item.get(
                    "token",
                    ""
                )
            ).strip()

            name = str(
                item.get(
                    "name",
                    ""
                )
            ).strip()

            instrument_type = str(
                item.get(
                    "instrumenttype",
                    ""
                )
            ).strip()

            # --------------------------------------------------
            # NORMAL NSE EQUITY ONLY
            # --------------------------------------------------

            if not symbol.endswith("-EQ"):
                continue

            if not token:
                continue

            stocks.append({

                "symbol": symbol,

                "token": token,

                "name": name,

                "exchange": "NSE",

                "instrumenttype": instrument_type
            })

        return stocks

    # ==========================================================
    # FIND STOCK
    # ==========================================================

    def find_stock(self, symbol):

        if not self.instruments:

            result = self.load_cache()

            if not result.get("success"):

                return None

        symbol = str(
            symbol
        ).upper().strip()

        for item in self.instruments:

            if not isinstance(item, dict):
                continue

            item_symbol = str(
                item.get(
                    "symbol",
                    ""
                )
            ).upper().strip()

            if (
                item.get("exch_seg") == "NSE"
                and item_symbol == symbol
            ):

                return item

        return None

    # ==========================================================
    # GET TOKEN
    # ==========================================================

    def get_token(self, symbol):

        stock = self.find_stock(
            symbol
        )

        if not stock:
            return None

        return str(
            stock.get(
                "token"
            )
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def summary(self):

        stocks = self.get_nse_equities()

        return {

            "success": True,

            "count": len(
                stocks
            ),

            "updated": datetime.now().isoformat(),

            "stocks": stocks
        }
