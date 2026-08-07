import pandas as pd
import numpy as np


class TechnicalAnalyzer:

    def __init__(self, dataframe):
        self.df = dataframe.copy()

    # -----------------------------
    # EMA
    # -----------------------------
    def ema(self, period):
        return self.df["Close"].ewm(span=period, adjust=False).mean()

    # -----------------------------
    # SMA
    # -----------------------------
    def sma(self, period):
        return self.df["Close"].rolling(period).mean()

    # -----------------------------
    # RSI
    # -----------------------------
    def rsi(self, period=14):

        delta = self.df["Close"].diff()

        gain = delta.clip(lower=0)

        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(period).mean()

        avg_loss = loss.rolling(period).mean()

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))

        return rsi

    # -----------------------------
    # MACD
    # -----------------------------
    def macd(self):

        ema12 = self.ema(12)

        ema26 = self.ema(26)

        macd = ema12 - ema26

        signal = macd.ewm(span=9, adjust=False).mean()

        histogram = macd - signal

        return macd, signal, histogram

    # -----------------------------
    # Volume Average
    # -----------------------------
    def average_volume(self):

        return self.df["Volume"].rolling(20).mean()

    # -----------------------------
    # Support
    # -----------------------------
    def support(self):

        return float(self.df["Low"].tail(20).min())

    # -----------------------------
    # Resistance
    # -----------------------------
    def resistance(self):

        return float(self.df["High"].tail(20).max())

    # -----------------------------
    # Complete Analysis
    # -----------------------------
    def analyze(self):

        macd, signal, hist = self.macd()

        result = {

            "price": round(float(self.df["Close"].iloc[-1]),2),

            "ema20": round(float(self.ema(20).iloc[-1]),2),

            "ema50": round(float(self.ema(50).iloc[-1]),2),

            "ema200": round(float(self.ema(200).iloc[-1]),2),

            "sma200": round(float(self.sma(200).iloc[-1]),2),

            "rsi": round(float(self.rsi().iloc[-1]),2),

            "macd": round(float(macd.iloc[-1]),2),

            "signal": round(float(signal.iloc[-1]),2),

            "histogram": round(float(hist.iloc[-1]),2),

            "support": self.support(),

            "resistance": self.resistance(),

            "avg_volume": int(self.average_volume().iloc[-1])

        }

        return result
