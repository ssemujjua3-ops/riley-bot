import numpy as np
from typing import List, Dict, Optional, Tuple
from loguru import logger

class CandlestickAnalyzer:
    def __init__(self):
        self.pattern_names = [
            "doji", "hammer", "inverted_hammer", "shooting_star",
            "bullish_engulfing", "bearish_engulfing", "morning_star",
            "evening_star", "three_white_soldiers", "three_black_crows",
            "bullish_harami", "bearish_harami", "tweezer_top", "tweezer_bottom",
            "spinning_top", "marubozu_bullish", "marubozu_bearish"
        ]
    
    def analyze_candles(self, candles: List[Dict]) -> List[Dict]:
        """Analyzes recent candles for known candlestick patterns."""
        if len(candles) < 3:
            return []
        
        patterns_found = []
        
        # Analyze the 10 most recent candles for single/multi-candle patterns
        for i in range(len(candles) - 2):
            current = candles[i]
            prev = candles[i + 1] if i + 1 < len(candles) else None
            prev2 = candles[i + 2] if i + 2 < len(candles) else None
            
            detected = self._detect_patterns(current, prev, prev2)
            for pattern in detected:
                patterns_found.append({
                    "pattern": pattern["name"],
                    "type": pattern["type"],
                    "signal": pattern["signal"],
                    "strength": pattern["strength"],
                    "candle_index": i,
                    "timestamp": current.get("timestamp"),
                    "price": current.get("close")
                })
            
            if i >= 10: break # Limit check to recent 10 candles
            
        return patterns_found

    def _is_bullish(self, c: Dict) -> bool:
        return c["close"] > c["open"]

    def _is_bearish(self, c: Dict) -> bool:
        return c["close"] < c["open"]

    def _detect_patterns(self, current: Dict, prev: Optional[Dict], prev2: Optional[Dict]) -> List[Dict]:
        """Placeholder for individual pattern detection logic."""
        
        detected = []
        
        # Example: Bullish Engulfing
        if prev and self._is_bearish(prev) and self._is_bullish(current) and \
           current["close"] > prev["open"] and current["open"] < prev["close"]:
            detected.append({
                "name": "Bullish Engulfing",
                "type": "reversal",
                "signal": "CALL",
                "strength": 0.9
            })
            
        # Example: Doji
        body_size = abs(current["close"] - current["open"])
        range_size = current["high"] - current["low"]
        if body_size < 0.1 * range_size and range_size > 0.0001:
            detected.append({
                "name": "Doji",
                "type": "indecision",
                "signal": "neutral",
                "strength": 0.5
            })
            
        return detected

    def get_trend(self, candles: List[Dict], period: int = 50) -> str:
        """Determines the short-term trend based on recent closes."""
        if len(candles) < period:
            return "neutral"
            
        closes = [c["close"] for c in candles[:period]]
        
        # Check if the last close is significantly above/below a long-term moving average
        avg_price = np.mean(closes)
        current_price = closes[0]
        
        diff_pct = (current_price - avg_price) / avg_price * 100
        
        if diff_pct > 0.05:
            return "uptrend"
        elif diff_pct < -0.05:
            return "downtrend"
        return "neutral"
