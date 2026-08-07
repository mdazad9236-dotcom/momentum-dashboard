import pandas as pd

from ta.trend import EMAIndicator
from ta.trend import SMAIndicator
from ta.trend import MACD
from ta.trend import ADXIndicator

from ta.momentum import RSIIndicator

from ta.volatility import BollingerBands
from ta.volatility import AverageTrueRange

from ta.volume import VolumeWeightedAveragePrice


class TechnicalAnalyzer:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def calculate(self):

        df = self.df

        if len(df) < 200:
            raise Exception("Not enough historical data")

        # EMA
        df["EMA20"] = EMAIndicator(df["Close"], window=20).ema_indicator()
        df["EMA50"] = EMAIndicator(df["Close"], window=50).ema_indicator()
        df["EMA200"] = EMAIndicator(df["Close"], window=200).ema_indicator()

        # SMA
        df["SMA200"] = SMAIndicator(df["Close"], window=200).sma_indicator()

        # RSI
        df["RSI"] = RSIIndicator(df["Close"]).rsi()

        # MACD
        macd = MACD(df["Close"])

        df["MACD"] = macd.macd()
        df["MACD_SIGNAL"] = macd.macd_signal()
        df["MACD_DIFF"] = macd.macd_diff()

        # ADX
        adx = ADXIndicator(df["High"], df["Low"], df["Close"])

        df["ADX"] = adx.adx()

        # ATR
        atr = AverageTrueRange(
            df["High"],
            df["Low"],
            df["Close"]
        )

        df["ATR"] = atr.average_true_range()

        # Bollinger Bands
        bb = BollingerBands(df["Close"])

        df["BB_HIGH"] = bb.bollinger_hband()
        df["BB_LOW"] = bb.bollinger_lband()

        # VWAP
        vwap = VolumeWeightedAveragePrice(
            df["High"],
            df["Low"],
            df["Close"],
            df["Volume"]
        )

        df["VWAP"] = vwap.volume_weighted_average_price()

        latest = df.iloc[-1]

        return {

            "price": round(float(latest["Close"]),2),

            "ema20": round(float(latest["EMA20"]),2),

            "ema50": round(float(latest["EMA50"]),2),

            "ema200": round(float(latest["EMA200"]),2),

            "sma200": round(float(latest["SMA200"]),2),

            "rsi": round(float(latest["RSI"]),2),

            "macd": round(float(latest["MACD"]),2),

            "macd_signal": round(float(latest["MACD_SIGNAL"]),2),

            "macd_histogram": round(float(latest["MACD_DIFF"]),2),

            "adx": round(float(latest["ADX"]),2),

            "atr": round(float(latest["ATR"]),2),

            "vwap": round(float(latest["VWAP"]),2),

            "bb_upper": round(float(latest["BB_HIGH"]),2),

            "bb_lower": round(float(latest["BB_LOW"]),2),

            "support": round(float(df["Low"].tail(20).min()),2),

            "resistance": round(float(df["High"].tail(20).max()),2)
        }
