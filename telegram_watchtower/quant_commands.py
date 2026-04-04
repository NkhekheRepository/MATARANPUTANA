#!/usr/bin/env python3
"""
Quant Command Processor for Telegram Watch Tower
Advanced trading analytics and commands for senior quant developers
"""

import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any

logger = logging.getLogger('QuantCommandProcessor')

DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'http://localhost:8080')
DASHBOARD_USER = os.getenv('DASHBOARD_USER', 'admin')
DASHBOARD_PASS = os.getenv('DASHBOARD_PASS', 'nwa45690')


class QuantCommandProcessor:
    """Advanced command processor for quant trading operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.dashboard_url = DASHBOARD_URL
        self.auth = (DASHBOARD_USER, DASHBOARD_PASS)
        
        self.commands = {
            # P&L & Risk Analytics
            '/pnl': self.cmd_pnl,
            '/risk': self.cmd_risk,
            '/positions': self.cmd_positions,
            '/portfolio': self.cmd_portfolio,
            
            # Market Data
            '/market': self.cmd_market,
            '/price': self.cmd_price,
            
            # Trade Execution
            '/long': self.cmd_long,
            '/short': self.cmd_short,
            '/close': self.cmd_close,
            '/buy': self.cmd_buy,
            '/sell': self.cmd_sell,
            
            # Position Sizing
            '/calc': self.cmd_calc,
            '/size': self.cmd_size,
            
            # Strategy
            '/strategy': self.cmd_strategy,
            '/strategies': self.cmd_strategies,
            
            # Performance
            '/report': self.cmd_report,
            '/history': self.cmd_history,
            '/trades': self.cmd_trades,
            
            # System
            '/system': self.cmd_system,
            '/health': self.cmd_health,
            
            # Advanced Analytics (NEW)
            '/equity': self.cmd_equity,
            '/drawdown': self.cmd_drawdown,
            '/winrate': self.cmd_winrate,
            '/metrics': self.cmd_metrics,
            '/regime': self.cmd_regime,
            
            # Model Learning (NEW)
            '/learning': self.cmd_learning,
            
            # Help
            '/help': self.cmd_help,
            '/h': self.cmd_help,
        }
    
    def _api_get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated GET request to dashboard API"""
        try:
            url = f"{self.dashboard_url}{endpoint}"
            response = requests.get(url, auth=self.auth, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return {'error': str(e)}
    
    def _api_post(self, endpoint: str, data: Dict = None) -> Dict:
        """Make authenticated POST request to dashboard API"""
        try:
            url = f"{self.dashboard_url}{endpoint}"
            response = requests.post(url, auth=self.auth, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return {'error': str(e)}
    
    def process(self, chat_id: int, text: str, bot) -> str:
        """Process a command and return response"""
        command = text.strip().split()[0] if text.strip() else ''
        
        if not command:
            return "Please send a command. Type /help for available commands."
        
        if command in self.commands:
            try:
                return self.commands[command](chat_id, text, bot)
            except Exception as e:
                logger.error(f"Command error: {e}")
                return f"Error: {str(e)}"
        
        # Fallback to legacy commands
        return None
    
    # =========================================================================
    # P&L & Risk Analytics Commands
    # =========================================================================
    
    def cmd_pnl(self, chat_id: int, text: str, bot) -> str:
        """Comprehensive P&L Dashboard"""
        data = self._api_get('/api/pnl/summary')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        daily = data.get('daily', {})
        metrics = data.get('metrics', {})
        
        lines = [
            "📊 *P&L DASHBOARD*",
            "═" * 30,
            "",
            "┌─ *DAILY PERFORMANCE* ────────┐",
            f"│ P&L:          ${daily.get('total_pnl', 0):>12.2f} │",
            f"│ Trades:        {daily.get('trade_count', 0):>12} │",
            f"│ Win Rate:      {daily.get('win_rate', 0):>11.1f}% │",
            f"│ Wins:          {daily.get('win_count', 0):>12} │",
            f"│ Losses:        {daily.get('loss_count', 0):>12} │",
            "└────────────────────────────────┘",
            "",
            "┌─ *CUMULATIVE* ────────────────┐",
            f"│ Total P&L:    ${data.get('cumulative', 0):>12.2f} │",
            f"│ Total Trades: {data.get('trade_count', 0):>12} │",
            "└────────────────────────────────┘",
            "",
            "┌─ *RISK METRICS* ──────────────┐",
            f"│ Sharpe:       {metrics.get('sharpe_ratio', 0):>12.2f} │",
            f"│ Sortino:      {metrics.get('sortino_ratio', 0):>12.2f} │",
            f"│ Max Drawdown: ${metrics.get('max_drawdown', 0):>11.2f} │",
            f"│ Profit Factor:{metrics.get('profit_factor', 0):>12.2f} │",
            f"│ Volatility:   {metrics.get('volatility', 0):>11.2f}% │",
            "└────────────────────────────────┘",
        ]
        
        return "\n".join(lines)
    
    def cmd_risk(self, chat_id: int, text: str, bot) -> str:
        """Risk metrics display"""
        data = self._api_get('/api/pnl/summary')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        metrics = data.get('metrics', {})
        
        lines = [
            "🎯 *RISK METRICS*",
            "═" * 25,
            "",
            f"*Sharpe Ratio:*    `{metrics.get('sharpe_ratio', 0):.2f}`",
            f"*Sortino Ratio:*   `{metrics.get('sortino_ratio', 0):.2f}`",
            f"*Max Drawdown:*    `${metrics.get('max_drawdown', 0):.2f}`",
            f"*Profit Factor:*   `{metrics.get('profit_factor', 0):.2f}`",
            f"*Calmar Ratio:*    `{metrics.get('calmar_ratio', 0):.2f}`",
            f"*Volatility:*      `{metrics.get('volatility', 0):.2f}%`",
            "",
            "─── Trade Statistics ───",
            f"*Total Trades:*     {metrics.get('total_trades', 0)}",
            f"*Winning Trades:*  {metrics.get('winning_trades', 0)}",
            f"*Losing Trades:*   {metrics.get('losing_trades', 0)}",
            f"*Win Rate:*         {metrics.get('win_rate', 0):.1f}%",
            f"*Avg Win:*         `${metrics.get('avg_win', 0):.2f}`",
            f"*Avg Loss:*        `${metrics.get('avg_loss', 0):.2f}`",
            f"*Avg P&L/Trade:*   `${metrics.get('avg_pnl_per_trade', 0):.2f}`",
        ]
        
        return "\n".join(lines)
    
    def cmd_positions(self, chat_id: int, text: str, bot) -> str:
        """Current positions"""
        data = self._api_get('/api/positions')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        positions = data.get('positions', [])
        
        if not positions:
            return "📊 *POSITIONS*\n\nNo open positions"
        
        lines = ["📊 *OPEN POSITIONS*", "═" * 20, ""]
        
        total_pnl = 0
        for pos in positions:
            side = "🟢 LONG" if pos.get('size', 0) > 0 else "🔴 SHORT"
            pnl = pos.get('pnl', 0)
            total_pnl += pnl
            
            lines.append(f"*{pos.get('symbol', 'UNKNOWN')}*")
            lines.append(f"  {side} │ Size: {abs(pos.get('size', 0))}")
            lines.append(f"  Entry: ${pos.get('entry_price', 0):,.2f}")
            lines.append(f"  P&L:   ${pnl:,.2f} │ ROE: {pos.get('roe', 0):.2f}%")
            lines.append("")
        
        lines.append(f"*Total Unrealized:* `${total_pnl:,.2f}`")
        
        return "\n".join(lines)
    
    def cmd_portfolio(self, chat_id: int, text: str, bot) -> str:
        """Portfolio overview across all symbols"""
        positions = self._api_get('/api/positions')
        status = self._api_get('/api/status')
        pnl = self._api_get('/api/pnl/summary')
        
        if 'error' in positions:
            return f"❌ Error: {positions['error']}"
        
        lines = ["💼 *PORTFOLIO OVERVIEW*", "═" * 25, ""]
        
        # Capital
        capital = status.get('capital', 0)
        lines.append(f"*Total Capital:* `${capital:,.2f}`")
        
        # Daily P&L
        daily_pnl = pnl.get('daily', {}).get('total_pnl', 0)
        pnl_emoji = "🟢" if daily_pnl >= 0 else "🔴"
        lines.append(f"*Daily P&L:*   {pnl_emoji} ${daily_pnl:,.2f}")
        
        # Cumulative
        cum_pnl = pnl.get('cumulative', 0)
        cum_emoji = "🟢" if cum_pnl >= 0 else "🔴"
        lines.append(f"*Cumulative:*  {cum_emoji} ${cum_pnl:,.2f}")
        
        # Positions
        pos_list = positions.get('positions', [])
        if pos_list:
            lines.append("")
            lines.append("─── Positions ───")
            for pos in pos_list:
                side = "▲" if pos.get('size', 0) > 0 else "▼"
                lines.append(f"  {side} {pos.get('symbol')}: ${pos.get('pnl', 0):,.2f}")
        else:
            lines.append("")
            lines.append("─── No open positions ───")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Market Data Commands
    # =========================================================================
    
    def cmd_market(self, chat_id: int, text: str, bot) -> str:
        """Live market data"""
        status = self._api_get('/api/status')
        
        if 'error' in status:
            return f"❌ Error: {status['error']}"
        
        prices = status.get('prices', {})
        
        lines = ["📈 *MARKET DATA*", "═" * 20, ""]
        
        for symbol, price_data in prices.items():
            # Handle both formats: dict with price/change or direct float
            if isinstance(price_data, dict):
                price = price_data.get('price', 0)
                change_24h = price_data.get('change_24h', 0)
                high_24h = price_data.get('high_24h', 0)
                low_24h = price_data.get('low_24h', 0)
            else:
                price = float(price_data) if price_data else 0
                change_24h = 0
                high_24h = price
                low_24h = price
            
            emoji = "🟢" if change_24h >= 0 else "🔴"
            
            lines.append(f"*{symbol}*")
            lines.append(f"  Price:    ${price:,.2f}")
            lines.append(f"  24h:      {emoji} {change_24h:+.2f}%")
            lines.append(f"  High:     ${high_24h:,.2f}")
            lines.append(f"  Low:      ${low_24h:,.2f}")
            lines.append("")
        
        return "\n".join(lines)
    
    def cmd_price(self, chat_id: int, text: str, bot) -> str:
        """Quick price check"""
        parts = text.strip().split()
        symbol = parts[1].upper() if len(parts) > 1 else 'BTCUSDT'
        
        status = self._api_get('/api/status')
        prices = status.get('prices', {})
        
        price_data = prices.get(symbol)
        if not price_data:
            return f"❌ Symbol {symbol} not found"
        
        # Handle both formats
        if isinstance(price_data, dict):
            price = price_data.get('price', 0)
            change_24h = price_data.get('change_24h', 0)
            high_24h = price_data.get('high_24h', 0)
            low_24h = price_data.get('low_24h', 0)
        else:
            price = float(price_data) if price_data else 0
            change_24h = 0
            high_24h = price
            low_24h = price
        
        lines = [
            f"💵 *{symbol}*",
            "─" * 15,
            f"Price:    `${price:,.2f}`",
            f"24h:      `{change_24h:+.2f}%`",
            f"High:     `${high_24h:,.2f}`",
            f"Low:      `${low_24h:,.2f}`",
        ]
        
        return "\n".join(lines)
    
    # =========================================================================
    # Trade Execution Commands
    # Note: These require order API endpoints to be added to the dashboard
    # =========================================================================
    
    def cmd_long(self, chat_id: int, text: str, bot) -> str:
        """Open LONG position"""
        # Check if order API exists
        test = self._api_get('/api/order/test')
        
        parts = text.strip().split()
        quantity = float(parts[1]) if len(parts) > 1 else 0.001
        
        data = self._api_post('/api/order/long', {'quantity': quantity})
        
        if 'error' in data:
            # Return helpful message instead of error
            return f"""
⚠️ *Trade Execution Not Available*

The trading API endpoints need to be added to the dashboard.

Current available commands:
• /pnl     - P&L Dashboard
• /risk    - Risk Metrics  
• /market  - Live Prices
• /calc    - Position Calculator
• /trades  - Trade History

Use dashboard at http://35.177.250.139:8080 for trade execution.
"""
        
        order = data.get('order', {})
        return f"""
📈 *LONG OPENED*

✅ Order ID: `{order.get('orderId', 'N/A')}`
💰 Symbol: {order.get('symbol')}
📊 Quantity: {order.get('executedQty')}
💵 Price: ${float(order.get('avgPrice', 0)):,.2f}
"""
    
    def cmd_short(self, chat_id: int, text: str, bot) -> str:
        """Open SHORT position"""
        parts = text.strip().split()
        quantity = float(parts[1]) if len(parts) > 1 else 0.001
        
        data = self._api_post('/api/order/short', {'quantity': quantity})
        
        if 'error' in data:
            return f"""
⚠️ *Trade Execution Not Available*

Use dashboard at http://35.177.250.139:8080 for trade execution.
"""
        
        order = data.get('order', {})
        return f"""
📉 *SHORT OPENED*

✅ Order ID: `{order.get('orderId', 'N/A')}`
💰 Symbol: {order.get('symbol')}
📊 Quantity: {order.get('executedQty')}
💵 Price: ${float(order.get('avgPrice', 0)):,.2f}
"""
    
    def cmd_close(self, chat_id: int, text: str, bot) -> str:
        """Close position"""
        data = self._api_post('/api/order/close')
        
        if 'error' in data:
            return f"""
⚠️ *Trade Execution Not Available*

Use dashboard at http://35.177.250.139:8080 for trade execution.
"""
        
        return """
🛑 *POSITION CLOSED*

✅ All positions closed successfully
"""
    
    def cmd_buy(self, chat_id: int, text: str, bot) -> str:
        """Buy - same as long"""
        return self.cmd_long(chat_id, text, bot)
    
    def cmd_sell(self, chat_id: int, text: str, bot) -> str:
        """Sell - same as short"""
        return self.cmd_short(chat_id, text, bot)
    
    # =========================================================================
    # Position Sizing Commands
    # =========================================================================
    
    def cmd_calc(self, chat_id: int, text: str, bot) -> str:
        """
        Position size calculator
        Usage: /calc [account_size] [risk_pct] [entry_price] [stop_loss]
        Example: /calc 10000 1 50000 49000
        """
        parts = text.strip().split()
        
        if len(parts) < 5:
            return """
📐 *POSITION CALCULATOR*

Usage: `/calc [account] [risk%] [entry] [stop_loss]`

Example:
`/calc 10000 1 50000 49000`

→ Account: $10,000
→ Risk: 1%
→ Entry: $50,000
→ Stop: $49,000

*Output:* Recommended position size based on risk
"""
        
        try:
            account = float(parts[1])
            risk_pct = float(parts[2])
            entry = float(parts[3])
            stop = float(parts[4])
            
            # Calculate risk
            risk_amount = account * (risk_pct / 100)
            
            # Calculate position size
            price_risk = abs(entry - stop)
            if price_risk == 0:
                return "❌ Stop loss cannot be same as entry price"
            
            position_size = risk_amount / price_risk
            position_value = position_size * entry
            
            # Leverage required
            leverage = position_value / account if account > 0 else 0
            
            # Risk per contract
            risk_per_contract = price_risk
            
            lines = [
                "📐 *POSITION SIZE CALCULATOR*",
                "═" * 25,
                "",
                f"*Inputs:*",
                f"  Account:    ${account:,.2f}",
                f"  Risk:       {risk_pct}%",
                f"  Entry:      ${entry:,.2f}",
                f"  Stop Loss:  ${stop:,.2f}",
                "",
                f"*Results:*",
                f"  Risk Amount:    ${risk_amount:,.2f}",
                f"  Position Size:  {position_size:.6f}",
                f"  Position Value: ${position_value:,.2f}",
                f"  Required Leve:  {leverage:.1f}x",
                f"  Risk/Contract:  ${risk_per_contract:.2f}",
            ]
            
            return "\n".join(lines)
            
        except ValueError as e:
            return f"❌ Invalid parameters: {e}"
    
    def cmd_size(self, chat_id: int, text: str, bot) -> str:
        """Quick position size (uses current account)"""
        status = self._api_get('/api/status')
        account = status.get('capital', 10000)
        
        parts = text.strip().split()
        
        if len(parts) < 4:
            return f"""
📐 *QUICK SIZE*

Current Account: `${account:,.2f}`

Usage: `/size [risk%] [entry] [stop_loss]`

Example: `/size 1 50000 49000`
"""
        
        try:
            risk_pct = float(parts[1])
            entry = float(parts[2])
            stop = float(parts[3])
            
            risk_amount = account * (risk_pct / 100)
            price_risk = abs(entry - stop)
            position_size = risk_amount / price_risk
            
            return f"""
📐 *POSITION SIZE*

Account: `${account:,.2f}`
Risk: `{risk_pct}%` (${risk_amount:,.2f})

*Recommended Size:* `{position_size:.6f}` contracts

Entry: ${entry:,.2f}
Stop:  ${stop:,.2f}
Risk:  ${price_risk:.2f} per contract
"""
        except Exception as e:
            return f"❌ Error: {e}"
    
    # =========================================================================
    # Strategy Commands
    # =========================================================================
    
    def cmd_strategy(self, chat_id: int, text: str, bot) -> str:
        """Get or set active strategy"""
        parts = text.strip().split()
        
        if len(parts) < 2:
            # Show current strategy
            status = self._api_get('/api/status')
            current = status.get('active_strategy', 'unknown')
            return f"""
🎯 *CURRENT STRATEGY*

*Active:* `{current}`

Use `/strategy [name]` to switch
"""
        
        # Switch strategy
        new_strategy = parts[1]
        data = self._api_post('/api/switch_strategy', {'strategy': new_strategy})
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        return f"""
✅ *STRATEGY SWITCHED*

New strategy: `{new_strategy}`
"""
    
    def cmd_strategies(self, chat_id: int, text: str, bot) -> str:
        """List available strategies"""
        data = self._api_get('/api/strategies/performance')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        strategies = data.get('strategies', {})
        
        lines = ["📋 *AVAILABLE STRATEGIES*", "═" * 20, ""]
        
        for name, perf in strategies.items():
            pnl = perf.get('pnl', 0)
            trades = perf.get('trade_count', 0)
            win_rate = perf.get('win_rate', 0)
            emoji = "🟢" if pnl >= 0 else "🔴"
            
            lines.append(f"*{name}*")
            lines.append(f"  {emoji} P&L: ${pnl:,.2f} │ Trades: {trades}")
            lines.append(f"  Win Rate: {win_rate:.1f}%")
            lines.append("")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Performance Reports
    # =========================================================================
    
    def cmd_report(self, chat_id: int, text: str, bot) -> str:
        """Performance report"""
        parts = text.strip().split()
        period = parts[1].lower() if len(parts) > 1 else 'day'
        
        pnl = self._api_get('/api/pnl/summary')
        
        daily = pnl.get('daily', {})
        metrics = pnl.get('metrics', {})
        
        period_label = {
            'day': 'Today',
            'week': 'This Week', 
            'month': 'This Month'
        }.get(period, 'Today')
        
        lines = [
            f"📊 *PERFORMANCE REPORT*",
            f"_{period_label}_",
            "═" * 25,
            "",
            f"*Net P&L:*     `${daily.get('total_pnl', 0):+,.2f}`",
            f"*Trades:*      {daily.get('trade_count', 0)}",
            f"*Win Rate:*    {daily.get('win_rate', 0):.1f}%",
            "",
            "─── Risk Metrics ───",
            f"Sharpe:    `{metrics.get('sharpe_ratio', 0):.2f}`",
            f"Sortino:   `{metrics.get('sortino_ratio', 0):.2f}`",
            f"Max DD:    `${metrics.get('max_drawdown', 0):,.2f}`",
            f"Profit F:  `{metrics.get('profit_factor', 0):.2f}`",
        ]
        
        return "\n".join(lines)
    
    def cmd_history(self, chat_id: int, text: str, bot) -> str:
        """Trade history"""
        return self.cmd_trades(chat_id, text, bot)
    
    def cmd_trades(self, chat_id: int, text: str, bot) -> str:
        """Recent trades"""
        parts = text.strip().split()
        limit = int(parts[1]) if len(parts) > 1 else 10
        
        data = self._api_get('/api/trades', {'limit': limit})
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        trades = data.get('trades', [])
        
        if not trades:
            return "📜 *TRADE HISTORY*\n\nNo trades found"
        
        lines = ["📜 *RECENT TRADES*", "═" * 18, ""]
        
        for trade in trades[:10]:
            side = "▲" if trade.get('side') == 'BUY' else "▼"
            pnl = trade.get('pnl', 0)
            pnl_str = f"${pnl:+.2f}" if pnl else ""
            
            ts = trade.get('timestamp', '')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    ts = dt.strftime('%m/%d %H:%M')
                except Exception:
                    pass
            
            lines.append(
                f"{side} {trade.get('symbol')} "
                f"{trade.get('quantity', 0):.4f} "
                f"@ ${float(trade.get('price', 0)):,.0f} "
                f"{pnl_str}"
            )
            lines.append(f"   {ts}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # System Commands
    # =========================================================================
    
    def cmd_system(self, chat_id: int, text: str, bot) -> str:
        """System status"""
        status = self._api_get('/api/status')
        
        if 'error' in status:
            return f"❌ Error: {status['error']}"
        
        running = "🟢 Running" if status.get('running') else "🔴 Stopped"
        
        lines = [
            "⚙️ *SYSTEM STATUS*",
            "═" * 18,
            "",
            f"*Engine:*   {running}",
            f"*Symbol:*   {status.get('symbol', 'BTCUSDT')}",
            f"*Capital:*  ${status.get('capital', 0):,.2f}",
            f"*Leverage:* {status.get('leverage', 1)}x",
            f"*Mode:*     {'TESTNET' if status.get('testnet') else 'LIVE'}",
            "",
            f"*Strategy:* {status.get('active_strategy', 'N/A')}",
            f"*Regime:*   {status.get('current_regime', 'N/A')}",
        ]
        
        return "\n".join(lines)
    
    def cmd_health(self, chat_id: int, text: str, bot) -> str:
        """System health check"""
        data = self._api_get('/api/health')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        lines = [
            "🏥 *SYSTEM HEALTH*",
            "═" * 18,
            "",
            f"*Status:*   {data.get('status', 'unknown')}",
            f"*Uptime:*   {data.get('uptime', 'N/A')}",
            "",
            "─── Components ───",
        ]
        
        for comp, info in data.get('components', {}).items():
            status = "✅" if info.get('healthy') else "❌"
            lines.append(f"  {status} {comp}")
        
        return "\n".join(lines)
    
    def cmd_equity(self, chat_id: int, text: str, bot) -> str:
        """Show equity curve data"""
        data = self._api_get('/api/pnl/summary')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        daily = data.get('daily', {})
        cumulative = data.get('cumulative', 0)
        
        lines = [
            "📈 *EQUITY CURVE*",
            "═" * 18,
            "",
            f"*Daily P&L:*  ${daily.get('total_pnl', 0):.2f}",
            f"*Cumulative:* ${cumulative:.2f}",
            f"*Trade Count:* {daily.get('trade_count', 0)}",
        ]
        
        return "\n".join(lines)
    
    def cmd_drawdown(self, chat_id: int, text: str, bot) -> str:
        """Show drawdown metrics"""
        data = self._api_get('/api/pnl/summary')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        metrics = data.get('metrics', {})
        
        lines = [
            "📉 *DRAWDOWN ANALYSIS*",
            "═" * 22,
            "",
            f"*Max Drawdown:* ${metrics.get('max_drawdown', 0):.2f}",
            f"*Volatility:*   {metrics.get('volatility', 0):.2f}",
            f"*Sortino Ratio:* {metrics.get('sortino_ratio', 0):.2f}",
        ]
        
        return "\n".join(lines)
    
    def cmd_winrate(self, chat_id: int, text: str, bot) -> str:
        """Show win rate analysis"""
        data = self._api_get('/api/pnl/summary')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        daily = data.get('daily', {})
        metrics = data.get('metrics', {})
        
        lines = [
            "🎯 *WIN RATE ANALYSIS*",
            "═" * 22,
            "",
            f"*Daily Win Rate:* {daily.get('win_rate', 0):.1f}%",
            f"*Win Count:*      {daily.get('win_count', 0)}",
            f"*Loss Count:*     {daily.get('loss_count', 0)}",
            f"*Avg Win:*        ${metrics.get('avg_win', 0):.2f}",
            f"*Avg Loss:*       ${metrics.get('avg_loss', 0):.2f}",
            f"*Profit Factor:*  {metrics.get('profit_factor', 0):.2f}",
        ]
        
        return "\n".join(lines)
    
    def cmd_metrics(self, chat_id: int, text: str, bot) -> str:
        """Show comprehensive metrics"""
        pnl_data = self._api_get('/api/pnl/summary')
        learning_data = self._api_get('/api/learning')
        
        metrics = pnl_data.get('metrics', {})
        sl = learning_data.get('self_learning', {})
        
        lines = [
            "📊 *PERFORMANCE METRICS*",
            "═" * 24,
            "",
            f"*Sharpe Ratio:*  {metrics.get('sharpe_ratio', 0):.2f}",
            f"*Sortino Ratio:* {metrics.get('sortino_ratio', 0):.2f}",
            f"*Calmar Ratio:*  {metrics.get('calmar_ratio', 0):.2f}",
            f"*Win Rate:*      {metrics.get('win_rate', 0):.1f}%",
            f"*Profit Factor:* {metrics.get('profit_factor', 0):.2f}",
            f"*Total Trades:*  {metrics.get('total_trades', 0)}",
            "",
            "🧠 *MODEL LEARNING*",
            "─" * 24,
            f"*Retrains:*   {sl.get('retrain_count', 0)}",
            f"*Accuracy:*   {sl.get('model_accuracy', 0)*100:.1f}%",
            f"*Buffer:*     {sl.get('buffer_size', 0)}/{sl.get('min_samples_required', 50)}",
        ]
        
        return "\n".join(lines)
    
    def cmd_regime(self, chat_id: int, text: str, bot) -> str:
        """Show current market regime"""
        data = self._api_get('/api/regime')
        
        if 'error' in data:
            return f"❌ Error: {data['error']}"
        
        regime = data.get('regime', 'unknown')
        strategy = data.get('strategy', 'unknown')
        
        emoji = {'bull': '🐂', 'bear': '🐻', 'volatile': '⚡', 'sideways': '➡️'}.get(regime, '❓')
        
        lines = [
            f"🌊 *MARKET REGIME*",
            "═" * 18,
            "",
            f"*Regime:*  {emoji} {regime.upper()}",
            f"*Strategy:* {strategy}",
        ]
        
        return "\n".join(lines)
    
    def cmd_learning(self, chat_id: int, text: str, bot) -> str:
        """Model Learning Status - shows self-learning engine metrics"""
        data = self._api_get('/api/learning')
        
        if 'error' in data:
            return f"Error: {data.get('error', 'Failed to fetch learning data')}"
        
        sl = data.get('self_learning', {})
        ml = data.get('meta_learning', {})
        win_rate = data.get('recent_win_rate', 0) * 100
        current_regime = data.get('current_regime', 'unknown')
        top_features = data.get('top_features', [])
        decisions = data.get('decisions', {})
        
        buffer = sl.get('buffer_size', 0)
        min_req = sl.get('min_samples_required', 50)
        progress = min(100, int(buffer / min_req * 100)) if min_req > 0 else 0
        bar_len = 10
        filled = int(bar_len * progress / 100)
        bar = '=' * filled + '-' * (bar_len - filled)
        
        status = "Training" if sl.get('is_training') else (
            "Ready" if buffer >= min_req else f"Building {progress}%"
        )
        
        accuracy = sl.get('model_accuracy', 0) * 100
        retrain_count = sl.get('retrain_count', 0)
        time_left = sl.get('time_to_retrain', 0)
        
        # Format feature importance
        feature_str = ""
        if top_features:
            feature_lines = ["  Top Indicators Learned:"]
            for f in top_features[:5]:
                weight_pct = f.get('weight', 0) * 100
                feature_lines.append(f"    {f.get('name', 'unknown')}: {weight_pct:.0f}%")
            feature_str = "\n".join(feature_lines)
        
        # Format regime performance
        regime_perf = ml.get('regime_performance', {})
        regime_str = ""
        if regime_perf:
            regime_lines = ["  Regime Performance:"]
            for regime, perf in regime_perf.items():
                wr = perf.get('win_rate', 0) * 100
                trades = perf.get('trades', 0)
                regime_lines.append(f"    {regime}: {wr:.0f}% ({trades} trades)")
            regime_str = "\n".join(regime_lines)
        
        # Format decision breakdown
        decision_str = ""
        if decisions:
            buy_w = decisions.get('buy_signals', {}).get('wins', 0)
            buy_l = decisions.get('buy_signals', {}).get('losses', 0)
            sell_w = decisions.get('sell_signals', {}).get('wins', 0)
            sell_l = decisions.get('sell_signals', {}).get('losses', 0)
            
            if buy_w + buy_l > 0 or sell_w + sell_l > 0:
                decision_lines = ["  Decision Breakdown:"]
                if buy_w + buy_l > 0:
                    buy_wr = buy_w / (buy_w + buy_l) * 100 if (buy_w + buy_l) > 0 else 0
                    decision_lines.append(f"    Buy Signals: {buy_w}W / {buy_l}L ({buy_wr:.0f}%)")
                if sell_w + sell_l > 0:
                    sell_wr = sell_w / (sell_w + sell_l) * 100 if (sell_w + sell_l) > 0 else 0
                    decision_lines.append(f"    Sell Signals: {sell_w}W / {sell_l}L ({sell_wr:.0f}%)")
                decision_str = "\n".join(decision_lines)
        
        lines = [
            "🧠 MODEL LEARNING STATUS",
            "=" * 30,
            "",
            "📊 Self-Learning Engine:",
            f"  Buffer: {buffer}/{min_req} [{bar}]",
            f"  Retrains: {retrain_count}",
            f"  Accuracy: {accuracy:.1f}%",
            f"  Win Rate: {win_rate:.1f}%",
            f"  Status: {status}",
            "",
            f"🌊 Current Regime: {current_regime.upper()}",
            "",
            "🧠 Meta-Learning:",
            f"  Regime: {ml.get('current_regime', 'unknown')}",
        ]
        
        if regime_str:
            lines.append(regime_str)
        
        if feature_str:
            lines.extend(["", feature_str])
        
        if decision_str:
            lines.extend(["", decision_str])
        
        lines.extend([
            "",
            f"📊 Dashboard: {self.dashboard_url}",
        ])
        
        return "\n".join(lines)
    
    def cmd_help(self, chat_id: int, text: str, bot) -> str:
        """Show help message with all available commands"""
        lines = [
            "📖 *QUANT BOT COMMANDS*",
            "═" * 25,
            "",
            "─── P&L & Risk ───",
            "/pnl       - Full P&L dashboard",
            "/risk      - Risk metrics (Sharpe, DD)",
            "/positions - Current positions",
            "/portfolio - Portfolio overview",
            "",
            "─── Market Data ───",
            "/market    - Live market prices",
            "/price     - Single symbol price",
            "",
            "─── Position Sizing ───",
            "/calc      - Position size calculator",
            "/size      - Quick size (uses account)",
            "",
            "─── Strategy ───",
            "/strategy  - Get/set active strategy",
            "/strategies - List all strategies",
            "",
            "─── Performance ───",
            "/report    - Performance report",
            "/trades    - Trade history",
            "/history   - Recent trades",
            "",
            "─── Analytics (NEW) ───",
            "/equity    - Equity curve data",
            "/drawdown  - Drawdown analysis",
            "/winrate   - Win rate breakdown",
            "/metrics   - Full metrics",
            "/regime    - Market regime",
            "",
            "─── Model Learning ───",
            "/learning  - Self-learning status",
            "",
            "─── System ───",
            "/system    - System status",
            "/health    - Health check",
            "",
            "_All commands connect to paper trading engine_"
        ]
        
        return "\n".join(lines)
