import pandas as pd
import numpy as np


class TechnicalAnalyzer:
    """
    Technical analysis engine for OHLCV market data.

    Expected DataFrame columns:
        Open
        High
        Low
        Close
        Volume
    """

    def __init__(self, history: pd.DataFrame):

        if history is None or history.empty:
            raise ValueError("Market history is empty.")

        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        missing = [
            column
            for column in required_columns
            if column not in history.columns
        ]

        if missing:
            raise ValueError(
                f"Missing required market data columns: {missing}"
            )

        self.df = history.copy()

        # Make sure data is ordered chronologically.
        self.df = self.df.sort_index()

        # Convert numeric columns safely.
        for column in required_columns:
            self.df[column] = pd.to_numeric(
                self.df[column],
                errors="coerce"
            )

        self.df = self.df.dropna(
            subset=["High", "Low", "Close"]
        )

    # ============================================================
    # BASIC PRICE
    # ============================================================

    def current_price(self):
        return round(
            float(self.df["Close"].iloc[-1]),
            2
        )

    # ============================================================
    # RSI
    # ============================================================

    def calculate_rsi(self, period=14):

        if len(self.df) < period + 1:
            return 50.0

        close = self.df["Close"]

        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # Wilder-style smoothing using EWM.
        avg_gain = gain.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        avg_loss = loss.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        last_gain = avg_gain.iloc[-1]
        last_loss = avg_loss.iloc[-1]

        if pd.isna(last_gain) or pd.isna(last_loss):
            return 50.0

        if last_loss == 0:
            return 100.0

        rs = last_gain / last_loss

        rsi = 100 - (
            100 / (1 + rs)
        )

        return round(float(rsi), 2)

    # ============================================================
    # EMA
    # ============================================================

    def ema(self, period):

        if len(self.df) == 0:
            return 0.0

        ema_value = (
            self.df["Close"]
            .ewm(
                span=period,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        return round(
            float(ema_value),
            2
        )

    # ============================================================
    # MACD
    # ============================================================

    def macd(self):

        close = self.df["Close"]

        ema12 = close.ewm(
            span=12,
            adjust=False
        ).mean()

        ema26 = close.ewm(
            span=26,
            adjust=False
        ).mean()

        macd_line = ema12 - ema26

        signal_line = macd_line.ewm(
            span=9,
            adjust=False
        ).mean()

        histogram = (
            macd_line - signal_line
        )

        return {
            "macd": round(
                float(macd_line.iloc[-1]),
                2
            ),
            "signal": round(
                float(signal_line.iloc[-1]),
                2
            ),
            "histogram": round(
                float(histogram.iloc[-1]),
                2
            ),
        }

    # ============================================================
    # ATR
    # ============================================================

    def atr(self, period=14):

        if len(self.df) < period + 1:
            return 0.0

        high = self.df["High"]
        low = self.df["Low"]
        close = self.df["Close"]

        previous_close = close.shift(1)

        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1
        ).max(axis=1)

        atr_value = (
            true_range
            .ewm(
                alpha=1 / period,
                adjust=False,
                min_periods=period
            )
            .mean()
            .iloc[-1]
        )

        if pd.isna(atr_value):
            return 0.0

        return round(
            float(atr_value),
            2
        )

    # ============================================================
    # ADX
    # ============================================================

    def adx(self, period=14):

        if len(self.df) < (period * 2):
            return {
                "adx": 25.0,
                "plus_di": 0.0,
                "minus_di": 0.0,
            }

        high = self.df["High"]
        low = self.df["Low"]
        close = self.df["Close"]

        previous_high = high.shift(1)
        previous_low = low.shift(1)
        previous_close = close.shift(1)

        up_move = high - previous_high
        down_move = previous_low - low

        plus_dm = pd.Series(
            np.where(
                (up_move > down_move) &
                (up_move > 0),
                up_move,
                0.0
            ),
            index=self.df.index
        )

        minus_dm = pd.Series(
            np.where(
                (down_move > up_move) &
                (down_move > 0),
                down_move,
                0.0
            ),
            index=self.df.index
        )

        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1
        ).max(axis=1)

        atr = true_range.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        plus_dm_smoothed = plus_dm.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        minus_dm_smoothed = minus_dm.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        plus_di = (
            100 *
            plus_dm_smoothed /
            atr.replace(0, np.nan)
        )

        minus_di = (
            100 *
            minus_dm_smoothed /
            atr.replace(0, np.nan)
        )

        denominator = (
            plus_di + minus_di
        ).replace(0, np.nan)

        dx = (
            100 *
            (plus_di - minus_di).abs() /
            denominator
        )

        adx_series = dx.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        adx_value = adx_series.iloc[-1]
        plus_di_value = plus_di.iloc[-1]
        minus_di_value = minus_di.iloc[-1]

        if pd.isna(adx_value):
            adx_value = 25.0

        if pd.isna(plus_di_value):
            plus_di_value = 0.0

        if pd.isna(minus_di_value):
            minus_di_value = 0.0

        return {
            "adx": round(float(adx_value), 2),
            "plus_di": round(float(plus_di_value), 2),
            "minus_di": round(float(minus_di_value), 2),
        }

    # ============================================================
    # SUPPORT
    # ============================================================

    def support(self, period=20):

        if self.df.empty:
            return 0.0

        return round(
            float(
                self.df["Low"]
                .tail(period)
                .min()
            ),
            2
        )

    # ============================================================
    # RESISTANCE
    # ============================================================

    def resistance(self, period=20):

        if self.df.empty:
            return 0.0

        return round(
            float(
                self.df["High"]
                .tail(period)
                .max()
            ),
            2
        )

    # ============================================================
    # VOLUME ANALYSIS
    # ============================================================

    def volume_analysis(self, period=20):

        if "Volume" not in self.df.columns:
            return {
                "volume": 0,
                "average_volume": 0,
                "volume_ratio": 0.0,
            }

        volume = self.df["Volume"]

        current_volume = volume.iloc[-1]

        average_volume = (
            volume
            .rolling(period)
            .mean()
            .iloc[-1]
        )

        if (
            pd.isna(average_volume)
            or average_volume == 0
        ):
            ratio = 0.0
        else:
            ratio = (
                current_volume /
                average_volume
            )

        return {
            "volume": int(current_volume),
            "average_volume": round(
                float(average_volume)
                if not pd.isna(average_volume)
                else 0,
                0
            ),
            "volume_ratio": round(
                float(ratio),
                2
            ),
        }

    # ============================================================
    # 52 WEEK RANGE
    # ============================================================

    def yearly_range(self):

        window = self.df.tail(252)

        if window.empty:
            return {
                "52_week_high": 0.0,
                "52_week_low": 0.0,
            }

        return {
            "52_week_high": round(
                float(window["High"].max()),
                2
            ),
            "52_week_low": round(
                float(window["Low"].min()),
                2
            ),
        }

    # ============================================================
    # TREND
    # ============================================================

    def trend(self):

        price = self.current_price()

        ema20 = self.ema(20)
        ema50 = self.ema(50)
        ema200 = self.ema(200)

        if (
            price > ema20
            and ema20 > ema50
            and ema50 > ema200
        ):
            return "Strong Bullish"

        if (
            price > ema20
            and ema20 > ema50
        ):
            return "Bullish"

        if (
            price < ema20
            and ema20 < ema50
            and ema50 < ema200
        ):
            return "Strong Bearish"

        if (
            price < ema20
            and ema20 < ema50
        ):
            return "Bearish"

        return "Neutral"

    # ============================================================
    # MOMENTUM
    # ============================================================

    def momentum(self):

        rsi = self.calculate_rsi()

        macd_data = self.macd()

        histogram = macd_data["histogram"]

        if (
            rsi >= 55
            and histogram > 0
        ):
            return "Positive"

        if (
            rsi <= 45
            and histogram < 0
        ):
            return "Negative"

        return "Neutral"

    # ============================================================
    # TECHNICAL SCORE
    # ============================================================

    def technical_score(self):

        score = 0

        price = self.current_price()

        ema20 = self.ema(20)
        ema50 = self.ema(50)
        ema200 = self.ema(200)

        rsi = self.calculate_rsi()

        macd_data = self.macd()

        adx_data = self.adx()

        volume_data = self.volume_analysis()

        # --------------------------------------------------------
        # Trend structure
        # --------------------------------------------------------

        if price > ema20:
            score += 10

        if ema20 > ema50:
            score += 10

        if ema50 > ema200:
            score += 10

        # --------------------------------------------------------
        # RSI
        # --------------------------------------------------------

        if 50 <= rsi <= 70:
            score += 15
        elif 45 <= rsi < 50:
            score += 8
        elif 70 < rsi <= 75:
            score += 8

        # --------------------------------------------------------
        # MACD
        # --------------------------------------------------------

        if macd_data["macd"] > macd_data["signal"]:
            score += 15

        if macd_data["histogram"] > 0:
            score += 10

        # --------------------------------------------------------
        # ADX trend strength
        # --------------------------------------------------------

        if adx_data["adx"] >= 25:
            score += 10
        elif adx_data["adx"] >= 20:
            score += 5

        # --------------------------------------------------------
        # Directional movement
        # --------------------------------------------------------

        if (
            adx_data["plus_di"] >
            adx_data["minus_di"]
        ):
            score += 5

        # --------------------------------------------------------
        # Volume
        # --------------------------------------------------------

        if volume_data["volume_ratio"] >= 1.2:
            score += 5

        return min(
            int(score),
            100
        )

    # ============================================================
    # FINAL TECHNICAL ANALYSIS
    # ============================================================

    def calculate(self):

        macd_data = self.macd()

        adx_data = self.adx()

        volume_data = self.volume_analysis()

        yearly_data = self.yearly_range()

        score = self.technical_score()

        return {
            "price": self.current_price(),

            "rsi": self.calculate_rsi(),

            "ema20": self.ema(20),
            "ema50": self.ema(50),
            "ema200": self.ema(200),

            "macd": macd_data["macd"],
            "macd_signal": macd_data["signal"],
            "macd_histogram": macd_data["histogram"],

            "atr": self.atr(),

            "adx": adx_data["adx"],
            "plus_di": adx_data["plus_di"],
            "minus_di": adx_data["minus_di"],

            "support": self.support(),
            "resistance": self.resistance(),

            "volume": volume_data["volume"],
            "average_volume": volume_data["average_volume"],
            "volume_ratio": volume_data["volume_ratio"],

            "52_week_high": yearly_data["52_week_high"],
            "52_week_low": yearly_data["52_week_low"],

            "trend": self.trend(),
            "momentum": self.momentum(),

            "technical_score": score,
        }


def analyze_stock(history: pd.DataFrame):
    """
    Public helper used by other X10 modules.
    """

    analyzer = TechnicalAnalyzer(history)
    return analyzer.calculate()
