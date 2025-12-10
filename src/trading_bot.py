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
        }async def handle_candle(self, candle: Dict):
        """Processes a new candle and runs the trading logic."""
        asset = candle["asset"]
        timeframe = candle["timeframe"]
        
        # 1. Store the candle in market data (Most recent candle at index 0)
        if asset not in self.market_data:
            self.market_data[asset] = {"candles": []}
            
        self.market_data[asset]["candles"].insert(0, candle)
        self.market_data[asset]["candles"] = self.market_data[asset]["candles"][:200]
        
        # Only analyze the currently active asset/timeframe for web updates
        if asset == self.current_asset and timeframe == self.current_timeframe:
            candles_to_analyze = self.market_data[asset]["candles"]
            
            # 2. Run analysis modules
            self.patterns_detected = self.candlestick_analyzer.analyze_candles(candles_to_analyze)
            self.levels_detected = self.level_analyzer.find_support_resistance(candles_to_analyze)
            self.indicator_values = self.indicators.calculate_all(candles_to_analyze)
            
            # 3. Generate Trade Decision
            if self.is_trading and self.is_running:
                context = {
                    "asset": asset, "timeframe": timeframe, "patterns": self.patterns_detected,
                    "levels": self.levels_detected, "indicators": self.indicator_values,
                    "balance": self.client.balance
                }
                trade_suggestion = self.agent.get_trade_decision(context)
                
                direction = trade_suggestion.get("direction")
                confidence = trade_suggestion.get("confidence", 0)
                
                logger.info(f"Agent Suggestion: {direction} with {confidence:.2%} confidence.")
                
                # 4. Execute Trade if confident enough
                if direction in ("CALL", "PUT") and confidence >= self.min_confidence:
                    amount = self.agent.get_trade_amount(self.client.balance, confidence)
                    
                    # NOTE: This line needs the TournamentScheduler imported at the top of trading_bot.py
                    expiration = self.agent.determine_expiration(
                        self.indicator_values.get("atr", 0.0), 
                        self.candlestick_analyzer.get_pattern_strength(self.patterns_detected)
                    )
                    
                    logger.success(f"PLACING TRADE: {direction} {asset} for ${amount:.2f} @ {confidence:.2%} confidence. Exp: {expiration}s")
                    
                    trade_result = await self.client.place_trade(
                        asset=asset, 
                        direction=direction, 
                        amount=amount, 
                        duration=expiration
                    )
                    self.trades_this_hour += 1
                    self.trade_history.append({
                        "asset": asset, "direction": direction, "amount": amount, 
                        "confidence": confidence, "outcome": "PENDING"
                    })
                else:
                    logger.debug(f"Signal confidence {confidence:.2%} too low (Min: {self.min_confidence:.2%}) or direction is HOLD.")

    async def start(self):
        """Main asynchronous loop for the bot."""
        if self.is_running: return

        self.is_running = True
        logger.info("Bot is starting...")

        if not await self.client.connect():
            self.is_running = False
            logger.error("Failed to connect to Pocket Option Client. Stopping.")
            return

        logger.info(f"Connected. Running in {'DEMO' if self.client.is_simulation() else 'REAL'} mode. Balance: ${self.client.balance:.2f}")

        # Subscribe to market data for all available timeframes
        for tf in self.available_timeframes:
            await self.client.subscribe_candles(
                asset=self.current_asset, 
                timeframe=tf, 
                callback=self.handle_candle
            )
            logger.info(f"Subscribed to {self.current_asset} at {tf}s timeframe.")
            
        # Start tournament scheduler (optional)
        # NOTE: You need a basic TournamentScheduler class defined in your project
        # TournamentScheduler(self.tournament_manager).start_scheduler()

        # Keep the async thread alive and processing tasks
        while self.is_running:
            await asyncio.sleep(5) 

        logger.info("Bot main loop exited.")

    async def stop(self):
        """Stops the main bot loop and disconnects."""
        if not self.is_running: return

        self.is_running = False
        logger.info("Bot is stopping...")

        # Unsubscribe from all assets/timeframes
        for tf in self.available_timeframes:
            await self.client.unsubscribe_candles(asset=self.current_asset, timeframe=tf)
        
        await self.client.disconnect() 
        logger.info("Bot stopped and disconnected.")

    # Utility methods for the web interface
    def start_trading(self):
        self.is_trading = True
        logger.success("Trading is now ENABLED.")
        
    def stop_trading(self):
        self.is_trading = False
        logger.warning("Trading is now DISABLED.")

    def set_asset(self, asset: str):
        # NOTE: For a complete solution, you'd need to unsubscribe/re-subscribe, 
        # but this simple update allows the next candle to use the new asset.
        self.current_asset = asset
        logger.info(f"Active trading asset changed to: {asset}")

    def set_timeframe(self, timeframe: str):
        try:
            tf_int = int(timeframe)
            if tf_int in self.available_timeframes:
                self.current_timeframe = tf_int
                logger.info(f"Active analysis timeframe changed to: {tf_int}s")
        except ValueError:
            logger.error(f"Invalid timeframe value: {timeframe}")

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        # Simple history retrieval for the web UI
        return self.trade_history[-limit:][::-1]
