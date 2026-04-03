"""
Web Dashboard for Paper Trading
Layer 7: Command & Control - Web Interface
"""

import os
import sys
import time as time_module
import secrets
from pathlib import Path
from threading import Thread
from collections import deque
from flask import Flask, render_template, jsonify, request, Response
from functools import wraps
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.engine import PaperTradingEngine
from paper_trading.metrics import generate_latest, CONTENT_TYPE_LATEST


class HistoricalDataTracker:
    def __init__(self, max_points=300):
        self.max_points = max_points
        self.price_history = {s: deque(maxlen=max_points) for s in ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT']}
        self.pnl_history = deque(maxlen=max_points)
        self.strategy_performance = {}
    
    def record_price(self, symbol, price, timestamp=None):
        if timestamp is None:
            timestamp = time_module.time()
        if symbol in self.price_history:
            self.price_history[symbol].append({'timestamp': timestamp, 'price': price})
    
    def record_pnl(self, capital, daily_pnl, timestamp=None):
        if timestamp is None:
            timestamp = time_module.time()
        self.pnl_history.append({'timestamp': timestamp, 'capital': capital, 'daily_pnl': daily_pnl})
    
    def record_strategy(self, strategy_name, pnl, timestamp=None):
        if timestamp is None:
            timestamp = time_module.time()
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = deque(maxlen=100)
        self.strategy_performance[strategy_name].append({'timestamp': timestamp, 'pnl': pnl})
    
    def get_price_history(self):
        return {s: list(h) for s, h in self.price_history.items()}
    
    def get_pnl_history(self):
        return list(self.pnl_history)
    
    def get_strategy_performance(self):
        result = {}
        for strategy, history in self.strategy_performance.items():
            entries = list(history)
            result[strategy] = {'total_pnl': sum(e['pnl'] for e in entries), 'trade_count': len(entries)}
        return result

data_tracker = HistoricalDataTracker(max_points=300)

# Authentication configuration
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "nwa45690")

def check_auth(username, password):
    return username == 'admin' and password == DASHBOARD_PASSWORD

def authenticate():
    return Response(
        'Authentication required', 401,
        {'WWW-Authenticate': 'Basic realm="Paper Trading Dashboard"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)

engine: PaperTradingEngine = None
refresh_interval = 1


def create_app(trading_engine: PaperTradingEngine = None) -> Flask:
    """Create and configure Flask app."""
    global engine
    
    if trading_engine:
        engine = trading_engine
    
    return app


@app.route('/')
@requires_auth
def index():
    """Main dashboard page."""
    config = {}
    if engine:
        config = engine.config
    
    return render_template('index.html', config=config)


@app.route('/api/status')
@requires_auth
def api_status():
    """Get system status."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    status = engine.get_status()
    
    # Record price data for charts
    prices = status.get('prices', {})
    for symbol, price in prices.items():
        if symbol in data_tracker.price_history:
            data_tracker.record_price(symbol, price)
    
    # Record P&L data for charts
    data_tracker.record_pnl(
        capital=status.get('capital', 0),
        daily_pnl=status.get('daily_pnl', 0)
    )
    
    # Record strategy performance
    active_strategy = status.get('active_strategy')
    if active_strategy:
        data_tracker.record_strategy(active_strategy, status.get('daily_pnl', 0))
    
    return jsonify(status)


@app.route('/api/positions')
@requires_auth
def api_positions():
    """Get open positions."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    positions = engine.get_positions()
    return jsonify(positions)


@app.route('/api/pnl')
@requires_auth
def api_pnl():
    """Get P&L data."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    status = engine.get_status()
    return jsonify({
        'daily_pnl': status.get('daily_pnl', 0),
        'capital': status.get('capital', 0),
        'leverage': status.get('leverage', 1)
    })


@app.route('/api/pnl/summary')
@requires_auth
def api_pnl_summary():
    """Get comprehensive PnL summary from TradeLogger."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    summary = engine.get_pnl_summary()
    return jsonify(summary)


@app.route('/api/trades')
@requires_auth
def api_trades():
    """Get recent trades from TradeLogger."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    try:
        if hasattr(engine.order_manager, 'trade_logger'):
            limit = request.args.get('limit', 50, type=int)
            trades = engine.order_manager.trade_logger.get_recent_trades(limit=limit)
            return jsonify({'trades': trades})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'trades': []})


@app.route('/api/health')
@requires_auth
def api_health():
    """Get health report from engine's actual health monitor."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    report = engine.health_monitor.get_health_report()
    return jsonify(report)


@app.route('/api/regime')
@requires_auth
def api_regime():
    """Get current market regime."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    status = engine.get_status()
    return jsonify({
        'regime': status.get('current_regime', 'unknown'),
        'strategy': status.get('active_strategy', 'unknown')
    })


@app.route('/api/start', methods=['POST'])
@requires_auth
def api_start():
    """Start trading."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    if not engine.running:
        engine.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})


