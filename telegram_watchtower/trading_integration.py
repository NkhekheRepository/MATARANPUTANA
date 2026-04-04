"""
Trading Integration for Telegram Bot
===================================
Connects NkhekheAlphaBot to the Paper Trading Engine.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

sys.path.insert(0, str(Path(__file__).parent.parent))


class TradingBotIntegration:
    """Integration with Paper Trading Engine"""
    
    def __init__(self):
        self.paper_engine = None
        self.alert_callback = None
        self.connected = False
        
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize connection to paper trading engine via API."""
        try:
            import requests
            
            # Test connection to dashboard API
            dashboard_url = os.getenv('DASHBOARD_URL', 'http://localhost:8080')
            response = requests.get(
                f"{dashboard_url}/api/health",
                auth=(
                    os.getenv('DASHBOARD_USER', 'admin'),
                    os.getenv('DASHBOARD_PASS', 'nwa45690')
                ),
                timeout=5
            )
            
            if response.status_code == 200:
                self.connected = True
                self.dashboard_url = dashboard_url
                self.auth = (
                    os.getenv('DASHBOARD_USER', 'admin'),
                    os.getenv('DASHBOARD_PASS', 'nwa45690')
                )
                print(f"Connected to Paper Trading Engine at {dashboard_url}")
                return True
            else:
                print(f"Failed to connect to dashboard: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Failed to initialize trading integration: {e}")
            return False
    
    def _api_get(self, endpoint: str) -> Dict:
        """Make API request to dashboard"""
        import requests
        try:
            response = requests.get(
                f"{self.dashboard_url}{endpoint}",
                auth=self.auth,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def _api_post(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make POST request to dashboard"""
        import requests
        try:
            response = requests.post(
                f"{self.dashboard_url}{endpoint}",
                auth=self.auth,
                json=data,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def start(self) -> Dict[str, Any]:
        """Start the trading engine."""
        return self._api_post('/api/start')
    
    def stop(self):
        """Stop the trading engine."""
        return self._api_post('/api/stop')
    
    def get_status(self) -> Dict[str, Any]:
        """Get trading status."""
        return self._api_get('/api/status')
    
    def long(self, quantity: float) -> Dict[str, Any]:
        """Open LONG position."""
        return self._api_post('/api/order/long', {'quantity': quantity})
    
    def short(self, quantity: float) -> Dict[str, Any]:
        """Open SHORT position."""
        return self._api_post('/api/order/short', {'quantity': quantity})
    
    def close(self) -> Dict[str, Any]:
        """Close position."""
        return self._api_post('/api/order/close')
    
    def set_leverage(self, leverage: int) -> Dict[str, Any]:
        """Set leverage."""
        return self._api_post('/api/leverage', {'leverage': leverage})
    
    def get_trade_history(self, limit: int = 10) -> List[Dict]:
        """Get trade history."""
        data = self._api_get(f'/api/trades?limit={limit}')
        return data.get('trades', [])
    
    def set_trading_engine(self, engine):
        """Legacy compatibility - accept engine object."""
        pass

    def get_balance(self) -> float:
        """Get wallet balance via API."""
        data = self._api_get('/api/balance')
        return data.get('balance', 0.0)

    def get_price(self, symbol: Optional[str] = None) -> float:
        """Get current price via API."""
        data = self._api_get(f'/api/price/{symbol or "BTCUSDT"}')
        return data.get('price', 0.0)

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions via API."""
        data = self._api_get('/api/positions')
        return data.get('positions', [])

    def get_liquidation_warning(self, symbol: Optional[str] = None) -> Optional[str]:
        """Get liquidation warning via API."""
        data = self._api_get(f'/api/liquidation/{symbol or "BTCUSDT"}')
        return data.get('warning')
    
    def set_alert_callback(self, callback):
        """Set callback for trade alerts."""
        self.alert_callback = callback
    
    def _format_trade_alert(self, side: str, result: Dict[str, Any]) -> str:
        """Format trade alert message."""
        order = result.get('order', {})
        position = result.get('position', {})
        
        emoji = "📈" if side == "LONG" else "📉"
        
        return f"""
{emoji} <b>{side} EXECUTED</b>

<b>Symbol:</b> {order.get('symbol', 'BTCUSDT')}
<b>Quantity:</b> {order.get('executedQty', 'N/A')}
<b>Price:</b> ${float(order.get('avgPrice', 0)):,.2f}
<b>Leverage:</b> {result.get('leverage', 75)}x
<b>PnL:</b> ${position.get('unrealized_pnl', 0):.2f}
"""
    
    def _format_close_alert(self, result: Dict[str, Any]) -> str:
        """Format close position alert."""
        return f"""
🛑 <b>POSITION CLOSED</b>

<b>Symbol:</b> {result.get('symbol', 'BTCUSDT')}
<b>Status:</b> {result.get('status', 'FILLED')}
"""


trading_integration = TradingBotIntegration()
