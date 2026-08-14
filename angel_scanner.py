from x10_engine import X10Engine
import time
import pandas as pd

from angel_service import AngelOneService
from angel_instruments import AngelInstrumentManager
from analysis import TechnicalAnalyzer


class AngelScanner:

    def __init__(
        self,
        batch_size=10,
        delay=1.0
    ):
        self.service = AngelOneService()
        self.instrument_manager = AngelInstrumentManager()
        self.x10_engine = X10Engine()

        self.batch_size = batch_size
        self.delay = delay

    # ==========================================================
    # SCORE STOCK
    # ==========================================================

    def analyze_stock(
        self,
        stock
    ):

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

            if dataframe is None:
                return None

            if dataframe.empty:
                return None

            analyzer = TechnicalAnalyzer(
                dataframe
            )

            analysis = analyzer.calculate()
            "x10_score": x10["x10_score"],

"signal": x10["signal"],

"entry": x10["entry"],

"stop_loss": x10["stop_loss"],

"target": x10["target"],

"risk": x10["risk"],

"reward": x10["reward"],

"risk_reward": x10["risk_reward"],

            technical_score = analysis.get(
                "technical_score",
                "x10_score": x10["x10_score"],

"signal": x10["signal"],
            )

            return {
                "symbol": symbol,
                "token": str(token),
                "name": name,

                "price": analysis.get(
                    "price",
                    0
                ),

                "technical_score": technical_score,

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

    def scan_market(
        self,
        limit=50
    ):

        start_time = time.time()

        try:

            # --------------------------------------------------
            # LOAD INSTRUMENT MASTER
            # --------------------------------------------------

            result = (
                self.instrument_manager.load_cache()
            )

            if not result.get("success"):

                return {
                    "success": False,
                    "message": (
                        "Unable to load "
                        "Angel One instruments."
                    ),
                    "stocks": []
                }

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
            # LIMIT FIRST SCAN
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

                analysis = (
                    self.analyze_stock(stock)
                )

                if analysis:

                    results.append(
                        analysis
                    )

                # Small delay prevents
                # aggressive API requests.

                time.sleep(
                    self.delay
                )

            # --------------------------------------------------
            # SORT
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
                f"Scanner completed in "
                f"{elapsed} seconds."
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

            return {
                "success": False,

                "message": str(
                    error
                ),

                "stocks": []
            }
