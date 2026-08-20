class X10Engine:
    """X10 scoring and actionable trade-plan engine."""

    def calculate_score(self, analysis):
        score = 0
        trend = analysis.get("trend", "Neutral")
        if trend == "Strong Bullish": score += 20
        elif trend == "Bullish": score += 15
        elif trend == "Neutral": score += 7

        momentum = analysis.get("momentum", "Neutral")
        if momentum == "Positive": score += 15
        elif momentum == "Neutral": score += 7

        rsi = float(analysis.get("rsi", 50) or 50)
        if 55 <= rsi <= 68: score += 15
        elif 50 <= rsi < 55: score += 10
        elif 68 < rsi <= 72: score += 8
        elif rsi > 75: score -= 5

        macd = float(analysis.get("macd", 0) or 0)
        signal = float(analysis.get("macd_signal", 0) or 0)
        histogram = float(analysis.get("macd_histogram", 0) or 0)
        if macd > signal: score += 10
        if histogram > 0: score += 5

        adx = float(analysis.get("adx", 0) or 0)
        plus_di = float(analysis.get("plus_di", 0) or 0)
        minus_di = float(analysis.get("minus_di", 0) or 0)
        if adx >= 25: score += 10
        elif adx >= 20: score += 5
        if plus_di > minus_di: score += 5

        volume_ratio = float(analysis.get("volume_ratio", 0) or 0)
        if volume_ratio >= 1.5: score += 10
        elif volume_ratio >= 1.2: score += 5
        return max(0, min(int(score), 100))

    def get_signal(self, score):
        if score >= 80: return "STRONG BUY"
        if score >= 70: return "BUY"
        if score >= 60: return "WATCH"
        if score >= 45: return "NEUTRAL"
        return "AVOID"

    @staticmethod
    def _round(value):
        return round(float(value), 2)

    @staticmethod
    def _format_risk_reward(value):
        """Return a trader-friendly ratio such as 1:2, 1:2.4 or 1:3."""
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            return "1:0"
        if ratio <= 0:
            return "1:0"
        rounded = round(ratio, 1)
        if rounded.is_integer():
            return f"1:{int(rounded)}"
        return f"1:{rounded:.1f}"

    def calculate_trade_plan(self, analysis):
        price = float(analysis.get("price", 0) or 0)
        support = float(analysis.get("support", 0) or 0)
        resistance = float(analysis.get("resistance", 0) or 0)
        atr = float(analysis.get("atr", 0) or 0)

        if price <= 0:
            return {"entry": 0, "entry_low": 0, "entry_high": 0,
                    "stop_loss": 0, "target": 0, "target_1": 0,
                    "target_2": 0, "risk": 0, "reward": 0,
                    "risk_reward": 0, "risk_reward_value": 0,
                    "risk_reward_display": "1:0",
                    "trailing_stop": 0, "chase_price": 0, "dont_chase": True,
                    "setup_quality": "INVALID"}

        if support > 0 and support < price:
            entry_low = max(support * 1.005, price - max(atr * 0.75, price * 0.01))
            entry_high = min(price, support * 1.025)
        else:
            entry_low = price - max(atr * 0.50, price * 0.01)
            entry_high = price

        if entry_low <= 0 or entry_low >= entry_high:
            entry_low = price * 0.98
            entry_high = price
        entry = entry_high

        atr_stop = price - (atr * 1.5) if atr > 0 else 0
        support_stop = support * 0.99 if support > 0 else 0
        possible_stops = [v for v in (atr_stop, support_stop) if 0 < v < entry]
        stop_loss = max(possible_stops) if possible_stops else entry * 0.97
        stop_loss = min(stop_loss, entry * 0.995)
        risk = entry - stop_loss

        target_1 = resistance if resistance > entry else entry + max(atr * 2.0, entry * 0.04)
        if target_1 <= entry:
            target_1 = entry + max(atr * 2.0, entry * 0.04)
        target_2 = max(entry + max(atr * 3.5, entry * 0.07), target_1 + max(atr, entry * 0.02))
        reward = target_1 - entry
        risk_reward_value = reward / risk if risk > 0 else 0
        risk_reward = self._format_risk_reward(risk_reward_value)

        chase_price = entry_high + max(atr * 0.50, price * 0.01)
        dont_chase = price > chase_price
        if risk_reward_value >= 2.0 and not dont_chase: setup_quality = "GOOD"
        elif risk_reward_value >= 1.5 and not dont_chase: setup_quality = "FAIR"
        else: setup_quality = "WEAK"

        return {
            "entry": self._round(entry),
            "entry_low": self._round(entry_low),
            "entry_high": self._round(entry_high),
            "stop_loss": self._round(stop_loss),
            "target": self._round(target_1),
            "target_1": self._round(target_1),
            "target_2": self._round(target_2),
            "risk": self._round(risk),
            "reward": self._round(reward),
            "risk_reward": self._round(risk_reward_value),
            "risk_reward_display": risk_reward,
            "risk_reward_value": self._round(risk_reward_value),
            "trailing_stop": self._round(max(entry, target_1 * 0.97)),
            "chase_price": self._round(chase_price),
            "dont_chase": dont_chase,
            "setup_quality": setup_quality
        }

    def analyze(self, analysis):
        score = self.calculate_score(analysis)
        signal = self.get_signal(score)
        plan = self.calculate_trade_plan(analysis)
        if plan["dont_chase"] and signal in ("STRONG BUY", "BUY"):
            signal = "WAIT / DON'T CHASE"
        return {
            "x10_score": score,
            "signal": signal,
            "entry": plan["entry"],
            "entry_low": plan["entry_low"],
            "entry_high": plan["entry_high"],
            "stop_loss": plan["stop_loss"],
            "target": plan["target"],
            "target_1": plan["target_1"],
            "target_2": plan["target_2"],
            "risk": plan["risk"],
            "reward": plan["reward"],
            "risk_reward": plan["risk_reward"],
            "risk_reward_display": plan["risk_reward_display"],
            "risk_reward_value": plan["risk_reward_value"],
            "trailing_stop": plan["trailing_stop"],
            "chase_price": plan["chase_price"],
            "dont_chase": plan["dont_chase"],
            "setup_quality": plan["setup_quality"]
        }
