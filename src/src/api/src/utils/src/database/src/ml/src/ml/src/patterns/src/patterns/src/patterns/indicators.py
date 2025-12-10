import numpy as np
from typing import List, Dict
from loguru import logger

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("TA library not available, using basic indicators")

class TechnicalIndicators:
    def __init__(self):
        self.indicators = {}
    
    def calculate_all(self, candles: List[Dict]) -> Dict:
        """Calculates a set of core indicators."""
        if len(candles) < 20:
            return {}
        
        # Prepare data (must be in reverse order for correct TA calculation)
        candles_rev = candles[::-1] 
        closes = np.array([c["close"] for c in candles_rev])
        highs = np.array([c["high"] for c in candles_rev])
        lows = np.array([c["low"] for c in candles_rev])
        
        result = {
            "rsi": self.calculate_rsi(closes),
            "sma_10": self.calculate_sma(closes, 10),
            "sma_20": self.calculate_sma(closes, 20),
            "ema_10": self.calculate_ema(closes, 10),
            "ema_20": self.calculate_ema(closes, 20),
            "macd": self.calculate_macd(closes),
            "bollinger": self.calculate_bollinger_bands(closes),
            "stochastic": self.calculate_stochastic(highs, lows, closes),
            "atr": self.calculate_atr(highs, lows, closes)
        }
        
        self.indicators = result
        return result
    
    def calculate_sma(self, closes: np.ndarray, period: int) -> Optional[float]:
        if len(closes) < period: return None
        return float(np.mean(closes[-period:]))

    def calculate_ema(self, closes: np.ndarray, period: int) -> Optional[float]:
        # Simple placeholder calculation for EMA
        if len(closes) < period: return None
        alpha = 2 / (period + 1)
        ema = closes[0]
        for close in closes[1:]:
            ema = alpha * close + (1 - alpha) * ema
        return float(ema)
        
    def calculate_rsi(self, closes: np.ndarray, period: int = 14) -> Dict:
        if not TA_AVAILABLE:
            return {"value": 50.0, "signal": "neutral"}
        
        # Calculate RSI using TA library
        rsi_series = ta.momentum.RSI(pd.Series(closes), window=period).rsi()
        rsi_value = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

        signal = "neutral"
        if rsi_value > 70: signal = "overbought"
        elif rsi_value < 30: signal = "oversold"
        
        return {"value": rsi_value, "signal": signal}

    def calculate_macd(self, closes: np.ndarray) -> Dict:
        if not TA_AVAILABLE:
            return {"trend": "neutral"}
            
        # Placeholder for MACD calculation logic
        return {"trend": "neutral", "histogram": 0.0}

    def calculate_bollinger_bands(self, closes: np.ndarray) -> Dict:
        if not TA_AVAILABLE:
            return {"position": "mid"}
            
        # Placeholder for Bollinger Bands calculation logic
        return {"position": "mid", "upper": 0.0, "lower": 0.0}

    def calculate_stochastic(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Dict:
        if not TA_AVAILABLE:
            return {"signal": "neutral"}
            
        # Placeholder for Stochastic Oscillator calculation logic
        return {"signal": "neutral", "k_value": 50.0, "d_value": 50.0}

    def calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Dict:
        if not TA_AVAILABLE:
            return {"value": 0.0}
            
        # Placeholder for ATR calculation logic
        return {"value": 0.00015, "volatility": "low"}
