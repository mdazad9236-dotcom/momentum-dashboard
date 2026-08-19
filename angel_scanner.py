import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from x10_engine import X10Engine
from angel_service import AngelOneService
from angel_instruments import AngelInstrumentManager
from analysis import TechnicalAnalyzer
from market_indices import INDEX_DEFINITIONS, build_index_snapshot


class AngelScanner:
    """Angel One market scanner with controlled parallel analysis."""

    def __init__(self, batch_size=3, delay=0.1, max_workers=3):
        self.service = AngelOneService()
        self.instrument_manager = AngelInstrumentManager()
        self.x10_engine = X10Engine()
        self.batch_size = max(1, int(batch_size))
        self.delay = max(0.0, float(delay))
        self.max_workers = max(1, int(max_workers))

    def analyze_stock(self, stock):
        symbol = stock.get("symbol")
        token = stock.get("token")
        name = stock.get("name", symbol)
        if not symbol or not token:
            return None
        started = time.time()
        try:
            dataframe = self.service.get_historical_dataframe(
                symbol=symbol, token=token, days=100,
                interval="ONE_DAY", exchange="NSE"
            )
            if dataframe is None or dataframe.empty:
                return None
            analysis = TechnicalAnalyzer(dataframe).calculate()
            if not analysis:
                return None
            x10 = self.x10_engine.analyze(analysis)
            if not x10:
                return None
            return {
                "symbol": symbol, "token": str(token), "name": name,
                "price": analysis.get("price", 0),
                "technical_score": analysis.get("technical_score", 0),
                "x10_score": x10.get("x10_score", 0),
                "success_probability": x10.get("x10_score", 0),
                "signal": x10.get("signal", "AVOID"),
                "entry": x10.get("entry", 0),
                "entry_low": x10.get("entry_low", 0),
                "entry_high": x10.get("entry_high", 0),
                "stop_loss": x10.get("stop_loss", 0),
                "target": x10.get("target", 0),
                "target_1": x10.get("target_1", 0),
                "target_2": x10.get("target_2", 0),
                "risk": x10.get("risk", 0),
                "reward": x10.get("reward", 0),
                "risk_reward": x10.get("risk_reward", 0),
                "trailing_stop": x10.get("trailing_stop", 0),
                "chase_price": x10.get("chase_price", 0),
                "dont_chase": x10.get("dont_chase", False),
                "setup_quality": x10.get("setup_quality", "WEAK"),
                "trend": analysis.get("trend", "Neutral"),
                "momentum": analysis.get("momentum", "Neutral"),
                "rsi": analysis.get("rsi", 0),
                "ema20": analysis.get("ema20", 0),
                "ema50": analysis.get("ema50", 0),
                "ema200": analysis.get("ema200", 0),
                "macd": analysis.get("macd", 0),
                "macd_signal": analysis.get("macd_signal", 0),
                "macd_histogram": analysis.get("macd_histogram", 0),
                "adx": analysis.get("adx", 0),
                "plus_di": analysis.get("plus_di", 0),
                "minus_di": analysis.get("minus_di", 0),
                "support": analysis.get("support", 0),
                "resistance": analysis.get("resistance", 0),
                "volume_ratio": analysis.get("volume_ratio", 0),
                "atr": analysis.get("atr", 0),
                "52_week_high": analysis.get("52_week_high", 0),
                "52_week_low": analysis.get("52_week_low", 0),
                "scan_time": round(time.time() - started, 2),
            }
        except Exception as error:
            print(f"[STOCK] {symbol} ERROR: {error}")
            return None

    def _analyze_batch(self, stocks):
        results = []
        workers = min(self.max_workers, len(stocks))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self.analyze_stock, stock) for stock in stocks]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as error:
                    print(f"[BATCH] ERROR: {error}")
        return results

    def _get_index_snapshots(self):
        snapshots = []
        for name, definition in INDEX_DEFINITIONS.items():
            try:
                quote = self.service.get_quote(
                    symbol=definition["tradingsymbol"],
                    token=definition["token"],
                    exchange=definition["exchange"],
                )
                data = (quote.get("data") or {}).get("fetched") or []
                q = data[0] if data else {}
                price = float(q.get("ltp", 0) or 0)
                close = float(q.get("close", 0) or 0)
                high = float(q.get("high", 0) or 0)
                low = float(q.get("low", 0) or 0)
                change = price - close if close else 0
                change_pct = (change / close * 100) if close else 0

                history = self.service.get_historical_data(
                    symbol=name, token=definition["token"], days=30,
                    interval="ONE_DAY", exchange=definition["exchange"]
                )
                candles = history.get("data", []) if history.get("success") else []
                lows = [float(c[3]) for c in candles[-20:] if len(c) >= 5]
                highs = [float(c[2]) for c in candles[-20:] if len(c) >= 5]
                support = min(lows) if lows else low
                resistance = max(highs) if highs else high
                if price > 0 and support <= 0:
                    support = price * 0.99
                if price > 0 and resistance <= price:
                    resistance = max(high or price, price * 1.01)
                snapshot = build_index_snapshot(
                    name, price, support, resistance, change, change_pct
                )
            except Exception as error:
                print(f"[INDEX] {name} ERROR: {error}")
                snapshot = build_index_snapshot(name, 0, 0, 0, 0, 0)
            snapshots.append(snapshot)
        return snapshots

    @staticmethod
    def _index_rows(snapshots):
        """Represent indices as scanner-safe rows for the existing /api/scan response."""
        rows = []
        for snapshot in snapshots:
            rows.append({
                "symbol": "__INDEX__" + snapshot["name"],
                "name": json.dumps(snapshot, separators=(",", ":")),
                "price": snapshot["price"],
                "support": snapshot["support"],
                "resistance": snapshot["resistance"],
                "change": snapshot["change"],
                "change_percent": snapshot["change_percent"],
                "trend": snapshot["bias"],
                "momentum": snapshot["bias"],
                "x10_score": 0,
                "signal": snapshot["bias"],
                "technical_score": 0,
                "risk_reward": 0,
                "volume_ratio": 0,
                "is_index": True,
            })
        return rows

    def scan_market(self, limit=50):
        start = time.time()
        try:
            login = self.service.login()
            if not login.get("success"):
                return {"success": False, "message": login.get("message", "Angel One login failed."), "stocks": []}
            cache = self.instrument_manager.load_cache()
            if not cache.get("success"):
                return {"success": False, "message": "Unable to load Angel One instruments.", "stocks": []}

            stocks = self.instrument_manager.get_nse_equities() or []
            stocks = stocks[:max(1, int(limit))]
            results = []
            for start_index in range(0, len(stocks), self.batch_size):
                batch = stocks[start_index:start_index + self.batch_size]
                results.extend(self._analyze_batch(batch))

            results.sort(key=lambda item: item.get("x10_score", 0), reverse=True)
            top_stocks = results[:20]
            indices = self._get_index_snapshots()
            elapsed = round(time.time() - start, 2)
            return {
                "success": True,
                "count": len(top_stocks),
                "scanned": len(stocks),
                "successful": len(results),
                "time_seconds": elapsed,
                "stocks": top_stocks + self._index_rows(indices),
                "indices": indices,
            }
        except Exception as error:
            print(f"MARKET SCANNER ERROR: {error}")
            return {"success": False, "message": str(error), "stocks": []}
