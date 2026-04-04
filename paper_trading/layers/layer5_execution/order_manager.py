"""
Layer 5: Order Manager
Handles order placement, tracking, and execution.
Supports paper (simulated) and testnet (Binance testnet) modes.
"""

import os
import random
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from enum import Enum
from loguru import logger

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), '.env'))
except ImportError:
    pass


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class Order:
    """Order representation."""
    
    def __init__(self, order_id: str, symbol: str, side: str, order_type: OrderType,
                 size: float, price: Optional[float] = None, leverage: Optional[int] = 1):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.size = size
        self.price = price
        self.leverage = leverage
        
        self.status = OrderStatus.PENDING
        self.filled_size = 0
        self.avg_fill_price = 0
        
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        
        self.pnl = 0.0
    
    def fill(self, fill_price: float, fill_size: float):
        """Fill order."""
        self.filled_size += fill_size
        
        if self.avg_fill_price == 0:
            self.avg_fill_price = fill_price
        else:
            self.avg_fill_price = (self.avg_fill_price * (self.filled_size - fill_size) + 
                                   fill_price * fill_size) / self.filled_size
        
        self.updated_at = datetime.now().isoformat()
        
        if self.filled_size >= self.size:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIAL
    
    def cancel(self):
        """Cancel order."""
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.now().isoformat()
    
    def reject(self, reason: str = ""):
        """Reject order."""
        self.status = OrderStatus.REJECTED
        self.updated_at = datetime.now().isoformat()
        logger.warning("Order rejected")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type.value,
            'size': self.size,
            'price': self.price,
            'leverage': self.leverage,
            'status': self.status.value,
            'filled_size': self.filled_size,
            'avg_fill_price': self.avg_fill_price,
            'created_at': self.created_at,
            'pnl': self.pnl
        }


