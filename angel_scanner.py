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
            print(
                "[STOCK] Missing symbol or token."
            )
            return None

        stock_start = time.time()

        try:

            print(
                f"[STOCK] {symbol} "
                f"START"
            )

            # --------------------------------------------------
            # GET HISTORICAL DATA FROM ANGEL ONE
            # --------------------------------------------------

            print(
                f"[STOCK] {symbol} "
                f"Requesting historical data..."
            )

            historical_start = time.time()

            dataframe = self.service.get_historical_dataframe(
                symbol=symbol,
                token=token,
                days=100,
                interval="ONE_DAY",
                exchange="NSE"
            )

            historical_time = round(
                time.time() - historical_start,
                2
            )

            print(
                f"[STOCK] {symbol} "
                f"Historical data completed in "
                f"{historical_time}s"
            )

            if dataframe is None or dataframe.empty:

                print(
                    f"[STOCK] {symbol} "
                    f"No historical data."
                )

                return None

            print(
                f"[STOCK] {symbol} "
                f"Historical rows: "
                f"{len(dataframe)}"
            )

            # --------------------------------------------------
            # TECHNICAL ANALYSIS
            # --------------------------------------------------

            print(
                f"[STOCK] {symbol} "
                f"Technical analysis START..."
            )

            technical_start = time.time()

            analyzer = TechnicalAnalyzer(
                dataframe
            )

            analysis = analyzer.calculate()

            technical_time = round(
                time.time() - technical_start,
                2
            )

            print(
                f"[STOCK] {symbol} "
                f"Technical analysis completed in "
                f"{technical_time}s"
            )

            if analysis is None:

                print(
                    f"[STOCK] {symbol} "
                    f"Technical analysis returned no result."
                )

                return None

            # --------------------------------------------------
            # X10 ENGINE
            # --------------------------------------------------

            print(
                f"[STOCK] {symbol} "
                f"X10 analysis START..."
            )

            x10_start = time.time()

            x10_result = self.x10_engine.analyze(
                analysis
            )

            x10_time = round(
                time.time() - x10_start,
                2
            )

            print(
                f"[STOCK] {symbol} "
                f"X10 analysis completed in "
                f"{x10_time}s"
            )

            if x10_result is None:

                print(
                    f"[STOCK] {symbol} "
                    f"X10 returned no result."
                )

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
            # Kept exactly as before.
            # This is not a statistical probability.
            # --------------------------------------------------

            probability = x10_score

            # --------------------------------------------------
            # FINAL STOCK RESULT
            # --------------------------------------------------

            result = {

                # ------------------------------------------------
                # IDENTIFICATION
                # ------------------------------------------------

                "symbol": symbol,

                "token": str(token),

                "name": name,

                # ------------------------------------------------
                # PRICE
                # ------------------------------------------------

                "price": analysis.get(
                    "price",
                    0
                ),

                # ------------------------------------------------
                # SCORES
                # ------------------------------------------------

                "technical_score": technical_score,

                "x10_score": x10_score,

                "success_probability": probability,

                # ------------------------------------------------
                # X10 SIGNAL
                # ------------------------------------------------

                "signal": signal,

                # ------------------------------------------------
                # TRADE PLAN
                # ------------------------------------------------

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

                # ------------------------------------------------
                # TREND / MOMENTUM
                # ------------------------------------------------

                "trend": analysis.get(
                    "trend",
                    "Neutral"
                ),

                "momentum": analysis.get(
                    "momentum",
                    "Neutral"
                ),

                # ------------------------------------------------
                # RSI
                # ------------------------------------------------

                "rsi": analysis.get(
                    "rsi",
                    0
                ),

                # ------------------------------------------------
                # MOVING AVERAGES
                # ------------------------------------------------

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

                # ------------------------------------------------
                # MACD
                # ------------------------------------------------

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

                # ------------------------------------------------
                # ADX / DIRECTIONAL MOVEMENT
                # ------------------------------------------------

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

                # ------------------------------------------------
                # SUPPORT / RESISTANCE
                # ------------------------------------------------

                "support": analysis.get(
                    "support",
                    0
                ),

                "resistance": analysis.get(
                    "resistance",
                    0
                ),

                # ------------------------------------------------
                # VOLUME
                # ------------------------------------------------

                "volume_ratio": analysis.get(
                    "volume_ratio",
                    0
                ),

                # ------------------------------------------------
                # VOLATILITY
                # ------------------------------------------------

                "atr": analysis.get(
                    "atr",
                    0
                ),

                # ------------------------------------------------
                # 52 WEEK RANGE
                # ------------------------------------------------

                "52_week_high": analysis.get(
                    "52_week_high",
                    0
                ),

                "52_week_low": analysis.get(
                    "52_week_low",
                    0
                )
            }

            total_stock_time = round(
                time.time() - stock_start,
                2
            )

            print(
                f"[STOCK] {symbol} "
                f"COMPLETE in "
                f"{total_stock_time}s "
                f"| X10 Score: {x10_score} "
                f"| Signal: {signal}"
            )

            return result

        except Exception as error:

            total_stock_time = round(
                time.time() - stock_start,
                2
            )

            print(
                f"[STOCK] {symbol} "
                f"ERROR after "
                f"{total_stock_time}s: "
                f"{error}"
            )

            return None

    # ==========================================================
    # SCAN MARKET
    # ==========================================================

    def scan_market(self, limit=50):

        start_time = time.time()

        print(
            "=================================================="
        )

        print(
            "X10 MARKET SCANNER STARTING"
        )

        print(
            f"Requested limit: {limit}"
        )

        print(
            f"Batch size: {self.batch_size}"
        )

        print(
            f"Delay: {self.delay}s"
        )

        print(
            "=================================================="
        )

        try:

            # --------------------------------------------------
            # LOAD ANGEL ONE INSTRUMENTS
            # --------------------------------------------------

            print(
                "[SCAN] Loading Angel One instrument cache..."
            )

            instrument_start = time.time()

            result = (
                self.instrument_manager
                .load_cache()
            )

            instrument_time = round(
                time.time() - instrument_start,
                2
            )

            print(
                "[SCAN] Instrument loading completed in "
                f"{instrument_time}s"
            )

            if not result.get("success"):

                print(
                    "[SCAN] Instrument loading FAILED:"
                    f" {result.get('message')}"
                )

                return {

                    "success": False,

                    "message": (
                        "Unable to load Angel One instruments."
                    ),

                    "stocks": []
                }

            print(
                "[SCAN] Instruments available: "
                f"{result.get('count', 0)}"
            )

            # --------------------------------------------------
            # GET NSE EQUITIES
            # --------------------------------------------------

            print(
                "[SCAN] Getting NSE equity stocks..."
            )

            equity_start = time.time()

            stocks = (
                self.instrument_manager
                .get_nse_equities()
            )

            equity_time = round(
                time.time() - equity_start,
                2
            )

            print(
                "[SCAN] NSE equity filtering completed in "
                f"{equity_time}s"
            )

            if not stocks:

                print(
                    "[SCAN] No NSE equity stocks found."
                )

                return {

                    "success": False,

                    "message": (
                        "No NSE equity stocks found."
                    ),

                    "stocks": []
                }

            print(
                f"[SCAN] Total NSE equities available: "
                f"{len(stocks)}"
            )

            # --------------------------------------------------
            # LIMIT SCAN
            # --------------------------------------------------

            stocks = stocks[:limit]

            print(
                "=================================================="
            )

            print(
                f"[SCAN] Starting scan for "
                f"{len(stocks)} stocks..."
            )

            print(
                "=================================================="
            )

            results = []

            # --------------------------------------------------
            # PROCESS STOCKS
            # --------------------------------------------------

            for index, stock in enumerate(
                stocks,
                start=1
            ):

                symbol = stock.get(
                    "symbol",
                    "UNKNOWN"
                )

                print(
                    ""
                )

                print(
                    "--------------------------------------------------"
                )

                print(
                    f"[SCAN] STOCK {index}/{len(stocks)}: "
                    f"{symbol}"
                )

                print(
                    "--------------------------------------------------"
                )

                stock_analysis = (
                    self.analyze_stock(
                        stock
                    )
                )

                if stock_analysis:

                    results.append(
                        stock_analysis
                    )

                    print(
                        f"[SCAN] {symbol} "
                        f"ADDED TO RESULTS"
                    )

                else:

                    print(
                        f"[SCAN] {symbol} "
                        f"SKIPPED"
                    )

                # ------------------------------------------------
                # DELAY BETWEEN REQUESTS
                # ------------------------------------------------

                if index < len(stocks):

                    print(
                        f"[SCAN] Waiting "
                        f"{self.delay}s before next stock..."
                    )

                    time.sleep(
                        self.delay
                    )

            # --------------------------------------------------
            # SORT BY X10 SCORE
            # --------------------------------------------------

            print(
                "[SCAN] Sorting results by X10 score..."
            )

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
                "=================================================="
            )

            print(
                "[SCAN] X10 SCANNER COMPLETED"
            )

            print(
                f"[SCAN] Scanned: {len(stocks)}"
            )

            print(
                f"[SCAN] Successful: {len(results)}"
            )

            print(
                f"[SCAN] Returned: {len(top_stocks)}"
            )

            print(
                f"[SCAN] Total time: {elapsed}s"
            )

            print(
                "=================================================="
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

            elapsed = round(
                time.time() - start_time,
                2
            )

            print(
                "=================================================="
            )

            print(
                "MARKET SCANNER ERROR"
            )

            print(
                f"Time before error: {elapsed}s"
            )

            print(
                f"Error: {error}"
            )

            print(
                "=================================================="
            )

            return {

                "success": False,

                "message": str(
                    error
                ),

                "stocks": []
            }
