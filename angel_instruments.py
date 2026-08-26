import json
import os
import time
import requests
from datetime import datetime

INSTRUMENT_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
CACHE_FILE = "angel_instruments.json"
TEMP_CACHE_FILE = "angel_instruments.json.tmp"
DOWNLOAD_ATTEMPTS = 3
CHUNK_SIZE = 1024 * 1024
FAILURE_COOLDOWN_SECONDS = 600


class AngelInstrumentManager:
    """Load Angel's large instrument master once and fail fast when the source is unavailable."""

    _shared_instruments = None
    _shared_stock_cache = None
    _shared_failure_until = 0.0
    _shared_failure_message = None

    def __init__(self):
        self.instruments = self.__class__._shared_instruments or []
        self._stock_cache = self.__class__._shared_stock_cache

    def _sync_shared(self):
        self.__class__._shared_instruments = self.instruments or None
        self.__class__._shared_stock_cache = self._stock_cache

    def _save_cache_atomically(self, data):
        with open(TEMP_CACHE_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, separators=(",", ":"))
            file.flush()
            os.fsync(file.fileno())
        os.replace(TEMP_CACHE_FILE, CACHE_FILE)

    def _download_once(self):
        """Download a fresh master; never resume a known-invalid partial JSON file."""
        try:
            if os.path.exists(TEMP_CACHE_FILE):
                os.remove(TEMP_CACHE_FILE)
        except OSError:
            pass

        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        response = requests.get(
            INSTRUMENT_URL,
            stream=True,
            timeout=(20, 180),
            headers=headers,
        )
        response.raise_for_status()
        try:
            with open(TEMP_CACHE_FILE, "wb") as file:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        file.write(chunk)
                file.flush()
                os.fsync(file.fileno())
        finally:
            response.close()

        with open(TEMP_CACHE_FILE, "rb") as file:
            payload = file.read()
        if not payload:
            raise ValueError("Angel One instrument master download was empty.")
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, list) or not data:
            raise ValueError("Invalid or empty Angel One instrument data.")
        return data

    def download_master(self):
        now = time.time()
        if now < self.__class__._shared_failure_until:
            return {
                "success": False,
                "count": 0,
                "message": self.__class__._shared_failure_message or "Instrument master temporarily unavailable; using fallback.",
            }

        last_error = None
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                data = self._download_once()
                self._save_cache_atomically(data)
                self.instruments = data
                self._stock_cache = None
                self._sync_shared()
                self.__class__._shared_failure_until = 0.0
                self.__class__._shared_failure_message = None
                message = "Instrument master downloaded."
                if attempt > 1:
                    message = f"Instrument master downloaded on retry {attempt}."
                print(f"{message} Records: {len(data)}")
                return {"success": True, "count": len(data), "message": message}
            except (requests.exceptions.RequestException, json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError) as error:
                last_error = error
                partial_size = os.path.getsize(TEMP_CACHE_FILE) if os.path.exists(TEMP_CACHE_FILE) else 0
                print(
                    f"Angel instrument master download attempt {attempt}/{DOWNLOAD_ATTEMPTS} "
                    f"failed after {partial_size} bytes: {error}"
                )
                try:
                    os.remove(TEMP_CACHE_FILE)
                except OSError:
                    pass
                if attempt < DOWNLOAD_ATTEMPTS:
                    time.sleep(min(2 ** (attempt - 1), 5))

        message = f"Unable to download Angel One instrument master after {DOWNLOAD_ATTEMPTS} attempts: {last_error}"
        self.__class__._shared_failure_until = time.time() + FAILURE_COOLDOWN_SECONDS
        self.__class__._shared_failure_message = message
        print(f"[INSTRUMENT] Cooling down master download for {FAILURE_COOLDOWN_SECONDS}s; fallback remains available.")
        return {"success": False, "count": 0, "message": message}

    def load_cache(self):
        if self.instruments:
            return {"success": True, "count": len(self.instruments), "message": "Instrument cache already loaded."}
        if self.__class__._shared_instruments:
            self.instruments = self.__class__._shared_instruments
            self._stock_cache = self.__class__._shared_stock_cache
            return {"success": True, "count": len(self.instruments), "message": "Shared instrument cache loaded."}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as file:
                    data = json.load(file)
                if not isinstance(data, list) or not data:
                    raise ValueError("Instrument cache is empty or invalid.")
                self.instruments = data
                self._stock_cache = None
                self._sync_shared()
                return {"success": True, "count": len(data), "message": "Instrument cache loaded."}
            except (json.JSONDecodeError, OSError, ValueError) as error:
                print("Instrument cache read error; rebuilding cache:", error)
                try:
                    os.remove(CACHE_FILE)
                except OSError:
                    pass
        return self.download_master()

    def refresh(self):
        self.instruments = []
        self._stock_cache = None
        self.__class__._shared_instruments = None
        self.__class__._shared_stock_cache = None
        self.__class__._shared_failure_until = 0.0
        self.__class__._shared_failure_message = None
        for path in (CACHE_FILE, TEMP_CACHE_FILE):
            try:
                os.remove(path)
            except OSError:
                pass
        return self.download_master()

    def get_nse_equities(self):
        if self._stock_cache is not None:
            return self._stock_cache
        if not self.instruments and not self.load_cache().get("success"):
            return []
        stocks = []
        seen = set()
        for item in self.instruments:
            if not isinstance(item, dict) or item.get("exch_seg") != "NSE":
                continue
            symbol = str(item.get("symbol", "")).strip().upper()
            token = str(item.get("token", "")).strip()
            if not symbol.endswith("-EQ") or not token or symbol in seen:
                continue
            seen.add(symbol)
            stocks.append({
                "symbol": symbol,
                "token": token,
                "name": str(item.get("name", "")).strip(),
                "exchange": "NSE",
                "instrumenttype": str(item.get("instrumenttype", "")).strip(),
            })
        self._stock_cache = stocks
        self._sync_shared()
        return stocks

    def find_stock(self, symbol):
        requested = str(symbol).upper().strip()
        requested = requested.replace(".NS", "")
        if not self.instruments and not self.load_cache().get("success"):
            return None
        aliases = {
            "NIFTY 50": "NIFTY", "NIFTY50": "NIFTY", "NIFTY BANK": "BANKNIFTY",
            "BANK NIFTY": "BANKNIFTY", "BANKNIFTY 50": "BANKNIFTY",
            "NIFTY FIN SERVICE": "FINNIFTY", "NIFTY FIN SERV": "FINNIFTY",
            "NIFTY FINANCIAL SERVICES": "FINNIFTY", "NIFTY MIDCAP SELECT": "MIDCPNIFTY",
        }
        candidates = [requested, aliases.get(requested, requested)]
        if requested.endswith("-EQ"):
            candidates.append(requested[:-3])
        elif requested.endswith("EQ"):
            candidates.append(requested[:-2] + "-EQ")
            candidates.append(requested[:-2])
        for item in self.instruments:
            if not isinstance(item, dict) or str(item.get("exch_seg", "")).upper() != "NSE":
                continue
            raw_symbol = str(item.get("symbol", "")).strip().upper()
            raw_name = str(item.get("name", "")).strip().upper()
            token = str(item.get("token", "")).strip()
            if token and (raw_symbol in candidates or raw_name in candidates):
                return {"symbol": raw_symbol, "token": token, "name": str(item.get("name", "")).strip(), "exchange": "NSE", "instrumenttype": str(item.get("instrumenttype", "")).strip()}
        equity_symbol = requested if requested.endswith("-EQ") else requested + "-EQ"
        for stock in self.get_nse_equities():
            if stock["symbol"] == equity_symbol:
                return stock
        return None

    def get_token(self, symbol):
        stock = self.find_stock(symbol)
        return str(stock["token"]) if stock else None

    def summary(self):
        stocks = self.get_nse_equities()
        return {"success": True, "count": len(stocks), "updated": datetime.now().isoformat(), "stocks": stocks}
