import time

from angel_service import AngelOneService
from angel_instruments import AngelInstrumentManager
from analysis import TechnicalAnalyzer


class AngelScanner:

    def __init__(self, batch_size=10, delay=1.0):

        self.service = AngelOneService()
        self.instrument_manager = AngelInstrumentManager()

        self.batch_size = batch_size
        self.delay = delay

    # ==========================================================
    # ANALYZE ONE STOCK
    # ==========================================================

    def analyze_stock(self, stock):

        symbol = stock.get("symbol")
        token = stock.get("token")
        name = stock.get("name", symbol)

        if not symbol or not token:
            return None

        try:

            dataframe = self.service.get_historical_dataframe(
                symbol=symbol,
                token=token,
                days=200,
                interval="ONE_DAY",
                exchange="NSE"
            )

            if dataframe is None or dataframe.empty:
                return None

            analyzer = TechnicalAnalyzer(dataframe)

            analysis = analyzer.calculate()

            technical_score = analysis.get(
                "technical_score",
                0
            )

            # --------------------------------------------------
            # X10 SCORE
            # --------------------------------------------------

            x10_score = technical_score

            # Extra momentum confirmation

            if analysis.get("trend") == "Strong Bullish":
                x10_score += 5

            elif analysis.get("trend") == "Bullish":
                x10_score += 3

            if analysis.get("momentum") == "Positive":
                x10_score += 5

            # RSI confirmation

            rsi = analysis.get("rsi", 50)

            if 55 <= rsi <= 70:
                x10_score += 5

            # ADX confirmation

            adx = analysis.get("adx", 0)

            if adx >= 25:
                x10_score += 5

            # Volume confirmation

            volume_ratio = analysis.get(
                "volume_ratio",
                0
            )

            if volume_ratio >= 1.5:
                x10_score += 5

            x10_score = min(
                int(x10_score),
                100
            )

            # --------------------------------------------------
            # SUCCESS PROBABILITY
            # --------------------------------------------------

            probability = x10_score

            if probability >= 80:
                signal = "VERY STRONG"

            elif probability >= 70:
                signal = "STRONG"

            elif probability >= 60:
                signal = "BULLISH"

            elif probability >= 50:
                signal = "NEUTRAL"

            else:
                signal = "WEAK"

            # --------------------------------------------------
            # FINAL STOCK RESULT
            # --------------------------------------------------

            return {

                "symbol": symbol,

                "token": str(token),

                "name": name,

                "price": analysis.get(
                    "price",
                    0
                ),

                "technical_score": technical_score,

                "x10_score": x10_score,

                "success_probability": probability,

                "signal": signal,

                "trend": analysis.get(
                    "trend",
                    "Neutral"
                ),

                "momentum": analysis.get(
                    "momentum",
                    "Neutral"
                ),

                "rsi": analysis.get(
                    "rsi",
                    0
                ),

                "ema20": analysis.get(
                    "ema20",
                    0
                ),

                "ema50": analysis.get(
                    "ema50",
                    0
                ),

                "ema200": analysis.get(
                    "ema200",
                    0
                ),

                "macd": analysis.get(
                    "macd",
                    0
                ),

                "macd_signal": analysis.get(
                    "macd_signal",
                    0
                ),

                "macd_histogram": analysis.get(
                    "macd_histogram",
                    0
                ),

                "adx": analysis.get(
                    "adx",
                    0
                ),

                "plus_di": analysis.get(
                    "plus_di",
                    0
                ),

                "minus_di": analysis.get(
                    "minus_di",
                    0
                ),

                "support": analysis.get(
                    "support",
                    0
                ),

                "resistance": analysis.get(
                    "resistance",
                    0
                ),

                "volume_ratio": analysis.get(
                    "volume_ratio",
                    0
                ),

                "atr": analysis.get(
                    "atr",
                    0
                ),

                "52_week_high": analysis.get(
                    "52_week_high",
                    0
                ),

                "52_week_low": analysis.get(
                    "52_week_low",
                    0
                )
            }

        except Exception as error:

            print(
                f"Scanner error {symbol}: {error}"
            )

            return None

    # ==========================================================
    # SCAN MARKET
    # ==========================================================

    def scan_market(self, limit=50):

        start_time = time.time()

        try:

            # --------------------------------------------------
            # LOAD ANGEL ONE INSTRUMENTS
            # --------------------------------------------------

            result = self.instrument_manager.load_cache()

            if not result.get("success"):

                return {
                    "success": False,
                    "message": "Unable to load Angel One instruments.",
                    "stocks": []
                }

            stocks = self.instrument_manager.get_nse_equities()

            if not stocks:

                return {
                    "success": False,
                    "message": "No NSE equity stocks found.",
                    "stocks": []
                }

            # --------------------------------------------------
            # LIMIT FIRST SCAN
            # --------------------------------------------------

            stocks = stocks[:limit]

            print(
                f"Starting scanner for {len(stocks)} stocks..."
            )

            results = []

            # --------------------------------------------------
            # PROCESS STOCKS
            # --------------------------------------------------

            for index, stock in enumerate(
                stocks,
                start=1
            ):

                print(
                    f"[{index}/{len(stocks)}] "
                    f"{stock.get('symbol')}"
                )

                analysis = self.analyze_stock(stock)

                if analysis:

                    results.append(
                        analysis
                    )

                time.sleep(
                    self.delay
                )

            # --------------------------------------------------
            # SORT BY X10 SCORE
            # --------------------------------------------------

            results.sort(
                key=lambda item: item.get(
                    "x10_score",
                    0
                ),
                reverse=True
            )

            # --------------------------------------------------
            # TOP OPPORTUNITIES
            # --------------------------------------------------

            top_stocks = results[:20]

            elapsed = round(
                time.time() - start_time,
                2
            )

            print(
                f"Scanner completed in {elapsed} seconds."
            )

            return {

                "success": True,

                "count": len(
                    top_stocks
                ),

                "scanned": len(
                    stocks
                ),

                "successful": len(
                    results
                ),

                "time_seconds": elapsed,

                "stocks": top_stocks
            }

        except Exception as error:

            print(
                "Market scanner error:",
                error
            )

            return {

                "success": False,

                "message": str(
                    error
                ),

                "stocks": []
            }
