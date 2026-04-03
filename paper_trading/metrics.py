from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Trading metrics
orders_placed_total = Counter('orders_placed_total', 'Total orders placed', ['symbol', 'side', 'status'])
orders_filled_total = Counter('orders_filled_total', 'Total orders filled', ['symbol', 'side'])
orders_failed_total = Counter('orders_failed_total', 'Total orders failed', ['symbol', 'reason'])

positions_open = Gauge('positions_open', 'Number of open positions', ['symbol'])
position_size = Gauge('position_size', 'Position size in contracts', ['symbol'])
position_pnl = Gauge('position_pnl', 'Unrealized P&L in USDT', ['symbol'])

daily_pnl = Gauge('daily_pnl_usdt', 'Daily P&L in USDT')
cumulative_pnl = Gauge('cumulative_pnl_usdt', 'Cumulative P&L in USDT')
total_trades = Gauge('total_trades', 'Total number of trades')
win_rate = Gauge('win_rate', 'Win rate percentage')
total_wins = Gauge('total_wins', 'Total winning trades')
total_losses = Gauge('total_losses', 'Total losing trades')

capital = Gauge('capital_usdt', 'Current capital in USDT')
available_capital = Gauge('available_capital_usdt', 'Available capital in USDT')

order_latency = Histogram('order_latency_seconds', 'Order execution latency', ['symbol', 'type'])

# Risk metrics
max_drawdown = Gauge('max_drawdown_pct', 'Maximum drawdown percentage')
sharpe_ratio = Gauge('sharpe_ratio', 'Sharpe ratio')
sortino_ratio = Gauge('sortino_ratio', 'Sortino ratio')
profit_factor = Gauge('profit_factor', 'Profit factor')
calmar_ratio = Gauge('calmar_ratio', 'Calmar ratio')
volatility = Gauge('volatility_pct', 'Volatility percentage')

def update_trading_metrics(pnl_summary: dict):
    """Update Prometheus metrics from PnL summary."""
    daily = pnl_summary.get('daily', {})
    metrics = pnl_summary.get('metrics', {})
    
    daily_pnl.set(daily.get('total_pnl', 0))
    cumulative_pnl.set(pnl_summary.get('cumulative', 0))
    total_trades.set(pnl_summary.get('trade_count', 0))
    win_rate.set(daily.get('win_rate', 0))
    total_wins.set(daily.get('win_count', 0))
    total_losses.set(daily.get('loss_count', 0))

    if 'sharpe_ratio' in metrics:
        sharpe_ratio.set(metrics.get('sharpe_ratio', 0))
    if 'sortino_ratio' in metrics:
        sortino_ratio.set(metrics.get('sortino_ratio', 0))
    if 'max_drawdown' in metrics:
        max_drawdown.set(metrics.get('max_drawdown', 0))
    if 'profit_factor' in metrics:
        profit_factor.set(metrics.get('profit_factor', 0))
    if 'calmar_ratio' in metrics:
        calmar_ratio.set(metrics.get('calmar_ratio', 0))
    if 'volatility' in metrics:
        volatility.set(metrics.get('volatility', 0))

def update_position_metrics(positions: dict):
    """Update position metrics."""
    for symbol, pos in positions.items():
        positions_open.labels(symbol=symbol).set(1 if pos.get('size', 0) != 0 else 0)
        position_size.labels(symbol=symbol).set(pos.get('size', 0))
        position_pnl.labels(symbol=symbol).set(pos.get('pnl', 0))

def update_capital_metrics(capital_val: float, available_val: float):
    """Update capital metrics."""
    capital.set(capital_val)
    available_capital.set(available_val)

def record_order_placed(symbol: str, side: str, status: str = 'submitted'):
    """Record order placed."""
    orders_placed_total.labels(symbol=symbol, side=side, status=status).inc()

def record_order_filled(symbol: str, side: str):
    """Record order filled."""
    orders_filled_total.labels(symbol=symbol, side=side).inc()

def record_order_failed(symbol: str, reason: str):
    """Record order failed."""
    orders_failed_total.labels(symbol=symbol, reason=reason).inc()
