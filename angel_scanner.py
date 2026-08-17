import time

from x10_engine import X10Engine
from angel_service import AngelOneService
from angel_instruments import AngelInstrumentManager
from analysis import TechnicalAnalyzer


class AngelScanner:

    def __init__(self, batch_size=10, delay=1.0):

        self.service = AngelOneService()
        self.instrument_manager = AngelInstrumentManager()
        self.x10_engine = X10Engine()

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

            # --------------------------------------------------
            # GET HISTORICAL DATA FROM ANGEL ONE
            # --------------------------------------------------

            dataframe = self.service.get_historical_dataframe(
                symbol=symbol,
                token=token,
                days=200,
                interval="ONE_DAY",
                exchange="NSE"
            )

            if dataframe is None or dataframe.empty:
                return None

            # --------------------------------------------------
            # TECHNICAL ANALYSIS
            # --------------------------------------------------

            analyzer = TechnicalAnalyzer(dataframe)

            analysis = analyzer.calculate()

            if analysis is None:
                return None

            # --------------------------------------------------
            # X10 ENGINE
            # --------------------------------------------------

            x10_result = self.x10_engine.analyze(
                analysis
            )

            if x10_result is None:
                return None

            # --------------------------------------------------
            # BASIC VALUES
            # --------------------------------------------------

            technical_score = analysis.get(
                "technical_score",
                0
            )

            x10_score = x10_result.get(
                "x10_score",
                0
            )

            signal = x10_result.get(
                "signal",
                "AVOID"
            )

            # --------------------------------------------------
            # EXISTING COMPATIBILITY FIELD
            #
            # NOTE:
            # This is kept for API compatibility.
            # It should not be interpreted as a real
            # statistical probability.
            # --------------------------------------------------

            probability = x10_score

            # --------------------------------------------------
            # FINAL STOCK RESULT
            # --------------------------------------------------

            return {

                # --------------------------------------------------
                # IDENTIFICATION
                # --------------------------------------------------

                "symbol": symbol,

                "token": str(token),

                "name": name,

                # --------------------------------------------------
                # PRICE
                # --------------------------------------------------

                "price": analysis.get(
                    "price",
                    0
                ),

                # --------------------------------------------------
                # SCORES
                # --------------------------------------------------

                "technical_score": technical_score,

                "x10_score": x10_score,

                "success_probability": probability,

                # --------------------------------------------------
                # X10 SIGNAL
                # --------------------------------------------------

                "signal": signal,

                # --------------------------------------------------
                # TRADE PLAN
                # --------------------------------------------------

                "entry": x10_result.get(
                    "entry",
                    0
                ),

                "stop_loss": x10_result.get(
                    "stop_loss",
                    0
                ),

                "target": x10_result.get(
                    "target",
                    0
                ),

                "risk": x10_result.get(
                    "risk",
                    0
                ),

                "reward": x10_result.get(
                    "reward",
                    0
                ),

                "risk_reward": x10_result.get(
                    "risk_reward",
                    0
                ),

                # --------------------------------------------------
                # TREND / MOMENTUM
                # --------------------------------------------------

                "trend": analysis.get(
                    "trend",
                    "Neutral"
                ),

                "momentum": analysis.get(
                    "momentum",
                    "Neutral"
                ),

                # --------------------------------------------------
                # RSI
                # --------------------------------------------------

                "rsi": analysis.get(
                    "rsi",
                    0
                ),

                # --------------------------------------------------
                # MOVING AVERAGES
                # --------------------------------------------------

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

                # --------------------------------------------------
                # MACD
                # --------------------------------------------------

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

                # --------------------------------------------------
                # ADX / DIRECTIONAL MOVEMENT
                # --------------------------------------------------

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

                # --------------------------------------------------
                # SUPPORT / RESISTANCE
                # --------------------------------------------------

                "support": analysis.get(
                    "support",
                    0
                ),

                "resistance": analysis.get(
                    "resistance",
                    0
                ),

                # --------------------------------------------------
                # VOLUME
                # --------------------------------------------------

                "volume_ratio": analysis.get(
                    "volume_ratio",
                    0
                ),

                # --------------------------------------------------
                # VOLATILITY
                # --------------------------------------------------

                "atr": analysis.get(
                    "atr",
                    0
                ),

                # --------------------------------------------------
                # 52 WEEK RANGE
                # --------------------------------------------------

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
                    "message": (
                        "Unable to load Angel One instruments."
                    ),
                    "stocks": []
                }

            # --------------------------------------------------
            # GET NSE EQUITIES
            # --------------------------------------------------

            stocks = (
                self.instrument_manager
                .get_nse_equities()
            )

            if not stocks:

                return {
                    "success": False,
                    "message": (
                        "No NSE equity stocks found."
                    ),
                    "stocks": []
                }

            # --------------------------------------------------
            # LIMIT SCAN
            # --------------------------------------------------

            stocks = stocks[:limit]

            print(
                f"Starting scanner for "
                f"{len(stocks)} stocks..."
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

                stock_analysis = (
                    self.analyze_stock(stock)
                )

                if stock_analysis:

                    results.append(
                        stock_analysis
                    )

                # --------------------------------------------------
                # DELAY BETWEEN REQUESTS
                # --------------------------------------------------

                if index < len(stocks):

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

            # --------------------------------------------------
            # SCAN TIME
            # --------------------------------------------------

            elapsed = round(
                time.time() - start_time,
                2
            )

            print(
                f"Scanner completed in "
                f"{elapsed} seconds."
            )

            # --------------------------------------------------
            # FINAL RESPONSE
            # --------------------------------------------------

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
