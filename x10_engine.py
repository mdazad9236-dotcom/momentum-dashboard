class X10Engine:

    def calculate_score(self, analysis):

        score = 0

        # ======================================================
        # TREND
        # ======================================================

        trend = analysis.get("trend", "Neutral")

        if trend == "Strong Bullish":
            score += 20
        elif trend == "Bullish":
            score += 15
        elif trend == "Neutral":
            score += 7

        # ======================================================
        # MOMENTUM
        # ======================================================

        momentum = analysis.get(
            "momentum",
            "Neutral"
        )

        if momentum == "Positive":
            score += 15
        elif momentum == "Neutral":
            score += 7

        # ======================================================
        # RSI
        # ======================================================

        rsi = float(
            analysis.get("rsi", 50)
        )

        if 55 <= rsi <= 68:
            score += 15

        elif 50 <= rsi < 55:
            score += 10

        elif 68 < rsi <= 72:
            score += 8

        elif rsi > 75:
            score -= 5

        # ======================================================
        # MACD
        # ======================================================

        macd = float(
            analysis.get("macd", 0)
        )

        signal = float(
            analysis.get("macd_signal", 0)
        )

        histogram = float(
            analysis.get("macd_histogram", 0)
        )

        if macd > signal:
            score += 10

        if histogram > 0:
            score += 5

        # ======================================================
        # ADX
        # ======================================================

        adx = float(
            analysis.get("adx", 0)
        )

        plus_di = float(
            analysis.get("plus_di", 0)
        )

        minus_di = float(
            analysis.get("minus_di", 0)
        )

        if adx >= 25:
            score += 10

        elif adx >= 20:
            score += 5

        if plus_di > minus_di:
            score += 5

        # ======================================================
        # VOLUME
        # ======================================================

        volume_ratio = float(
            analysis.get(
                "volume_ratio",
                0
            )
        )

        if volume_ratio >= 1.5:
            score += 10

        elif volume_ratio >= 1.2:
            score += 5

        # ======================================================
        # FINAL SCORE
        # ======================================================

        score = max(
            0,
            min(
                int(score),
                100
            )
        )

        return score

    # ==========================================================
    # SIGNAL
    # ==========================================================

    def get_signal(self, score):

        if score >= 80:
            return "STRONG BUY"

        if score >= 70:
            return "BUY"

        if score >= 60:
            return "WATCH"

        if score >= 45:
            return "NEUTRAL"

        return "AVOID"

    # ==========================================================
    # ANALYZE
    # ==========================================================

    def analyze(self, analysis):

        score = self.calculate_score(
            analysis
        )

        signal = self.get_signal(
            score
        )

        return {
            "x10_score": score,
            "signal": signal
        }