class OrderManager:
    """Manages orders and positions. Thread-safe."""
    
    def __init__(self, config: Dict[str, Any]):
        self._lock = threading.RLock()
        
        self.leverage = config.get('leverage', 75)
        self.mode = config.get('mode', 'paper')
        
        self.slippage_pct = config.get('slippage_pct', 0.001)
        self.fee_pct = config.get('fee_pct', 0.0004)
        self.fill_delay = config.get('fill_delay', 0.0)
        
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Dict[str, Any]] = {}
        
        self.order_counter = 0
        self.total_fees = 0.0
        
        self.order_callbacks: List[Callable[[Order], None]] = []
        
        self.testnet_client = None
        if self.mode == 'testnet':
            self._init_testnet_client()
        
        # Black Swan Phase 3: Slippage Feedback Loop
        self.slippage_history: List[Dict[str, Any]] = []
        self.max_slippage_history = 100
        self.predicted_slippage_pct = self.slippage_pct
        self.slippage_error_tolerance = 0.002
        self.slippage_penalty_factor = 1.5
        
        from .trade_logger import get_trade_logger
        self.trade_logger = get_trade_logger()
    
    def _init_testnet_client(self):
        """Initialize Binance testnet client."""
        try:
            from .binance_testnet_client import BinanceTestnetClient
            import concurrent.futures
            
            api_key = os.getenv('BINANCE_API_KEY', '')
            secret_key = os.getenv('BINANCE_SECRET_KEY', '')
            
            if not api_key or not secret_key:
                logger.error("BINANCE_API_KEY or BINANCE_SECRET_KEY not set, falling back to paper mode")
                self.mode = 'paper'
                return
            
            self.testnet_client = BinanceTestnetClient(api_key, secret_key)
            
            symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
            
            def set_leverage_for_symbol(symbol):
                try:
                    self.testnet_client.set_leverage(symbol, self.leverage)
                    logger.info(f"Set {symbol} leverage to {self.leverage}x on testnet")
                except Exception as e:
                    logger.debug(f"Leverage set note for {symbol}: {e}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                executor.map(set_leverage_for_symbol, symbols)
            
            account = self.testnet_client.get_account()
            wallet = float(account.get('totalWalletBalance', 0))
            logger.info(f"Testnet mode active. Wallet: ${wallet:,.2f}")
            
        except Exception as e:
            logger.error("Failed to initialize testnet client - falling back to paper mode")
            self.mode = 'paper'
            self.testnet_client = None
    
    def _wait_for_order_fill(self, symbol: str, order_id: str, timeout: int = 10) -> dict:
        """Poll order until filled, return final status with avgPrice/executedQty"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                status = self.testnet_client._get(
                    '/fapi/v1/order',
                    params={'symbol': symbol.upper(), 'orderId': order_id},
                    signed=True
                )
                
                status_val = status.get('status', '')
                
                if status_val == 'FILLED':
                    logger.info(f"Order {order_id} filled")
                    return status
                elif status_val == 'PARTIALLY_FILLED':
                    logger.info(f"Order {order_id} partially filled")
                    return status
                elif status_val in ('CANCELED', 'EXPIRED', 'REJECTED'):
                    raise RuntimeError(f"Order failed: {status_val}")
                    
            except Exception as e:
                logger.warning(f"Order status poll error: {e}")
                
            time.sleep(0.5)
        
        raise RuntimeError(f"Order fill timeout after {timeout}s")
    
    def execute(self, signal: str, symbol: str, price: float, 
                size: float, leverage: Optional[int] = None) -> Optional[Order]:
        """Execute an order."""
        leverage = leverage or self.leverage
        
        if signal == 'buy':
            return self._open_long(symbol, price, size, leverage)
        elif signal == 'sell':
            return self._open_short(symbol, price, size, leverage)
        elif signal == 'close':
            return self._close_position(symbol, price, size)
        
        return None
    
    def _apply_slippage(self, price: float, side: str) -> float:
        """Apply simulated slippage to fill price."""
        slippage = price * self.slippage_pct * random.uniform(0.5, 1.5)
        if side in ('buy', 'long'):
            return price + slippage
        else:
            return price - slippage
    
    def _apply_fees(self, amount: float) -> float:
        """Calculate and track trading fees."""
        fee = amount * self.fee_pct
        self.total_fees += fee
        return fee
    
    def _open_long(self, symbol: str, price: float, size: float, 
                   leverage: Optional[int]) -> Order:
        """Open long position."""
        order_id = self._generate_order_id()
        
        order = Order(order_id, symbol, 'buy', OrderType.MARKET, size, price, leverage)
        self.orders[order_id] = order
        
        if self.mode == 'testnet' and self.testnet_client:
            try:
                result = self.testnet_client.place_market_order(
                    symbol=symbol,
                    side='BUY',
                    quantity=size,
                )
                
                order_id = result.get('orderId')
                if order_id:
                    result = self._wait_for_order_fill(symbol, str(order_id))
                
                order_status = result.get('status', '')
                
                fill_price_raw = result.get('avgPrice')
                fill_price = float(fill_price_raw) if fill_price_raw and fill_price_raw != '0.00' else float(price)
                filled_qty_raw = result.get('executedQty')
                filled_qty = float(filled_qty_raw) if filled_qty_raw and filled_qty_raw != '0.0000' else float(size)
                
                if order_status == 'REJECTED':
                    raise RuntimeError(f"Order rejected: {result.get('rejectReason', 'unknown')}")
                
                order.fill(fill_price, filled_qty)
                self._apply_fees(fill_price * filled_qty)
                self._update_position(symbol, 'long', filled_qty, fill_price, leverage)
                
                logger.info(
                    f"Testnet long filled: {symbol} {filled_qty} @ {fill_price} "
                    f"(orderId={result.get('orderId')}, leverage: {leverage}x)"
                )
            except Exception as e:
                logger.error(f"Testnet long order failed: {type(e).__name__}: {e}")
                order.reject(str(e))
                return order
        else:
            fill_price = self._apply_slippage(price, 'buy')
            order.fill(fill_price, size)
            self._apply_fees(fill_price * size)
            self._update_position(symbol, 'long', size, fill_price, leverage)
            logger.info(f"Opened long: {symbol} {size} @ {price} (leverage: {leverage}x)")
        
        self._notify_order_callback(order)
        return order
    
    def _open_short(self, symbol: str, price: float, size: float,
                    leverage: Optional[int]) -> Order:
        """Open short position."""
        order_id = self._generate_order_id()
        
        order = Order(order_id, symbol, 'sell', OrderType.MARKET, size, price, leverage)
        self.orders[order_id] = order
        
        if self.mode == 'testnet' and self.testnet_client:
            try:
                result = self.testnet_client.place_market_order(
                    symbol=symbol,
                    side='SELL',
                    quantity=size,
                )
                
                order_id = result.get('orderId')
                if order_id:
                    result = self._wait_for_order_fill(symbol, str(order_id))
                
                order_status = result.get('status', '')
                
                fill_price_raw = result.get('avgPrice')
                fill_price = float(fill_price_raw) if fill_price_raw and fill_price_raw != '0.00' else float(price)
                filled_qty_raw = result.get('executedQty')
                filled_qty = float(filled_qty_raw) if filled_qty_raw and filled_qty_raw != '0.0000' else float(size)
                
                if order_status == 'REJECTED':
                    raise RuntimeError(f"Order rejected: {result.get('rejectReason', 'unknown')}")
                
                order.fill(fill_price, filled_qty)
                self._apply_fees(fill_price * filled_qty)
                self._update_position(symbol, 'short', filled_qty, fill_price, leverage)
                
                logger.info(
                    f"Testnet short filled: {symbol} {filled_qty} @ {fill_price} "
                    f"(orderId={result.get('orderId')}, leverage: {leverage}x)"
                )
            except Exception as e:
                logger.error(f"Testnet short order failed: {type(e).__name__}: {e}")
                order.reject(str(e))
                return order
        else:
            fill_price = self._apply_slippage(price, 'sell')
            order.fill(fill_price, size)
            self._apply_fees(fill_price * size)
            self._update_position(symbol, 'short', size, fill_price, leverage)
            logger.info(f"Opened short: {symbol} {size} @ {price} (leverage: {leverage}x)")
        
        self._notify_order_callback(order)
        return order
    
    def close_position(self, symbol: str, price: Optional[float] = None, size: Optional[float] = None) -> Optional[Order]:
        """Close a position by symbol."""
        position = self.positions.get(symbol)
        if not position or position.get('size', 0) == 0:
            logger.warning(f"No position to close: {symbol}")
            return None
        
        entry_price = position.get('entry_price', 0)
        close_price = float(price) if price else float(entry_price)
        return self._close_position(symbol, close_price, size)
    
    def _close_position(self, symbol: str, price: float, size: Optional[float] = None) -> Optional[Order]:
        """Close position."""
        position = self.positions.get(symbol)
        
        if not position or position.get('size', 0) == 0:
            logger.warning(f"No position to close: {symbol}")
            return None
        
        close_size = size or abs(position['size'])
        
        side = 'sell' if position['size'] > 0 else 'buy'
        position_side = 'LONG' if position['size'] > 0 else 'SHORT'
        
        order_id = self._generate_order_id()
        
        order = Order(order_id, symbol, side, OrderType.MARKET, close_size, price, position.get('leverage', 1))
        
        self.orders[order_id] = order
        
        if self.mode == 'testnet' and self.testnet_client:
            try:
                remote_positions = self.testnet_client.get_position_risk(symbol)
                remote_size = 0
                remote_side = None
                for rp in remote_positions:
                    if rp.get('symbol') == symbol:
                        remote_amt_raw = rp.get('positionAmt', '0')
                        remote_amt = float(remote_amt_raw) if remote_amt_raw else 0.0
                        if remote_amt != 0:
                            remote_size = abs(remote_amt)
                            remote_side = 'sell' if remote_amt > 0 else 'buy'
                            break
                
                if remote_size == 0:
                    logger.info(f"No exchange position found for {symbol}, clearing local state")
                    position['size'] = 0
                    position['entry_price'] = 0
                    position['side'] = None
                    return None
                
                actual_close_side = remote_side or side
                result = self.testnet_client.place_market_order(
                    symbol=symbol,
                    side=actual_close_side.upper(),
                    quantity=remote_size,
                )
                
                order_id = result.get('orderId')
                if order_id:
                    result = self._wait_for_order_fill(symbol, str(order_id))
                
                order_status = result.get('status', '')
                
                fill_price_raw = result.get('avgPrice')
                fill_price = float(fill_price_raw) if fill_price_raw and fill_price_raw != '0.00' else float(price)
                filled_qty_raw = result.get('executedQty')
                filled_qty = float(filled_qty_raw) if filled_qty_raw and filled_qty_raw != '0.0000' else float(remote_size)
                order_id = str(result.get('orderId', ''))
                
                if order_status == 'REJECTED':
                    raise RuntimeError(f"Order rejected: {result.get('rejectReason', 'unknown')}")
                
                try:
                    order.fill(fill_price, filled_qty)
                except Exception as fill_err:
                    logger.error(f"order.fill failed: {fill_err}")
                    raise
                
                try:
                    self._apply_fees(fill_price * filled_qty)
                except Exception as fee_err:
                    logger.error(f"_apply_fees failed: {fee_err}")
                    raise
                
                pnl = 0.0
                try:
                    pos_copy = dict(position) if position else {}
                    for k, v in pos_copy.items():
                        if isinstance(v, str):
                            try:
                                pos_copy[k] = float(v)
                            except Exception:
                                pass
                    pnl_calc = self._calculate_pnl(pos_copy, filled_qty, fill_price)
                    if pnl_calc is not None:
                        pnl = float(pnl_calc)
                    order.pnl = pnl
                except Exception as calc_err:
                    logger.warning(f"PnL calculation failed: {calc_err}")
                    order.pnl = 0.0
                
                try:
                    self._reduce_position(symbol, filled_qty)
                except Exception as reduce_err:
                    logger.error(f"_reduce_position failed: {reduce_err}")
                    raise
                
                pnl_safe = 0.0
                try:
                    if pnl is None:
                        pnl_safe = 0.0
                    else:
                        pnl_safe = float(pnl)
                except (ValueError, TypeError):
                    pnl_safe = 0.0
                try:
                    pnl_str = f"{pnl_safe:.2f}"
                    logger.info(
                        f"Testnet close filled: {symbol} {actual_close_side} {filled_qty} @ {fill_price} "
                        f"PnL: {pnl_str} (orderId={order_id})"
                    )
                except Exception as log_err:
                    logger.info(f"Testnet close filled: {symbol} {filled_qty} @ {fill_price}")
                
                if self.trade_logger and pnl_safe != 0:
                    self.trade_logger.log_close_position(
                        symbol=symbol,
                        side=actual_close_side,
                        quantity=filled_qty,
                        exit_price=fill_price,
                        pnl=pnl_safe,
                        fees=0.0,
                        order_id=order_id,
                    )
            except Exception as e:
                # Log actual error for debugging (without passing to reject)
                logger.info(f"Testnet close error: {type(e).__name__}: {str(e)[:200]}")
                logger.error("Testnet close order failed")
                order.reject("close_failed")
                return order
        else:
            fill_price = self._apply_slippage(price, side)
            order.fill(fill_price, close_size)
            self._apply_fees(fill_price * close_size)
            
            pnl = self._calculate_pnl(position, close_size, fill_price)
            order.pnl = pnl
            
            self._reduce_position(symbol, close_size)
            
            pnl_val = float(pnl) if pnl is not None else 0.0
            logger.info(f"Closed position: {symbol} {close_size} @ {price} PnL: {pnl_val:.2f}")
            
            if self.trade_logger:
                self.trade_logger.log_close_position(
                    symbol=symbol,
                    side=side,
                    quantity=close_size,
                    exit_price=fill_price,
                    pnl=pnl_val,
                    fees=0.0,
                    order_id=order.order_id if order else "",
                )
        
        self._notify_order_callback(order)
        
        return order
    
    def _update_position(self, symbol: str, side: str, size: float, 
                         price: float, leverage: Optional[int]):
        """Update position. Thread-safe."""
        with self._lock:
            if symbol not in self.positions:
                self.positions[symbol] = {
                    'size': 0,
                    'entry_price': 0,
                    'leverage': leverage,
                    'side': None,
                    'pnl': 0,
                    'unrealized_pnl': 0
                }
            
            position = self.positions[symbol]
            
            was_empty = position['size'] == 0
            
            if position['size'] == 0:
                position['size'] = size if side == 'long' else -size
                position['entry_price'] = price
                position['side'] = side
            else:
                existing_side = 'long' if position['size'] > 0 else 'short'
                
                if side == existing_side:
                    position['size'] += size if side == 'long' else -size
                    position['entry_price'] = (position['entry_price'] * (abs(position['size']) - size) + 
                                                price * size) / abs(position['size'])
                else:
                    if abs(position['size']) >= size:
                        position['size'] += size if side == 'long' else -size
                        if position['size'] == 0:
                            position['entry_price'] = 0
                            position['side'] = None
                    else:
                        remaining = size - abs(position['size'])
                        position['size'] = size if side == 'long' else -size
                        position['entry_price'] = price
                        position['side'] = side
            
            position['leverage'] = leverage
            
            if was_empty and self.trade_logger:
                self.trade_logger.log_open_position(
                    symbol=symbol,
                    side=side,
                    quantity=abs(size),
                    entry_price=price,
                    order_id="",
                    strategy="engine",
                    leverage=leverage or 1,
                )
    
    def _reduce_position(self, symbol: str, size: float):
        """Reduce position by size, correctly handling longs and shorts. Thread-safe."""
        with self._lock:
            position = self.positions.get(symbol)
            
            if position:
                was_open = position.get('size', 0) != 0
                
                if position['size'] > 0:
                    position['size'] = position['size'] - size
                else:
                    position['size'] = position['size'] + size
                
                is_closed = abs(position['size']) < 1e-10
                
                if is_closed:
                    position['size'] = 0
                    position['entry_price'] = 0
                    position['side'] = None
                    position['unrealized_pnl'] = 0
                    
                    if was_open and self.trade_logger:
                        pass  # PnL is calculated in close_position method
    
    def _calculate_pnl(self, position: Dict[str, Any], size: float, 
                       close_price: float) -> float:
        """Calculate realized PnL."""
        try:
            position_size = position.get('size', 0)
            if position_size == 0:
                return 0.0
            
            entry_price = float(position.get('entry_price', 0))
            size = float(size)
            close_price = float(close_price)
            
            if position_size > 0:
                return (close_price - entry_price) * size
            else:
                return (entry_price - close_price) * size
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"PnL calculation error: {e}, position={position}, size={size}, close={close_price}")
            return 0.0
    
    def update_unrealized_pnl(self, symbol: str, current_price: float):
        """Update unrealized PnL. Thread-safe."""
        with self._lock:
            position = self.positions.get(symbol)
            
            if position and position.get('size', 0) != 0:
                entry_price = position['entry_price']
                
                if position['size'] > 0:
                    position['unrealized_pnl'] = (current_price - entry_price) * abs(position['size'])
                else:
                    position['unrealized_pnl'] = (entry_price - current_price) * abs(position['size'])
    
    def get_position(self, symbol: str) -> Dict[str, Any]:
        """Get position for symbol. Thread-safe."""
        with self._lock:
            pos = self.positions.get(symbol)
            if pos:
                return dict(pos)
        return {
            'size': 0, 'entry_price': 0, 'leverage': 1,
            'side': None, 'pnl': 0, 'unrealized_pnl': 0
        }
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all positions. Thread-safe snapshot."""
        with self._lock:
            return {k: dict(v) for k, v in self.positions.items()}
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_open_orders(self) -> List[Order]:
        """Get open orders."""
        return [o for o in self.orders.values() 
                if o.status in [OrderStatus.PENDING, OrderStatus.PARTIAL]]
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self.order_counter += 1
        return f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.order_counter}"
    
    def add_order_callback(self, callback: Callable[[Order], None]):
        """Add order callback."""
        self.order_callbacks.append(callback)
    
    def _notify_order_callback(self, order: Order):
        """Notify order callbacks."""
        for callback in self.order_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error("Order callback error")
    
    def sync_positions_from_exchange(self) -> int:
        """
        Sync local positions with exchange state.
        Replaces local state entirely with exchange state.
        Only syncs positions for tracked symbols.
        Returns number of positions synced.
        """
        if self.mode != 'testnet' or not self.testnet_client:
            return 0
        
        tracked_symbols = {'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'}
        
        try:
            remote_positions = self.testnet_client.get_position_risk()
            
            self.positions.clear()
            synced = 0
            
            for pos in remote_positions:
                symbol = pos.get('symbol', '')
                
                if symbol not in tracked_symbols:
                    continue
                
                position_amt_raw = pos.get('positionAmt', '0')
                position_amt = float(position_amt_raw) if position_amt_raw else 0.0
                
                if position_amt == 0:
                    continue
                
                side = 'long' if position_amt > 0 else 'short'
                entry_price_raw = pos.get('entryPrice', '0')
                entry_price = float(entry_price_raw) if entry_price_raw else 0.0
                leverage = self.leverage
                unrealized_pnl_raw = pos.get('unRealizedProfit', '0')
                unrealized_pnl = float(unrealized_pnl_raw) if unrealized_pnl_raw else 0.0
                
                self.positions[symbol] = {
                    'size': position_amt,
                    'entry_price': entry_price,
                    'leverage': leverage,
                    'side': side,
                    'pnl': 0,
                    'unrealized_pnl': unrealized_pnl,
                }
                
                logger.info(
                    f"Synced position from testnet: {symbol} {side} "
                    f"{abs(position_amt)} @ {entry_price} (PnL: {unrealized_pnl:.2f})"
                )
                synced += 1
            
            if synced == 0:
                logger.info("No open positions on testnet for tracked symbols")
            
            return synced
            
        except Exception as e:
            logger.error("Failed to sync positions from exchange")
            return 0
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 3 (Feature 4: Slippage Feedback)
    # =========================================================================
    
    def record_slippage(self, symbol: str, predicted_price: float, 
                        actual_price: float, side: str):
        """
        Feature 4: Slippage Feedback Loop
        Track predicted vs actual slippage, update model.
        """
        if predicted_price == 0:
            return
        
        predicted_slip = abs(actual_price - predicted_price) / predicted_price
        
        self.slippage_history.append({
            'symbol': symbol,
            'predicted_price': predicted_price,
            'actual_price': actual_price,
            'actual_slippage': predicted_slip,
            'side': side,
            'timestamp': datetime.now().isoformat()
        })
        
        if len(self.slippage_history) > self.max_slippage_history:
            self.slippage_history.pop(0)
        
        self._update_slippage_model()
    
    def _update_slippage_model(self):
        """Update slippage model based on actual vs predicted."""
        if len(self.slippage_history) < 5:
            return
        
        recent = self.slippage_history[-20:]
        avg_actual_slippage = sum(s['actual_slippage'] for s in recent) / len(recent)
        
        error = avg_actual_slippage - self.predicted_slippage_pct
        
        if abs(error) > self.slippage_error_tolerance:
            self.predicted_slippage_pct = avg_actual_slippage * self.slippage_penalty_factor
            logger.warning(
                f"Slippage model updated: {self.predicted_slippage_pct:.4%} "
                f"(error: {error:.4%})"
            )
    
    def get_slippage_estimate(self, symbol: str = None) -> float:
        """Get current slippage estimate, adjusted by feedback."""
        if symbol and self.slippage_history:
            symbol_slips = [s['actual_slippage'] for s in self.slippage_history 
                           if s['symbol'] == symbol]
            if symbol_slips:
                return sum(symbol_slips) / len(symbol_slips) * self.slippage_penalty_factor
        
        return self.predicted_slippage_pct
    
    def get_slippage_status(self) -> Dict[str, Any]:
        """Get slippage feedback status."""
        if not self.slippage_history:
            return {
                'samples': 0,
                'predicted_slippage': self.slippage_pct,
                'actual_slippage': 0,
                'error': 0
            }
        
        recent = self.slippage_history[-20:]
        avg_actual = sum(s['actual_slippage'] for s in recent) / len(recent)
        
        return {
            'samples': len(self.slippage_history),
            'predicted_slippage': self.predicted_slippage_pct,
            'actual_slippage': avg_actual,
            'error': avg_actual - self.predicted_slippage_pct,
            'penalty_applied': self.slippage_penalty_factor
        }
