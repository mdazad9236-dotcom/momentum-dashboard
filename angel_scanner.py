import gc
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

from x10_engine import X10Engine
from angel_service import AngelOneService
from angel_instruments import AngelInstrumentManager
from analysis import TechnicalAnalyzer
from market_indices import INDEX_DEFINITIONS, build_index_snapshot

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
    """Fast, memory-conscious market scanner with X10 as the decision engine."""

    def __init__(self, batch_size=5, delay=0.0, max_workers=2):
        self.service = AngelOneService()
        self.instrument_manager = AngelInstrumentManager()
        self.x10_engine = X10Engine()
        self.batch_size = max(1, int(batch_size))
        self.delay = max(0.0, float(delay))
        self.max_workers = max(1, int(max_workers))
        self.quote_limit = max(200, int(os.getenv("X10_QUOTE_UNIVERSE", "1000")))
        self.analysis_limit = max(10, int(os.getenv("X10_ANALYSIS_CANDIDATES", "30")))
        self.min_price = float(os.getenv("X10_MIN_PRICE", "2"))
        self.max_price = float(os.getenv("X10_MAX_PRICE", "300"))

    def analyze_stock(self, stock):
        symbol = stock.get("symbol")
        token = stock.get("token")
        name = stock.get("name", symbol)
        if not symbol or not token:
            return None
        started = time.time()
        dataframe = None
        try:
            dataframe = self.service.get_historical_dataframe(
                symbol, token, days=100, interval="ONE_DAY", exchange="NSE"
            )
            if dataframe is None or dataframe.empty:
                return None
            analysis = TechnicalAnalyzer(dataframe).calculate()
            if not analysis:
                return None
            x10_input = {**analysis, "price": analysis.get("price", 0)}
            x10 = self.x10_engine.analyze(x10_input)
            if not x10:
                return None
            return self._format_result(symbol, token, name, analysis, x10, started, "ANGEL ONE")
        except Exception as error:
            print(f"[STOCK] {symbol} ERROR: {error}")
            return None
        finally:
            dataframe = None

    def _format_result(self, symbol, token, name, analysis, x10, started, source):
        return {
            "symbol": symbol,
            "token": str(token or ""),
            "name": name,
            "price": analysis.get("price", 0),
            "technical_score": analysis.get("technical_score", 0),
            "x10_score": x10.get("x10_score", 0),
            # Kept for UI compatibility; this is deliberately not a probability.
            "confidence": x10.get("confidence", "LOW"),
            "success_probability": None,
            "signal": x10.get("signal", "AVOID"),
            "early_momentum_score": x10.get("early_momentum_score", 0),
            "momentum_stage": x10.get("momentum_stage", "WATCH"),
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
            "risk_reward_display": x10.get("risk_reward_display", "1:0"),
            "risk_reward_value": x10.get("risk_reward_value", 0),
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
            "data_source": source,
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

    @staticmethod
    def _yahoo_candidate(symbol):
        try:
            history = yf.Ticker(f"{symbol}.NS").history(period="6mo", interval="1d", auto_adjust=False)
            if history is None or history.empty:
                return None
            analysis = TechnicalAnalyzer(history).calculate()
            x10 = X10Engine().analyze({**analysis, "price": analysis.get("price", 0)})
            if not x10:
                return None
            return AngelScanner()._format_result(symbol, "", symbol, analysis, x10, time.time(), "YAHOO FALLBACK")
        except Exception as error:
            print(f"[FALLBACK] {symbol} ERROR: {error}")
            return None

    def _fallback_yfinance_scan(self, limit=6):
        symbols = FALLBACK_STOCKS[:max(1, int(limit))]
        results = []
        started = time.time()
        with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
            futures = [executor.submit(self._yahoo_candidate, symbol) for symbol in symbols]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        result["scan_time"] = round(time.time() - started, 2)
                        results.append(result)
                except Exception as error:
                    print(f"[FALLBACK-BATCH] ERROR: {error}")
        results.sort(key=self._opportunity_key, reverse=True)
        return results[:max(1, int(limit))]

    @staticmethod
    def _opportunity_key(item):
        return (
            float(item.get("x10_score", 0) or 0),
            float(item.get("early_momentum_score", 0) or 0),
            float(item.get("risk_reward_value", 0) or 0),
        )

    @staticmethod
    def _quote_candidate_key(item):
        """Fast pre-analysis ranking using only quote data."""
        price = float(item.get("ltp", 0) or 0)
        change_pct = abs(float(item.get("percentChange", item.get("percentchange", 0)) or 0))
        volume = float(item.get("tradeVolume", item.get("tradevolume", 0)) or 0)
        return (change_pct, volume > 0, volume, -price)

    def _select_quote_candidates(self, quotes, requested_limit):
        eligible = []
        for quote in quotes:
            price = float(quote.get("ltp", 0) or 0)
            if not self.min_price <= price <= self.max_price:
                continue
            quote["name"] = quote.get("name") or quote.get("symbol") or quote.get("tradingsymbol", "")
            quote["symbol"] = quote.get("symbol") or quote.get("tradingsymbol", "")
            if not quote.get("symbol") or not quote.get("token", quote.get("symbolToken")):
                continue
            eligible.append(quote)
        eligible.sort(key=self._quote_candidate_key, reverse=True)
        # Technical analysis is the expensive stage. Over-scan quote candidates
        # but cap historical requests so a large universe remains responsive.
        return eligible[:max(requested_limit, min(self.analysis_limit, len(eligible)))]

    def _get_index_snapshots(self):
        definitions = [{"name": name, **definition} for name, definition in INDEX_DEFINITIONS.items()]
        quote_result = self.service.get_quotes(definitions)
        quotes = {
            (str(q.get("exchange")), str(q.get("token", q.get("symbolToken", "")))): q
            for q in quote_result.get("quotes", [])
        } if quote_result.get("success") else {}
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
                    close = float(recent[-2][4]) if len(recent) >= 2 else price
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
        analysis_limit = min(requested_limit, self.analysis_limit)

        login = self.service.login()
        if not login.get("success"):
            fallback_results = self._fallback_yfinance_scan(min(analysis_limit, 6))
            return self._response(fallback_results, [], start, "Angel One unavailable; showing fallback market-data candidates.")

        cache = self.instrument_manager.load_cache()
        if not cache.get("success"):
            fallback_results = self._fallback_yfinance_scan(min(analysis_limit, 6))
            return self._response(fallback_results, [], start, "Instrument master unavailable; showing fallback market-data candidates.")

        universe = self.instrument_manager.get_nse_equities()
        # AngelOneService.get_quotes already chunks requests into groups of 50.
        # Scan a substantially wider universe than the old first-200 slice while
        # keeping the cap configurable for rate-limit/performance control.
        quote_universe = universe[:self.quote_limit]
        quote_result = self.service.get_quotes(quote_universe)
        if not quote_result.get("success"):
            fallback_results = self._fallback_yfinance_scan(min(analysis_limit, 6))
            return self._response(fallback_results, [], start, "Angel One quote scan failed; showing fallback market-data candidates.")

        candidates = self._select_quote_candidates(quote_result.get("quotes", []), analysis_limit)
        if not candidates:
            fallback_results = self._fallback_yfinance_scan(min(analysis_limit, 6))
            return self._response(fallback_results, [], start, "No affordable liquid quote candidates were returned.")

        results = []
        for offset in range(0, len(candidates), self.batch_size):
            batch = candidates[offset:offset + self.batch_size]
            results.extend(self._analyze_batch(batch))
            if self.delay:
                time.sleep(self.delay)

        results.sort(key=self._opportunity_key, reverse=True)
        top_results = results[:requested_limit]
        indices = self._get_index_snapshots() if include_indices else []

        analyzed_symbols = {str(item.get("symbol", "")).upper() for item in results}
        manual_stocks = []
        for quote in candidates:
            symbol = str(quote.get("symbol", "")).upper()
            if not symbol or symbol in analyzed_symbols:
                continue
            manual_stocks.append({
                "symbol": symbol,
                "token": str(quote.get("token", quote.get("symbolToken", ""))),
                "name": quote.get("name") or symbol,
                "price": float(quote.get("ltp", 0) or 0),
                "x10_score": -1,
                "early_momentum_score": 0,
                "signal": "PENDING",
                "momentum_stage": "QUOTE RADAR",
                "momentum": "Awaiting technical validation",
                "trend": "Awaiting technical validation",
                "setup_quality": "QUOTE VALIDATED",
                "risk_reward": "—",
                "manual_only": True,
                "data_source": "ANGEL ONE QUOTE",
            })
            if len(manual_stocks) >= 20:
                break

        gc.collect()
        elapsed = round(time.time() - start, 2)
        return {
            "success": True,
            "count": len(top_results),
            "scanned": len(candidates),
            "successful": len(results),
            "manual_count": len(manual_stocks),
            "time_seconds": elapsed,
            "stocks": top_results + manual_stocks,
            "top_opportunities": top_results[:5],
            "early_momentum_radar": [
                item for item in results
                if item.get("momentum_stage") in ("EARLY ACCELERATION", "DEVELOPING MOMENTUM")
            ][:5],
            "indices": indices,
        }

    def _response(self, stocks, indices, started, message):
        return {
            "success": True,
            "message": message,
            "stocks": stocks,
            "top_opportunities": stocks[:5],
            "early_momentum_radar": stocks[:5],
            "count": len(stocks),
            "scanned": len(stocks),
            "successful": len(stocks),
            "manual_count": 0,
            "time_seconds": round(time.time() - started, 2),
            "indices": indices or (self._get_index_snapshots() if True else []),
        }
