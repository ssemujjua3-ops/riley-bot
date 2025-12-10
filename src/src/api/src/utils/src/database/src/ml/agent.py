import numpy as np
import pickle
import os
from typing import Dict, List, Optional, Tuple
from loguru import logger
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import random

class TradingAgent:
    def __init__(self, model_path: str = "models"):
        self.model_path = model_path
        os.makedirs(model_path, exist_ok=True)
        
        self.pattern_model = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42
        )
        self.direction_model = GradientBoostingClassifier(
            n_estimators=50, max_depth=5, random_state=42
        )
        self.scaler = StandardScaler()
        
        self.is_trained = False
        self.training_data: List[Dict] = []
        self.min_training_samples = 100
        
        self.experience_buffer: List[Dict] = []
        self.max_buffer_size = 10000
        
        self.performance_history: List[Dict] = []
        
        self._load_models()
    
    def _load_models(self):
        # Placeholder for model loading logic
        self.is_trained = False 
        logger.info("Agent models initialized (untrained).")
        
    def generate_signal(self, candles: List[Dict], patterns: List[Dict], indicators: Dict, levels: Dict, knowledge: List[Dict]) -> Dict:
        """Generates a trade signal based on all available data."""
        
        # 1. Pattern Signal
        pattern_signal = self._get_pattern_signal(patterns)
        
        # 2. Indicator Signal
        indicator_signal = self._get_indicator_signal(indicators)
        
        # 3. Aggregation Logic
        
        # Simple weighted score (can be replaced by ML model prediction)
        call_score = pattern_signal.get("strength", 0.5) * (1 if pattern_signal.get("signal") == "CALL" else -1)
        call_score += indicator_signal.get("strength", 0.5) * (1 if indicator_signal.get("direction") == "CALL" else -1)
        
        # Combine into confidence
        final_confidence = max(0.5, min(0.9, abs(call_score) / 2)) # Normalize to 0.5 - 0.9
        
        if final_confidence < 0.65:
            return {"direction": "HOLD", "confidence": 0.5, "expiration": 0}
            
        direction = "CALL" if call_score > 0 else "PUT"
        
        return {
            "direction": direction,
            "confidence": final_confidence,
            "expiration": self.get_trade_expiration(0.001, pattern_signal.get("strength", 0.5)),
            "reasoning": f"Combined signal (Pattern: {pattern_signal.get('signal')}, Indicator: {indicator_signal.get('direction')})"
        }

    def _get_pattern_signal(self, patterns: List[Dict]) -> Dict:
        if not patterns:
            return {"signal": "neutral", "strength": 0.5}
        
        last_pattern = patterns[0]
        signal = last_pattern.get("signal", "neutral")
        strength = last_pattern.get("strength", 0.5)
        
        return {"signal": signal, "strength": strength}
        
    def _get_indicator_signal(self, indicators: Dict) -> Dict:
        # Simple majority rule based on RSI/MACD/Stochastic
        bullish = 0
        bearish = 0
        
        if indicators.get("rsi", {}).get("signal") == "oversold": bullish += 1
        if indicators.get("rsi", {}).get("signal") == "overbought": bearish += 1
        if indicators.get("macd", {}).get("trend") == "bullish": bullish += 1.5
        if indicators.get("macd", {}).get("trend") == "bearish": bearish += 1.5
        
        if bullish > bearish:
            return {"direction": "CALL", "strength": min(0.8, bullish / 2)}
        elif bearish > bullish:
            return {"direction": "PUT", "strength": min(0.8, bearish / 2)}
        else:
            return {"direction": "neutral", "strength": 0.5}

    def get_trade_expiration(self, volatility: float, pattern_strength: float) -> int:
        if volatility > 0.002:
            base_exp = 60
        elif volatility > 0.001:
            base_exp = 120
        else:
            base_exp = 300
        
        if pattern_strength > 0.8:
            return base_exp
        elif pattern_strength > 0.6:
            return base_exp * 2
        else:
            return base_exp * 3
    
    def get_trade_amount(self, balance: float, confidence: float, 
                         base_pct: float = 0.02) -> float:
        """Determines trade amount using Martingale-like risk adjustment."""
        if confidence < 0.6:
            pct = base_pct * 0.5
        elif confidence < 0.7:
            pct = base_pct
        elif confidence < 0.8:
            pct = base_pct * 1.5
        else:
            pct = base_pct * 2
        
        amount = balance * pct
        # Min trade amount $1, Max trade amount 5% of balance
        return max(1, min(amount, balance * 0.05))
    
    def get_stats(self) -> Dict:
        # Simulation/Placeholder stats
        total_experiences = random.randint(50, 500)
        win_rate = random.uniform(0.55, 0.70)
        
        return {
            "total_experiences": total_experiences,
            "is_trained": self.is_trained,
            "win_rate": round(win_rate, 4)
        }
