"""
VN.PY Data Bridge
=================
Bridge between paper trading layers and VN.PY market data.
Replaces custom Binance clients with VN.PY's market data infrastructure.
"""

import os
import time
import random
import threading
from typing import Dict, Any, Optional, List, Callable
from collections import deque
from datetime import datetime
from loguru import logger

# Import from vnpy_engine - moved inside connect() for faster startup
# try:
#     from vnpy_engine.vnpy_local.market_data import get_market_data_instance, BinanceMarketData
#     from vnpy_engine.vnpy_local.shared_state import shared_state
#     VNPY_AVAILABLE = True
# except ImportError as e:
#     logger.warning(f"VN.PY imports not available: {e}")
#     VNPY_AVAILABLE = False

# Set to False initially, check in connect()
VNPY_AVAILABLE = False
get_market_data_instance = None
shared_state = None


class VNPyDataBridge:
    """
    Bridge between paper trading Layer 1 and VN.PY market data.
    Provides unified interface for market data from VN.PY engine.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.symbols = self.config.get('symbols', ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'])
        self.buffer_size = self.config.get('buffer_size', 100)
        self.update_interval = self.config.get('update_interval', 5)
        
        # State
        self.connected = False
        self._lock = threading.Lock()
        
        # Data storage
        self.data_buffer: Dict[str, deque] = {
            sym: deque(maxlen=self.buffer_size) for sym in self.symbols
        }
        self.latest_data: Dict[str, Dict[str, Any]] = {}
        
        # VN.PY integration
        self.market_data = None
        self._callbacks: Dict[str, List[Callable]] = {}
        
        logger.info(f"VNPyDataBridge initialized for symbols: {self.symbols}")
    
    def connect(self) -> bool:
        """Connect to VN.PY market data feed."""
        try:
            start_time = time.time()
            logger.info("Starting VNPyDataBridge connection...")
            
            # Lazy import VN.PY modules here to avoid slow startup
            global VNPY_AVAILABLE, get_market_data_instance, shared_state
            if not VNPY_AVAILABLE:
                try:
                    import sys
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    from vnpy_engine.vnpy_local.market_data import get_market_data_instance, BinanceMarketData
                    from vnpy_engine.vnpy_local.shared_state import shared_state
                    VNPY_AVAILABLE = True
                    logger.info("VN.PY modules imported successfully")
                except ImportError as e:
                    logger.warning(f"VN.PY imports not available: {e}")
                    VNPY_AVAILABLE = False
            
            if VNPY_AVAILABLE:
                # Use VN.PY market data
                logger.info("Initializing VN.PY market data instance...")
                instance_start = time.time()
                self.market_data = get_market_data_instance([s.lower() for s in self.symbols])
                instance_time = time.time() - instance_start
                logger.info(f"VN.PY market data instance initialized in {instance_time:.2f}s")
                
                # Subscribe to ticker updates for each symbol
                logger.info("Subscribing to market data symbols...")
                subscribe_start = time.time()
                for symbol in self.symbols:
                    self.market_data.subscribe(
                        callback=lambda data, s=symbol: self._on_market_data(s, data),
                        symbol=symbol.lower()
                    )
                subscribe_time = time.time() - subscribe_start
                logger.info(f"Symbol subscriptions completed in {subscribe_time:.2f}s")
                
                logger.info("Starting VN.PY market data feed...")
                start_start = time.time()
                self.market_data.start()
                start_time_taken = time.time() - start_start
                logger.info(f"VN.PY market data feed started in {start_time_taken:.2f}s")
                
                self.connected = True
                logger.info("Connected to VN.PY market data feed")
            else:
                # Fallback to mock data
                logger.warning("VN.PY not available, using mock data")
                self._start_mock_data()
                self.connected = True
            
            total_time = time.time() - start_time
            logger.info(f"VNPyDataBridge connection completed in {total_time:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to VN.PY: {e}")
            self._start_mock_data()
            self.connected = True
            return False
    
    def disconnect(self):
        """Disconnect from market data feed."""
        self.connected = False
        if self.market_data:
            try:
                self.market_data.stop()
            except Exception:
                pass
        logger.info("Disconnected from market data feed")
    
    def _on_market_data(self, symbol: str, data: Dict[str, Any]):
        """Callback for VN.PY market data updates."""
        try:
            symbol = symbol.upper()
            
            price = data.get('price', 0)
            if price <= 0:
                logger.warning(f"Invalid price for {symbol}: {price}")
                return
            
            # If high/low not provided, generate realistic OHLCV spread
            if 'high' not in data or 'low' not in data:
                spread_pct = random.uniform(0.003, 0.008)  # 0.3-0.8% spread
                spread = price * spread_pct
                high_price = price * (1 + random.uniform(0, spread_pct * 0.5))
                low_price = price * (1 - random.uniform(0, spread_pct * 0.5))
                open_price = price * (1 + random.uniform(-spread_pct * 0.3, spread_pct * 0.3))
            else:
                open_price = data.get('open', price)
                high_price = data['high']
                low_price = data['low']
            
            bar_data = {
                'symbol': symbol,
                'timestamp': int(data.get('timestamp', time.time() * 1000)),
                'open': round(open_price, 8),
                'high': round(high_price, 8),
                'low': round(low_price, 8),
                'close': round(price, 8),
                'volume': data.get('volume', 0),
                'closed': True,
                'datetime': datetime.fromtimestamp(data.get('timestamp', time.time()) / 1000) 
                           if 'timestamp' in data else datetime.now()
            }
            
            with self._lock:
                if symbol in self.data_buffer:
                    self.data_buffer[symbol].append(bar_data)
                self.latest_data[symbol] = bar_data
            
            # Call registered callbacks
            if symbol in self._callbacks:
                for callback in self._callbacks[symbol]:
                    try:
                        callback(bar_data)
                    except Exception as e:
                        logger.error(f"Callback error for {symbol}: {e}")
                        
            # Also publish to shared state for VN.PY engine
            if VNPY_AVAILABLE:
                try:
                    shared_state.set_position(f"{symbol}_price", {
                        "price": data.get('price', 0),
                        "volume": data.get('volume', 0),
                        "timestamp": time.time()
                    })
                except Exception:
                    pass
                        
        except Exception as e:
            logger.error(f"Error processing market data for {symbol}: {e}")
    
    def _start_mock_data(self):
        """Fetch real prices from Binance public API for realistic data."""
        import urllib.request
        import json

        # Initialize with dummy data immediately for fast startup
        for symbol in self.symbols:
            dummy_data = self._get_default_data(symbol)
            with self._lock:
                if symbol in self.data_buffer:
                    self.data_buffer[symbol].append(dummy_data)
                self.latest_data[symbol] = dummy_data
            logger.debug(f"Initialized {symbol} with dummy data")

        def fetch_binance_prices():
            """Get current prices from Binance public API."""
            prices = {}
            for symbol in self.symbols:
                try:
                    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                        prices[symbol] = float(data['price'])
                except Exception as e:
                    logger.warning(f"Failed to fetch {symbol} from Binance: {e}")
            return prices

        volume_ranges = {
            'BTCUSDT': (50.0, 500.0),
            'ETHUSDT': (200.0, 2000.0),
            'SOLUSDT': (1000.0, 10000.0),
            'BNBUSDT': (100.0, 1500.0),
        }

        def real_data_loop():
            while self.connected:
                real_prices = fetch_binance_prices()
                
                if not real_prices:
                    time.sleep(self.update_interval)
                    continue
                
                for symbol in self.symbols:
                    try:
                        current_price = real_prices.get(symbol)
                        if not current_price:
                            continue
                        
                        vol_min, vol_max = volume_ranges.get(symbol, (100.0, 1000.0))
                        volume = (vol_min + vol_max) / 2
                        
                        spread = current_price * 0.001
                        open_price = current_price * (1 + random.uniform(-0.0005, 0.0005))
                        high_price = current_price + abs(spread * random.uniform(0, 0.5))
                        low_price = current_price - abs(spread * random.uniform(0, 0.5))

                        bar_data = {
                            'symbol': symbol,
                            'timestamp': int(time.time() * 1000),
                            'open': round(open_price, 8),
                            'high': round(high_price, 8),
                            'low': round(low_price, 8),
                            'close': round(current_price, 8),
                            'volume': round(volume, 2),
                            'closed': True,
                            'datetime': datetime.now()
                        }

                        with self._lock:
                            if symbol in self.data_buffer:
                                self.data_buffer[symbol].append(bar_data)
                            self.latest_data[symbol] = bar_data

                        if symbol in self._callbacks:
                            for callback in self._callbacks[symbol]:
                                try:
                                    callback(bar_data)
                                except Exception as e:
                                    logger.error(f"Callback error for {symbol}: {e}")

                    except Exception as e:
                        logger.error(f"Data error for {symbol}: {e}")

                time.sleep(self.update_interval)

        thread = threading.Thread(target=real_data_loop, daemon=True)
        thread.start()
        logger.info("Started real-time Binance market data feed (public API)")
    
    def subscribe(self, callback: Callable, symbol: str):
        """Subscribe to market data updates for a symbol."""
        symbol = symbol.upper()
        if symbol not in self._callbacks:
            self._callbacks[symbol] = []
        self._callbacks[symbol].append(callback)
        logger.debug(f"Subscribed to {symbol} updates")
    
    def get_latest_data(self, symbol: str = None) -> Dict[str, Any]:
        """Get latest market data for a symbol (default: first symbol)."""
        with self._lock:
            if symbol:
                symbol = symbol.upper()
                return self.latest_data.get(symbol, self._get_default_data(symbol))
            
            # Return data for first symbol if no symbol specified
            if self.latest_data:
                return list(self.latest_data.values())[0]
            
            return self._get_default_data(self.symbols[0] if self.symbols else 'BTCUSDT')
    
    def get_buffer(self, symbol: str, n: int = 100) -> List[Dict[str, Any]]:
        """Get recent n bars from buffer for a symbol."""
        symbol = symbol.upper()
        with self._lock:
            if symbol in self.data_buffer:
                return list(self.data_buffer[symbol])[-n:]
            return []
    
    def get_all_latest(self) -> Dict[str, Dict[str, Any]]:
        """Get latest data for all subscribed symbols."""
        with self._lock:
            return self.latest_data.copy()
    
    def _get_default_data(self, symbol: str) -> Dict[str, Any]:
        """Return default data when no data is available."""
        base_prices = {
            'BTCUSDT': 102000.0,
            'ETHUSDT': 3500.0,
            'SOLUSDT': 150.0,
            'BNBUSDT': 650.0,
            'XRPUSDT': 2.20,
        }

        price = base_prices.get(symbol, 1000.0)
        spread = price * 0.005
        return {
            'symbol': symbol,
            'timestamp': int(time.time() * 1000),
            'open': price,
            'high': price + spread,
            'low': price - spread,
            'close': price,
            'volume': 100,
            'closed': True,
            'datetime': datetime.now()
        }
    
    def is_connected(self) -> bool:
        """Check if connected to data source."""
        return self.connected
    
    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        data = self.get_latest_data(symbol)
        return data.get('close', 0)
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get current prices for all symbols."""
        all_data = self.get_all_latest()
        return {sym: data.get('close', 0) for sym, data in all_data.items()}


# Singleton instance
_bridge_instance: Optional[VNPyDataBridge] = None


def get_data_bridge(config: Dict[str, Any] = None) -> VNPyDataBridge:
    """Get singleton data bridge instance."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = VNPyDataBridge(config)
    return _bridge_instance


def reset_data_bridge():
    """Reset the data bridge instance."""
    global _bridge_instance
    if _bridge_instance:
        _bridge_instance.disconnect()
    _bridge_instance = None


if __name__ == "__main__":
    # Test the data bridge
    print("Testing VNPyDataBridge...")
    
    config = {
        'symbols': ['BTCUSDT', 'ETHUSDT'],
        'update_interval': 2
    }
    
    bridge = VNPyDataBridge(config)
    
    # Test connection
    connected = bridge.connect()
    print(f"Connected: {connected}")
    
    # Wait for some data
    time.sleep(5)
    
    # Get latest data
    latest = bridge.get_latest_data('BTCUSDT')
    print(f"Latest BTC data: {latest}")
    
    # Get all prices
    prices = bridge.get_all_prices()
    print(f"All prices: {prices}")
    
    # Disconnect
    bridge.disconnect()
    print("VNPyDataBridge test complete!")