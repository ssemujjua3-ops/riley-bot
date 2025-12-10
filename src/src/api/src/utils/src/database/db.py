import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

class Database:
    def __init__(self, db_path: str = "trading_bot.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def get_connection(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table for Market Data (Candles)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                timeframe INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset, timeframe, timestamp)
            )
        ''')
        
        # Table for Pattern Detections
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                asset TEXT NOT NULL,
                timeframe INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                signal TEXT,
                strength REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for S/R Levels
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                timeframe INTEGER NOT NULL,
                level_type TEXT NOT NULL,
                price REAL NOT NULL,
                strength REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table for Trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                asset TEXT NOT NULL,
                amount REAL NOT NULL,
                direction TEXT NOT NULL,
                expiration INTEGER NOT NULL,
                outcome TEXT,
                profit REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for Learned Knowledge (from PDFs/Web)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                relevance_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for ML Model State
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                model_data BLOB,
                metrics TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info("Database initialized.")

    def save_trade(self, asset: str, amount: float, direction: str, expiration: int, trade_id: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (trade_id, asset, amount, direction, expiration)
            VALUES (?, ?, ?, ?, ?)
        ''', (trade_id, asset, amount, direction, expiration))
        conn.commit()
        return cursor.lastrowid

    def update_trade_outcome(self, trade_id: str, outcome: str, profit: float):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trades SET outcome = ?, profit = ? WHERE trade_id = ?
        ''', (outcome, profit, trade_id))
        conn.commit()

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM trades ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    # ... other methods (save_candle, save_pattern, save_level, save_knowledge, etc.)

# Initialize the database instance
db = Database()
