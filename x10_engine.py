class X10Engine:

    # ==========================================================
    # X10 SCORE
    # ==========================================================

    def calculate_score(self, analysis):

        score = 0

        # ------------------------------------------------------
        # TREND
        # ------------------------------------------------------

        trend = analysis.get("trend", "Neutral")

        if trend == "Strong Bullish":
            score += 20
        elif trend == "Bullish":
            score += 15
        elif trend == "Neutral":
            score += 7

        # ------------------------------------------------------
        # MOMENTUM
        # ------------------------------------------------------

        momentum = analysis.get(
            "momentum",
            "Neutral"
        )

        if momentum == "Positive":
            score += 15
        elif momentum == "Neutral":
            score += 7

        # ------------------------------------------------------
        # RSI
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # MACD
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # ADX
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # VOLUME
        # ------------------------------------------------------

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
    # TRADE PLAN
    # ==========================================================

    def calculate_trade_plan(self, analysis):

        price = float(
            analysis.get("price", 0)
        )

        support = float(
            analysis.get("support", 0)
        )

        resistance = float(
            analysis.get("resistance", 0)
        )

        atr = float(
            analysis.get("atr", 0)
        )

        if price <= 0:
            return {
                "entry": 0,
                "stop_loss": 0,
                "target": 0,
                "risk": 0,
                "reward": 0,
                "risk_reward": 0
            }

        # ------------------------------------------------------
        # ENTRY
        # ------------------------------------------------------

        entry = price

        # ------------------------------------------------------
        # STOP LOSS
        # ------------------------------------------------------

        atr_stop = price - (
            atr * 1.5
        )

        support_stop = support * 0.99

        possible_stops = [
            value
            for value in [
                atr_stop,
                support_stop
            ]
            if value > 0
        ]

        if possible_stops:

            stop_loss = max(
                possible_stops
            )

        else:

            stop_loss = price * 0.97

        # Make sure stop remains below entry.

        if stop_loss >= entry:
            stop_loss = entry * 0.97

        # ------------------------------------------------------
        # TARGET
        # ------------------------------------------------------

        atr_target = entry + (
            atr * 3
        )

        if resistance > entry:

            target = max(
                atr_target,
                resistance
            )

        else:

            target = atr_target

        # ------------------------------------------------------
        # RISK / REWARD
        # ------------------------------------------------------

        risk = entry - stop_loss

        reward = target - entry

        if risk > 0:

            risk_reward = (
                reward / risk
            )

        else:

            risk_reward = 0

        return {
            "entry": round(
                entry,
                2
            ),

            "stop_loss": round(
                stop_loss,
                2
            ),

            "target": round(
                target,
                2
            ),

            "risk": round(
                risk,
                2
            ),

            "reward": round(
                reward,
                2
            ),

            "risk_reward": round(
                risk_reward,
                2
            )
        }

    # ==========================================================
    # FINAL ANALYSIS
    # ==========================================================

    def analyze(self, analysis):

        score = self.calculate_score(
            analysis
        )

        signal = self.get_signal(
            score
        )

        trade_plan = self.calculate_trade_plan(
            analysis
        )

        return {

            "x10_score": score,

            "signal": signal,

            "entry": trade_plan["entry"],

            "stop_loss": trade_plan["stop_loss"],

            "target": trade_plan["target"],

            "risk": trade_plan["risk"],

            "reward": trade_plan["reward"],

            "risk_reward": trade_plan["risk_reward"]
        }
