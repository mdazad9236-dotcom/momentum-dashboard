import pandas as pd
import numpy as np


class TechnicalAnalyzer:

    def __init__(self, history: pd.DataFrame):
        self.df = history.copy()

    # ----------------------------
    # RSI
    # ----------------------------
    def calculate_rsi(self, period=14):

        delta = self.df["Close"].diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))

        return round(float(rsi.iloc[-1]), 2)

    # ----------------------------
    # EMA
    # ----------------------------
    def ema(self, period):

        return round(
            float(
                self.df["Close"]
                .ewm(span=period, adjust=False)
                .mean()
                .iloc[-1]
            ),
            2
        )

    # ----------------------------
    # MACD
    # ----------------------------
    def macd(self):

        ema12 = self.df["Close"].ewm(span=12).mean()

        ema26 = self.df["Close"].ewm(span=26).mean()

        macd = ema12 - ema26

        signal = macd.ewm(span=9).mean()

        histogram = macd - signal

        return {
            "macd": round(float(macd.iloc[-1]), 2),
            "signal": round(float(signal.iloc[-1]), 2),
            "histogram": round(float(histogram.iloc[-1]), 2)
        }

    # ----------------------------
    # ATR
    # ----------------------------
    def atr(self, period=14):

        high = self.df["High"]

        low = self.df["Low"]

        close = self.df["Close"]

        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()

        return round(float(atr.iloc[-1]), 2)

    # ----------------------------
    # ADX
    # ----------------------------
    def adx(self, period=14):

        high = self.df["High"]

        low = self.df["Low"]

        close = self.df["Close"]

        plus_dm = high.diff()

        minus_dm = low.diff().abs()

        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()

        plus_di = 100 * (
            plus_dm.rolling(period).mean() / atr
        )

        minus_di = 100 * (
            minus_dm.rolling(period).mean() / atr
        )

        dx = (
            abs(plus_di - minus_di)
            /
            (plus_di + minus_di)
        ) * 100

        adx = dx.rolling(period).mean()

        return round(float(adx.iloc[-1]), 2)

    # ----------------------------
    # Support
    # ----------------------------
    def support(self):

        return round(
            float(
                self.df["Low"]
                .tail(20)
                .min()
            ),
            2
        )

    # ----------------------------
    # Resistance
    # ----------------------------
    def resistance(self):

        return round(
            float(
                self.df["High"]
                .tail(20)
                .max()
            ),
            2
        )

    # ----------------------------
    # Overall Score
    # ----------------------------
    def score(self):

        score = 0

        rsi = self.calculate_rsi()

        ema20 = self.ema(20)

        ema50 = self.ema(50)

        price = float(self.df["Close"].iloc[-1])

        if price > ema20:
            score += 1

        if ema20 > ema50:
            score += 1

        if 50 <= rsi <= 70:
            score += 1

        if score == 3:
            return "Strong Buy"

        elif score == 2:
            return "Buy"

        elif score == 1:
            return "Neutral"

        return "Sell"

    # ----------------------------
    # Final Output
    # ----------------------------
    def calculate(self):

        macd = self.macd()

        return {

            "price": round(
                float(self.df["Close"].iloc[-1]),
                2
            ),

            "rsi": self.calculate_rsi(),

            "ema20": self.ema(20),

            "ema50": self.ema(50),

            "ema200": self.ema(200),

            "macd": macd["macd"],

            "signal": macd["signal"],

            "histogram": macd["histogram"],

            "atr": self.atr(),

            "adx": self.adx(),

            "support": self.support(),

            "resistance": self.resistance(),

            "recommendation": self.score()
        }
