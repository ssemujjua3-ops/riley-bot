import os
import asyncio
import threading
from flask import Flask, jsonify, request, render_template
from loguru import logger

# Import your main classes
from src.trading_bot import TradingBot 
# Assuming db object is initialized in src.database.db.py
from src.database.db import db 


# --- INITIALIZATION ---
# Using the full path for file access
base_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
            static_folder=base_dir, 
            template_folder=base_dir)

# Read environment variables
BOT_SSID = os.getenv("POCKET_OPTION_SSID")

# Check if SSID is provided. If not, force demo mode.
BOT_DEMO = os.getenv("BOT_DEMO", "False").lower() == "true" if BOT_SSID else True
if BOT_SSID is None or BOT_SSID == "":
    logger.warning("POCKET_OPTION_SSID not set. Running in forced DEMO mode.")

# Initialize bot and asyncio loop
bot = TradingBot(ssid=BOT_SSID, demo=BOT_DEMO)
bot_loop = asyncio.new_event_loop()


# --- THREAD UTILITY ---
def run_coro_in_bot_loop(coro):
    """Safely runs an async coroutine in the bot's dedicated loop."""
    if threading.current_thread() is threading.main_thread():
        # Prevent deadlock if called from the main thread before loop starts
        if bot_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, bot_loop)
            try:
                # Wait for the result, with a timeout
                return future.result(timeout=10)
            except asyncio.TimeoutError:
                logger.error("Async task timed out.")
                return {"error": "Async operation timed out"}, 504
            except Exception as e:
                logger.error(f"Async operation failed: {e}")
                return {"error": str(e)}, 500
        else:
            logger.warning("Bot loop not running.")
            return {"error": "Bot not connected or running"}, 503
    else:
        # If called from a non-main thread (e.g., in a request context), 
        # but the request itself is not the event loop. This is a common Flask pattern.
        future = asyncio.run_coroutine_threadsafe(coro, bot_loop)
        try:
            return future.result(timeout=10)
        except Exception as e:
            logger.error(f"Async operation failed in request context: {e}")
            return {"error": str(e)}, 500


# --- ROUTES ---

@app.route('/')
def index():
    """Serves the dashboard HTML."""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns the current status of the bot."""
    return jsonify(bot.get_status())


@app.route('/api/control', methods=['POST'])
def bot_control():
    data = request.json
    action = data.get('action')
    
    if action == 'start':
        bot.start(bot_loop)
        return jsonify({"message": "Bot started. Connection sequence initiated."}), 200
    
    elif action == 'stop':
        bot.stop()
        return jsonify({"message": "Bot stopped."}), 200
        
    elif action == 'start_trading':
        bot.is_trading = True
        return jsonify({"message": "Trading loop activated."}), 200

    elif action == 'stop_trading':
        bot.is_trading = False
        return jsonify({"message": "Trading loop deactivated."}), 200
    
    elif action == 'join_tournament':
        tournament_id = data.get('id')
        if not tournament_id:
            return jsonify({"message": "Missing tournament ID"}), 400
            
        coro = bot.tournament_manager.join_tournament_by_id(tournament_id)
        result = run_coro_in_bot_loop(coro)
        
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]

        if result is True:
            return jsonify({"message": f"Successfully joined tournament ID: {tournament_id}"}), 200
        else:
            return jsonify({"message": f"Failed to join tournament ID: {tournament_id}. Check logs for details."}), 400

    else:
        return jsonify({"message": f"Unknown action: {action}"}), 400


@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.json
    setting = data.get('setting')
    value = data.get('value')

    if setting == 'min_confidence':
        bot.set_min_confidence(float(value))
        return jsonify({"message": f"Min confidence set to {value}"}), 200
    elif setting == 'current_asset':
        bot.current_asset = value
        return jsonify({"message": f"Asset set to {value}"}), 200
    elif setting == 'current_timeframe':
        bot.current_timeframe = int(value)
        return jsonify({"message": f"Timeframe set to {value}s"}), 200
    
    return jsonify({"message": f"Unknown setting: {setting}"}), 400


@app.route('/api/tournaments/free', methods=['GET'])
def get_free_tournaments():
    """Returns a list of all active free tournaments for the dashboard."""
    coro = bot.tournament_manager.get_all_active_free_tournaments()
    result = run_coro_in_bot_loop(coro)
    
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result), 200


@app.route('/api/market/analysis', methods=['GET'])
def get_market_analysis():
    """Returns the current market analysis (patterns, levels, etc.)."""
    return jsonify(bot.get_market_analysis())


@app.route('/api/trades/history', methods=['GET'])
def get_trade_stats():
    """Returns trade history and statistics."""
    # Note: In a real app, this should pull from the DB for persistence.
    return jsonify(bot.get_trade_stats())


if __name__ == '__main__':
    # Start the asyncio loop in a separate thread for the bot logic
    threading.Thread(target=bot_loop.run_forever, daemon=True).start()

    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
