import numpy as np
from typing import List, Dict, Tuple
from loguru import logger
from collections import defaultdict

class LevelAnalyzer:
    def __init__(self, tolerance: float = 0.0005):
        self.tolerance = tolerance
        self.levels: Dict[str, List[Dict]] = defaultdict(list)
    
    def find_support_resistance(self, candles: List[Dict], 
                                 sensitivity: int = 3, count: int = 3) -> Dict[str, List[Dict]]:
        """Finds the strongest nearest Support and Resistance levels."""
        
        if len(candles) < sensitivity * 2:
            return {"support": [], "resistance": []}
        
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        current_price = candles[0]["close"]
        
        potential_levels = []
        
        # 1. Identify swing points (local highs/lows)
        for i in range(sensitivity, len(candles) - sensitivity):
            is_resistance = all(highs[i] >= highs[i-j] and highs[i] >= highs[i+j] 
                               for j in range(1, sensitivity + 1))
            if is_resistance:
                potential_levels.append({"price": highs[i], "type": "resistance", "index": i})
            
            is_support = all(lows[i] <= lows[i-j] and lows[i] <= lows[i+j] 
                            for j in range(1, sensitivity + 1))
            if is_support:
                potential_levels.append({"price": lows[i], "type": "support", "index": i})

        # 2. Merge nearby levels (Level Clustering)
        merged_levels = []
        potential_levels.sort(key=lambda x: x["price"])
        
        if potential_levels:
            current_cluster = [potential_levels[0]]
            for i in range(1, len(potential_levels)):
                prev_price = current_cluster[-1]["price"]
                current_price_level = potential_levels[i]["price"]
                
                # If current price is within tolerance of the previous one
                if abs(current_price_level - prev_price) < self.tolerance * current_price:
                    current_cluster.append(potential_levels[i])
                else:
                    # Finalize cluster
                    cluster_price = np.mean([c["price"] for c in current_cluster])
                    cluster_type = max(set(c["type"] for c in current_cluster), key=[c["type"] for c in current_cluster].count)
                    cluster_strength = len(current_cluster) / sensitivity # Simple strength metric
                    
                    merged_levels.append({
                        "price": cluster_price,
                        "type": cluster_type,
                        "touches": len(current_cluster),
                        "strength": min(1.0, cluster_strength)
                    })
                    current_cluster = [potential_levels[i]]

            # Finalize the last cluster
            if current_cluster:
                cluster_price = np.mean([c["price"] for c in current_cluster])
                cluster_type = max(set(c["type"] for c in current_cluster), key=[c["type"] for c in current_cluster].count)
                cluster_strength = len(current_cluster) / sensitivity
                
                merged_levels.append({
                    "price": cluster_price,
                    "type": cluster_type,
                    "touches": len(current_cluster),
                    "strength": min(1.0, cluster_strength)
                })

        # 3. Separate into Support/Resistance and find nearest
        nearest_support = []
        nearest_resistance = []

        for level in merged_levels:
            # Calculate distance from current price
            level["distance"] = abs(level["price"] - current_price)
            
            if level["type"] == "support" and level["price"] < current_price:
                nearest_support.append(level)
            elif level["type"] == "resistance" and level["price"] > current_price:
                nearest_resistance.append(level)
            # S/R flips logic can be added here (e.g., if price breaks a level)
                
        nearest_support.sort(key=lambda x: x["distance"])
        nearest_resistance.sort(key=lambda x: x["distance"])
        
        return {
            "support": nearest_support[:count],
            "resistance": nearest_resistance[:count]
        }
