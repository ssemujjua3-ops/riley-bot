import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger
import random # For trade simulation

from src.api.pocket_option import PocketOptionClient
from src.database.db import db
from src.patterns.candlestick import CandlestickAnalyzer
from src.patterns.levels import LevelAnalyzer
from src.patterns.indicators import TechnicalIndicators
from src.ml.agent import TradingAgent
from src.ml.knowledge_learner import KnowledgeLearner
from src.utils.tournament import TournamentManager 


class TradingBot:
    def __init__(self, ssid: str = None, demo: bool = True):
        self.client = PocketOptionClient(ssid=ssid, demo=demo)
        self.candlestick_analyzer = CandlestickAnalyzer()
        self.level_analyzer = LevelAnalyzer()
        self.indicators = TechnicalIndicators()
        self.agent = TradingAgent()
        self.knowledge_learner = KnowledgeLearner(db=db)
        
        # Initialize Tournament Manager
        self.tournament_manager = TournamentManager(self.client, self.agent, db=db)
        
        self.is_running = False
        self.is_learning = False
        self.is_trading = False
        
        self.current_asset = "EURUSD_otc"
        self.current_timeframe = 60
        self.available_timeframes = [60, 300, 900, 3600]
        
        self.market_data: Dict[str, Dict] = {}
        self.patterns_detected: List[Dict] = []
        self.levels_detected: Dict = {}
        self.indicator_values: Dict = {}
        
        self.trade_history: List[Dict] = []
        self.pending_trades: Dict = {}
        self.trades_this_hour = 0
        self.min_confidence = 0.75 
        self.loops: Dict[str, asyncio.Task] = {}
        
    def start(self, loop: asyncio.AbstractEventLoop):
        """Initializes and starts all background tasks."""
        if self.is_running:
            logger.warning("Bot is already running.")
            return

        self.is_running = True
        logger.info("Starting Trading Bot...")
        
        # 1. Start the main connection and data loops
        self.loops['main'] = loop.create_task(self._main_loop())
        
        # 2. Start the automated tournament loop
        self.loops['tournament'] = loop.create_task(self._tournament_loop())
        
        # 3. Start the trade execution loop
        self.loops['executor'] = loop.create_task(self._trade_executor_loop())
        
        # 4. Start the learning loop
        self.loops['learner'] = loop.create_task(self._knowledge_learner_loop())

    async def _main_loop(self):
        """Handles connection and market data subscription."""
        if not await self.client.connect():
            self.is_running = False
            logger.error("Connection failed. Bot stopping.")
            return
            
        logger.info("Starting market data feed...")
        # Simulating candle data feed subscription
        for asset in self.client.assets:
             self.loops[f'candles_{asset}'] = asyncio.get_event_loop().create_task(
                 self.client.subscribe_candles(asset, self.current_timeframe, self._on_new_candle)
             )
        
        while self.is_running:
            # Re-subscribe/Connection health check
            await asyncio.sleep(5) 

    async def _on_new_candle(self, candle: Dict):
        """Processes a new candle and generates a trade signal."""
        asset = candle["asset"]
        timeframe = candle["timeframe"]
        
        # 1. Update Market Data Store
        if asset not in self.market_data:
            self.market_data[asset] = {"candles": []}
        
        # Keep only the last 200 candles for analysis
        self.market_data[asset]["candles"].insert(0, candle)
        self.market_data[asset]["candles"] = self.market_data[asset]["candles"][:200]
        
        candles = self.market_data[asset]["candles"]
        if len(candles) < 20:
            return # Not enough data for analysis

        # 2. Run Technical Analysis
        self.patterns_detected = self.candlestick_analyzer.analyze_candles(candles)
        self.indicator_values = self.indicators.calculate_all(candles)
        self.levels_detected = self.level_analyzer.find_support_resistance(candles)
        
        # 3. Generate Trading Signal
        if self.is_trading:
            signal = self.agent.generate_signal(
                candles=candles,
                patterns=self.patterns_detected,
                indicators=self.indicator_values,
                levels=self.levels_detected,
                knowledge=self.knowledge_learner.get_relevant_knowledge("contextual data") # Placeholder context
            )
            
            if signal.get("direction") not in ["HOLD", "neutral"] and signal.get("confidence", 0) >= self.min_confidence:
                await self._execute_trade(asset, signal)
    
    async def _execute_trade(self, asset: str, signal: Dict):
        """Places a trade based on the validated signal."""
        direction = signal["direction"]
        confidence = signal["confidence"]
        expiration = signal.get("expiration", 60)
        
        # Use Martingale/Risk management logic from agent
        trade_amount = self.agent.get_trade_amount(self.client.balance, confidence)
        
        if trade_amount < 1:
            logger.warning(f"Trade amount too small ($ {trade_amount:.2f}). Skipping.")
            return
            
        logger.info(f"SIGNAL: {asset} - {direction} @ {expiration}s. Amount: ${trade_amount:.2f}. Confidence: {confidence:.2%}")
        
        trade_result = await self.client.place_trade(asset, trade_amount, direction, expiration)
        
        if trade_result and trade_result.get("trade_id"):
            self.pending_trades[trade_result["trade_id"]] = {
                "asset": asset,
                "amount": trade_amount,
                "direction": direction,
                "created_at": time.time(),
                "status": "pending"
            }
            db.save_trade(asset, trade_amount, direction, expiration, trade_id=trade_result["trade_id"])
            
    async def _resolve_trades(self):
        """Checks for expired trades and logs results."""
        resolved_ids = []
        for trade_id, trade in list(self.pending_trades.items()):
            # Real implementation would poll the Pocket Option API
            
            # Simulation: Resolve trades after a random delay
            if time.time() - trade["created_at"] > 5: 
                outcome = random.choice(["win", "loss"])
                profit = trade["amount"] * 0.85 if outcome == "win" else -trade["amount"]
                
                self.trade_history.append({**trade, "outcome": outcome, "profit": profit})
                self.client.balance += profit # Update balance in simulation
                db.update_trade_outcome(trade_id, outcome, profit)
                resolved_ids.append(trade_id)
                logger.info(f"TRADE RESOLVED: {trade['asset']} {trade['direction']} -> {outcome.upper()}. Profit: ${profit:.2f}")

        for trade_id in resolved_ids:
            del self.pending_trades[trade_id]
            
    async def _tournament_loop(self):
        """Runs periodically to check and join the daily free tournament."""
        await asyncio.sleep(30) # Initial wait for connection setup
        while self.is_running:
            try:
                # The manager handles the internal 4-hour frequency check
                await self.tournament_manager.join_daily_free_tournament() 
                
                # Check again in 1 hour
                await asyncio.sleep(3600) 
            except asyncio.CancelledError: 
                raise
            except Exception as e:
                logger.error(f"Tournament loop error: {e}")
                await asyncio.sleep(3600)
                
    async def _trade_executor_loop(self):
        """Handles trade execution and pending trade resolution."""
        while self.is_running:
            await self._resolve_trades()
            await asyncio.sleep(5) # Check resolution every 5 seconds

    async def _knowledge_learner_loop(self):
        """Handles data learning and model training."""
        while self.is_running:
            # Placeholder for continuous learning/retraining logic
            await asyncio.sleep(3600) 
            
    def stop(self):
        """Stops all background tasks."""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping Trading Bot...")
        
        for name, task in self.loops.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled {name} loop.")
        
        self.loops = {}
        
    def set_min_confidence(self, confidence: float):
        self.min_confidence = max(0.5, min(0.95, confidence))
        logger.info(f"Minimum confidence set to: {self.min_confidence:.2%}")
    
    # --- API GETTER METHODS ---
    def get_status(self) -> Dict:
        return {
            "is_running": self.is_running,
            "is_trading": self.is_trading,
            "is_learning": self.is_learning,
            "connected": self.client.is_connected(),
            "simulation_mode": self.client.is_simulation(),
            "balance": self.client.balance,
            "current_asset": self.current_asset,
            "current_timeframe": self.current_timeframe,
            "patterns_detected": len(self.patterns_detected),
            "trades_this_hour": self.trades_this_hour,
            "pending_trades": len(self.pending_trades),
            "total_trades": len(self.trade_history) + len(self.pending_trades),
            "agent_stats": self.agent.get_stats(),
            "knowledge_stats": self.knowledge_learner.get_stats()
        }
    
    def get_market_analysis(self) -> Dict:
        candles = self.market_data.get(self.current_asset, {}).get("candles", [])
        return {
            "patterns": self.patterns_detected[:10],
            "levels": self.levels_detected,
            "indicators": self.indicator_values,
            "trend": self.candlestick_analyzer.get_trend(candles),
            "candles": candles # Send candles for charting
        }
    
    def get_trade_stats(self) -> Dict:
        total_trades = len(self.trade_history)
        total_wins = sum(1 for t in self.trade_history if t.get("outcome") == "win")
        
        return {
            "total_trades": total_trades,
            "total_wins": total_wins,
            "total_losses": total_trades - total_wins,
            "recent_trades": self.trade_history[-10:],
            "win_rate": total_wins / total_trades if total_trades > 0 else 0,
            "pending_trades": len(self.pending_trades)
        }