@app.route('/api/stop', methods=['POST'])
@requires_auth
def api_stop():
    """Stop trading."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    if engine.running:
        engine.stop()
        return jsonify({'status': 'stopped'})
    return jsonify({'status': 'already_stopped'})


@app.route('/api/emergency', methods=['POST'])
@requires_auth
def api_emergency():
    """Emergency stop."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    engine.emergency_stop()
    return jsonify({'status': 'emergency_stop'})


@app.route('/api/order/long', methods=['POST'])
@requires_auth
def api_order_long():
    """Open a long position."""
    from loguru import logger
    
    data = request.get_json() or {}
    symbol = data.get('symbol', 'BTCUSDT')
    size = data.get('size')
    
    try:
        price = 0
        try:
            from vnpy_engine.vnpy_local.shared_state import SharedState
            ss = SharedState()
            price_data = ss.get_position(f"{symbol}_price")
            if price_data:
                price = price_data.get('price', 0)
                logger.info(f"[API order_long] Price from shared_state: {price}")
        except Exception as e:
            logger.error(f"shared_state error: {e}")
        
        if price <= 0:
            return jsonify({'error': f'Could not get price for {symbol}'}), 500
        
        if not engine:
            return jsonify({'error': 'Engine not available'}), 500
        
        if size is None:
            size = engine._calculate_position_size(symbol)
        
        # Cap position size for testnet to avoid insufficient margin
        if engine.order_manager.mode == 'testnet' and engine.order_manager.testnet_client:
            try:
                account = engine.order_manager.testnet_client.get_account()
                wallet = float(account.get('totalWalletBalance', 0))
                leverage = engine.leverage
                max_dollar_pos = wallet * leverage
                max_size = max_dollar_pos / price
                if size > max_size:
                    logger.warning(f"[API order_long] Size {size:.4f} exceeds max {max_size:.4f}, capping")
                    size = max_size * 0.95  # 5% buffer
            except Exception as e:
                logger.error(f"Could not check wallet: {e}")
        
        logger.info(f"[API order_long] Price: {price}, size: {size}, mode: {engine.order_manager.mode}")
        
        order = engine.order_manager.execute(
            signal='buy',
            symbol=symbol,
            price=price,
            size=size,
            leverage=engine.leverage
        )
        
        logger.info(f"[API order_long] Order result: {order}, status: {order.status if order else 'None'}")
        
        if order:
            return jsonify({
                'status': 'filled',
                'order_id': order.order_id,
                'symbol': symbol,
                'side': 'long',
                'size': order.filled_size,
                'price': order.avg_fill_price
            })
        return jsonify({'error': 'Order failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/order/short', methods=['POST'])
@requires_auth
def api_order_short():
    """Open a short position."""
    from loguru import logger
    
    data = request.get_json() or {}
    symbol = data.get('symbol', 'BTCUSDT')
    size = data.get('size')
    
    try:
        price = 0
        try:
            from vnpy_engine.vnpy_local.shared_state import SharedState
            ss = SharedState()
            price_data = ss.get_position(f"{symbol}_price")
            if price_data:
                price = price_data.get('price', 0)
        except:
            pass
        
        if price <= 0:
            return jsonify({'error': f'Could not get price for {symbol}'}), 500
        
        if not engine:
            return jsonify({'error': 'Engine not available'}), 500
        
        if size is None:
            size = engine._calculate_position_size(symbol)
        
        if engine.order_manager.mode == 'testnet' and engine.order_manager.testnet_client:
            try:
                account = engine.order_manager.testnet_client.get_account()
                wallet = float(account.get('totalWalletBalance', 0))
                leverage = engine.leverage
                max_dollar_pos = wallet * leverage
                max_size = max_dollar_pos / price
                if size > max_size:
                    size = max_size * 0.95
            except:
                pass
        
        order = engine.order_manager.execute(
            signal='sell',
            symbol=symbol,
            price=price,
            size=size,
            leverage=engine.leverage
        )
        
        if order:
            return jsonify({
                'status': 'filled',
                'order_id': order.order_id,
                'symbol': symbol,
                'side': 'short',
                'size': order.filled_size,
                'price': order.avg_fill_price
            })
        return jsonify({'error': 'Order failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/order/close', methods=['POST'])
@requires_auth
def api_order_close():
    """Close a position."""
    data = request.get_json() or {}
    symbol = data.get('symbol', 'BTCUSDT')
    
    try:
        price = 0
        try:
            from vnpy_engine.vnpy_local.shared_state import SharedState
            ss = SharedState()
            price_data = ss.get_position(f"{symbol}_price")
            if price_data:
                price = price_data.get('price', 0)
        except:
            pass
        
        if not engine:
            return jsonify({'error': 'Engine not available'}), 500
        
        order = engine.order_manager.execute(
            signal='close',
            symbol=symbol,
            price=price or 0,
            size=None,
            leverage=engine.leverage
        )
        
        if order:
            return jsonify({
                'status': 'closed',
                'order_id': order.order_id,
                'symbol': symbol,
                'size': order.filled_size,
                'price': order.avg_fill_price,
                'pnl': order.pnl
            })
        return jsonify({'error': 'No position to close'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/switch_strategy', methods=['POST'])
@requires_auth
def api_switch_strategy():
    """Switch strategy."""
    if engine is None:
        return jsonify({'error': 'Engine not initialized'}), 500
    
    data = request.get_json()
    strategy_name = data.get('strategy')
    
    if engine.switch_strategy(strategy_name):
        return jsonify({'status': 'switched', 'strategy': strategy_name})
    
    return jsonify({'error': 'Strategy not found'}), 400



@app.route('/api/prices/history')
@requires_auth
def api_prices_history():
    return jsonify(data_tracker.get_price_history())

@app.route('/api/pnl/history')
@requires_auth
def api_pnl_history():
    return jsonify(data_tracker.get_pnl_history())

@app.route('/api/strategies/performance')
@requires_auth
def api_strategies_performance():
    return jsonify(data_tracker.get_strategy_performance())

@app.route('/api/record/price', methods=['POST'])
@requires_auth
def api_record_price():
    data = request.get_json()
    if data.get('symbol') and data.get('price'):
        data_tracker.record_price(data['symbol'], data['price'])
    return jsonify({'status': 'recorded'})

@app.route('/api/record/pnl', methods=['POST'])
@requires_auth
def api_record_pnl():
    data = request.get_json()
    data_tracker.record_pnl(data.get('capital', 0), data.get('daily_pnl', 0))
    return jsonify({'status': 'recorded'})

@app.route('/api/record/strategy', methods=['POST'])
@requires_auth
def api_record_strategy():
    data = request.get_json()
    if data.get('strategy'):
        data_tracker.record_strategy(data['strategy'], data.get('pnl', 0))
    return jsonify({'status': 'recorded'})

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


def run_dashboard(host: str = '0.0.0.0', port: int = 8080, 
                trading_engine: PaperTradingEngine = None):
    """Run the dashboard server."""
    global engine
    
    if trading_engine:
        engine = trading_engine
    
    logger.info(f"Starting dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


def start_dashboard_thread(host: str = '0.0.0.0', port: int = 8080,
                          trading_engine: PaperTradingEngine = None):
    """Start dashboard in background thread."""
    thread = Thread(target=run_dashboard, 
                   args=(host, port, trading_engine),
                   daemon=True)
    thread.start()
    return thread


if __name__ == '__main__':
    print("=" * 50)
    print("Paper Trading Dashboard")
    print("=" * 50)
    print("\nStarting engine and dashboard...\n")
    
    try:
        engine = PaperTradingEngine()
        engine.start()
        
        run_dashboard('0.0.0.0', 8080, engine)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        if engine:
            engine.stop()
