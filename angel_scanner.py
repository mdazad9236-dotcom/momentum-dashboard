import time
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

from x10_engine import X10Engine
from angel_service import AngelOneService
from angel_instruments import AngelInstrumentManager
from analysis import TechnicalAnalyzer
from market_indices import INDEX_DEFINITIONS, build_index_snapshot


# Small emergency universe used only when the Angel One instrument/quote pipeline
# is unavailable. It prevents the dashboard from becoming completely empty while
# broker connectivity recovers. Technical/X10 validation is still applied.
FALLBACK_STOCKS = [
    "IDEA", "SUZLON", "YESBANK", "NHPC", "IREDA", "IRFC", "RVNL", "SJVN",
    "IDFCFIRSTB", "IOC", "PNB", "CANBK", "BANKBARODA", "UCOBANK", "TRIDENT",
    "HFCL", "NBCC", "BEL", "BHEL", "GAIL", "SAIL", "JINDALSTEL", "IEX",
    "INOXWIND", "TATASTEEL", "POWERGRID", "NTPC", "ONGC", "COALINDIA",
]

FALLBACK_INDICES = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "INDIA VIX": "^INDIAVIX",
}


class AngelScanner:
    """Memory-conscious X10 scanner: broker data first, safe market-data fallback second."""

    def __init__(self, batch_size=5, delay=0.05, max_workers=2):
        self.service = AngelOneService()
        self.instrument_manager = AngelInstrumentManager()
        self.x10_engine = X10Engine()
        self.batch_size = max(1, int(batch_size))
        self.delay = max(0.0, float(delay))
        self.max_workers = max(1, int(max_workers))

    def analyze_stock(self, stock):
        symbol, token, name = stock.get("symbol"), stock.get("token"), stock.get("name", stock.get("symbol"))
        if not symbol or not token:
            return None
        started = time.time()
        dataframe = None
        analysis = None
        x10 = None
        try:
            dataframe = self.service.get_historical_dataframe(symbol, token, days=100, interval="ONE_DAY", exchange="NSE")
            if dataframe is None or dataframe.empty:
                return None
            analysis = TechnicalAnalyzer(dataframe).calculate()
            if not analysis:
                return None
            x10 = self.x10_engine.analyze({**analysis, "price": analysis.get("price", 0)})
            if not x10:
                return None
            return self._format_result(symbol, token, name, analysis, x10, started, "ANGEL ONE")
        except Exception as error:
            print(f"[STOCK] {symbol} ERROR: {error}")
            return None
        finally:
            dataframe = None
            analysis = None
            x10 = None

    def _format_result(self, symbol, token, name, analysis, x10, started, source):
        return {
            "symbol": symbol, "token": str(token or ""), "name": name, "price": analysis.get("price", 0),
            "technical_score": analysis.get("technical_score", 0), "x10_score": x10.get("x10_score", 0),
            "success_probability": x10.get("x10_score", 0), "signal": x10.get("signal", "AVOID"),
            "entry": x10.get("entry", 0), "entry_low": x10.get("entry_low", 0), "entry_high": x10.get("entry_high", 0),
            "stop_loss": x10.get("stop_loss", 0), "target": x10.get("target", 0),
            "target_1": x10.get("target_1", 0), "target_2": x10.get("target_2", 0),
            "risk": x10.get("risk", 0), "reward": x10.get("reward", 0),
            "risk_reward": x10.get("risk_reward", "1:0"), "risk_reward_value": x10.get("risk_reward_value", 0),
            "trailing_stop": x10.get("trailing_stop", 0), "chase_price": x10.get("chase_price", 0),
            "dont_chase": x10.get("dont_chase", False), "setup_quality": x10.get("setup_quality", "WEAK"),
            "trend": analysis.get("trend", "Neutral"), "momentum": analysis.get("momentum", "Neutral"),
            "rsi": analysis.get("rsi", 0), "ema20": analysis.get("ema20", 0), "ema50": analysis.get("ema50", 0),
            "ema200": analysis.get("ema200", 0), "macd": analysis.get("macd", 0), "macd_signal": analysis.get("macd_signal", 0),
            "macd_histogram": analysis.get("macd_histogram", 0), "adx": analysis.get("adx", 0),
            "plus_di": analysis.get("plus_di", 0), "minus_di": analysis.get("minus_di", 0),
            "support": analysis.get("support", 0), "resistance": analysis.get("resistance", 0),
            "volume_ratio": analysis.get("volume_ratio", 0), "atr": analysis.get("atr", 0),
            "52_week_high": analysis.get("52_week_high", 0), "52_week_low": analysis.get("52_week_low", 0),
            "scan_time": round(time.time() - started, 2), "data_source": source,
        }

    def _analyze_batch(self, stocks):
        if not stocks:
            return []
        results = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(stocks))) as executor:
            futures = [executor.submit(self.analyze_stock, stock) for stock in stocks]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as error:
                    print(f"[BATCH] ERROR: {error}")
        gc.collect()
        return results

    def _fallback_yfinance_scan(self, limit=6):
        """Return validated X10 candidates when the Angel instrument master is unavailable."""
        results = []
        for symbol in FALLBACK_STOCKS:
            try:
                history = yf.Ticker(f"{symbol}.NS").history(period="6mo", interval="1d", auto_adjust=False)
                if history is None or history.empty:
                    continue
                analysis = TechnicalAnalyzer(history).calculate()
                if not analysis:
                    continue
                x10 = self.x10_engine.analyze({**analysis, "price": analysis.get("price", 0)})
                if x10:
                    results.append(self._format_result(symbol, "", symbol, analysis, x10, time.time(), "YAHOO FALLBACK"))
            except Exception as error:
                print(f"[FALLBACK] {symbol} ERROR: {error}")
        results.sort(key=lambda x: (x.get("x10_score", 0), x.get("risk_reward_value", 0)), reverse=True)
        return results[:max(1, int(limit))]

    def _get_index_snapshots(self):
        definitions = [{"name": name, **definition} for name, definition in INDEX_DEFINITIONS.items()]
        quote_result = self.service.get_quotes(definitions)
        quotes = {(str(q.get("exchange")), str(q.get("token", q.get("symbolToken", "")))): q for q in quote_result.get("quotes", [])} if quote_result.get("success") else {}
        snapshots = []
        for item in definitions:
            key = (item["exchange"], str(item["token"]))
            q = quotes.get(key, {})
            price = float(q.get("ltp", 0) or 0)
            close = float(q.get("close", 0) or 0)
            change = price - close if close else 0
            change_pct = change / close * 100 if close else 0
            high = float(q.get("high", 0) or 0)
            low = float(q.get("low", 0) or 0)
            support, resistance = low, high
            try:
                history = self.service.get_historical_data(item["name"], item["token"], days=45, interval="ONE_DAY", exchange=item["exchange"])
                candles = history.get("data", []) if history.get("success") else []
                recent = [c for c in candles[-20:] if isinstance(c, (list, tuple)) and len(c) >= 5]
                lows = [float(c[3]) for c in recent]
                highs = [float(c[2]) for c in recent]
                if price <= 0 and recent:
                    price = float(recent[-1][4])
                    if len(recent) >= 2:
                        close = float(recent[-2][4])
                    change = price - close if close else 0
                    change_pct = change / close * 100 if close else 0
                support = min(lows) if lows else support
                resistance = max(highs) if highs else resistance
            except Exception as error:
                print(f"[INDEX-HISTORY] {item['name']} ERROR: {error}")
            if price > 0 and support <= 0:
                support = price * 0.99
            if price > 0 and resistance <= price:
                resistance = max(price * 1.01, high)
            snapshots.append(build_index_snapshot(item["name"], price, support, resistance, change, change_pct))

        # If broker index calls produced no usable prices, keep the dashboard useful
        # with a current Yahoo Finance snapshot rather than showing an empty card.
        if not any(float(item.get("price", 0) or 0) > 0 for item in snapshots):
            fallback = []
            for name, ticker in FALLBACK_INDICES.items():
                try:
                    history = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=False)
                    if history is None or history.empty:
                        continue
                    closes = history["Close"].dropna()
                    highs = history["High"].dropna()
                    lows = history["Low"].dropna()
                    if closes.empty:
                        continue
                    price = float(closes.iloc[-1])
                    previous = float(closes.iloc[-2]) if len(closes) > 1 else price
                    change = price - previous
                    change_pct = change / previous * 100 if previous else 0
                    support = float(lows.tail(20).min()) if not lows.empty else price * 0.99
                    resistance = float(highs.tail(20).max()) if not highs.empty else price * 1.01
                    fallback.append(build_index_snapshot(name, price, support, resistance, change, change_pct))
                except Exception as error:
                    print(f"[INDEX-FALLBACK] {name} ERROR: {error}")
            if fallback:
                snapshots = fallback
        return snapshots

    def scan_market(self, limit=30, include_indices=True):
        start = time.time()
        requested_limit = max(1, int(limit))
        scan_limit = min(requested_limit, 6)

        login = self.service.login()
        if not login.get("success"):
            print("[X10] Angel login unavailable; using market-data fallback.")
            fallback_results = self._fallback_yfinance_scan(scan_limit)
            return {
                "success": True,
                "message": "Angel One unavailable; showing fallback market-data candidates.",
                "stocks": fallback_results,
                "top_opportunities": fallback_results[:5],
                "count": min(5, len(fallback_results)),
                "scanned": len(fallback_results),
                "successful": len(fallback_results),
                "manual_count": 0,
                "time_seconds": round(time.time() - start, 2),
                "indices": self._get_index_snapshots() if include_indices else [],
            }

        cache = self.instrument_manager.load_cache()
        if not cache.get("success"):
            print("[X10] Instrument master unavailable; using market-data fallback:", cache.get("message"))
            fallback_results = self._fallback_yfinance_scan(scan_limit)
            return {
                "success": True,
                "message": "Instrument master unavailable; showing fallback market-data candidates.",
                "stocks": fallback_results,
                "top_opportunities": fallback_results[:5],
                "count": min(5, len(fallback_results)),
                "scanned": len(fallback_results),
                "successful": len(fallback_results),
                "manual_count": 0,
                "time_seconds": round(time.time() - start, 2),
                "indices": self._get_index_snapshots() if include_indices else [],
            }

        universe = self.instrument_manager.get_nse_equities()
        quote_universe = universe[:200]
        quote_result = self.service.get_quotes(quote_universe)
        candidates = []
        if quote_result.get("success"):
            for q in quote_result.get("quotes", []):
                price = float(q.get("ltp", 0) or 0)
                if not (2 <= price <= 300):
                    continue
                volume = float(q.get("tradeVolume", 0) or 0)
                q["name"] = q.get("name") or q.get("symbol", "")
                q["symbol"] = q.get("symbol") or q.get("tradingsymbol", "")
                candidates.append((volume, q))
        if not candidates:
            print("[X10] Angel quote scan returned no candidates; using fallback market-data scan.")
            fallback_results = self._fallback_yfinance_scan(scan_limit)
            return {
                "success": True,
                "message": "Angel quote scan returned no candidates; showing fallback market-data candidates.",
                "stocks": fallback_results,
                "top_opportunities": fallback_results[:5],
                "count": min(5, len(fallback_results)),
                "scanned": len(fallback_results),
                "successful": len(fallback_results),
                "manual_count": 0,
                "time_seconds": round(time.time() - start, 2),
                "indices": self._get_index_snapshots() if include_indices else [],
            }

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        selected = [item for _, item in candidates[:scan_limit]]
        results = []
        for offset in range(0, len(selected), self.batch_size):
            results.extend(self._analyze_batch(selected[offset:offset + self.batch_size]))
            if self.delay:
                time.sleep(self.delay)
        results.sort(key=lambda item: (item.get("x10_score", 0), item.get("risk_reward_value", 0)), reverse=True)
        top_results = results[:5]

        analyzed_symbols = {str(item.get("symbol", "")).upper() for item in results}
        manual_stocks = []
        for _, q in candidates:
            symbol = str(q.get("symbol", "")).upper()
            if not symbol or symbol in analyzed_symbols:
                continue
            manual_stocks.append({
                "symbol": symbol,
                "token": str(q.get("token", q.get("symbolToken", ""))),
                "name": q.get("name") or symbol,
                "price": float(q.get("ltp", 0) or 0),
                "x10_score": -1,
                "signal": "MANUAL",
                "momentum": "Awaiting technical validation",
                "trend": "Awaiting technical validation",
                "setup_quality": "QUOTE VALIDATED",
                "risk_reward": "—",
                "manual_only": True,
                "data_source": "ANGEL ONE QUOTE",
            })
            if len(manual_stocks) >= 50:
                break

        indices = self._get_index_snapshots() if include_indices else []
        elapsed = round(time.time() - start, 2)
        gc.collect()
        return {
            "success": True,
            "count": len(top_results),
            "scanned": len(selected),
            "successful": len(top_results),
            "manual_count": len(manual_stocks),
            "time_seconds": elapsed,
            "stocks": top_results + manual_stocks,
            "top_opportunities": top_results,
            "indices": indices,
        }
