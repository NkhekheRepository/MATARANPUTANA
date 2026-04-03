"""
Paper Trading Engine
===================
Main trading engine for autonomous quant trading system.
Integrates VNPY with self-healing, self-learning, and adaptive learning.
Uses event bus for loose coupling between layers.
"""

import os
import sys
import time
import threading
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .layers.event_bus import (
    get_event_bus, EventType, 
    publish_market_data_update, publish_risk_check,
    publish_signal_generated, publish_regime_detected,
    publish_order_executed, publish_health_check,
    publish_command_received
)

from .metrics import (
    update_trading_metrics, update_position_metrics, 
    update_capital_metrics, record_order_placed, record_order_filled
)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


class PaperTradingEngine:
    """
    Main paper trading engine that orchestrates all layers.
    
    Architecture:
    - Layer 1: Data & Connectivity
    - Layer 2: Risk Management
    - Layer 3: Signal Generation
    - Layer 4: Intelligence (ML Ensemble)
    - Layer 5: Execution (VNPY)
    - Layer 6: Orchestration (Self-Healing)
    - Layer 7: Command & Control
    """
    
    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.config = self._load_config()
        
        self.running = False
        self.update_thread: Optional[threading.Thread] = None
        
        self.capital = self.config['trading']['initial_capital']
        self.leverage = self.config['trading']['leverage']
        self.update_interval = self.config['trading']['update_interval']
        
        # Positions are managed exclusively by OrderManager — single source of truth
        self.daily_pnl = 0.0
        self.daily_start_capital = self.capital
        
        self.strategies: Dict[str, Any] = {}
        self.active_strategy: Optional[str] = None
        self.current_regime = "sideways"
        
        self._pending_signals: Dict[str, Dict[str, Any]] = {}
        self._entry_prices: Dict[str, float] = {}
        self._signal_history: Dict[str, List[str]] = {}
        self._signal_stability_required = 5  # Increased to require 5 consecutive signals
        self._last_trade_time: Dict[str, float] = {}
        self._trade_cooldown = 120  # Increased to 120s to prevent overtrading
        
        # Risk breach cooldown to prevent spam loop
        self._last_breach_time = 0.0
        self._breach_cooldown = 300  # 5 minutes between breach resets
        
        self._init_layers()
        self._init_strategies()
        
        logger.info(f"PaperTradingEngine initialized: capital=${self.capital}, leverage={self.leverage}x")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded config from {self.config_path}")
        return config
    
    def _init_layers(self):
        """Initialize all layers using VNPyDataBridge and event bus."""
        from .layers.layer1_data.vnpy_bridge import VNPyDataBridge, get_data_bridge
        from .layers.layer2_risk.risk_engine import RiskEngine
        from .layers.layer2_risk.circuit_breaker import TradingCircuitBreaker
        from .layers.layer2_risk.emergency_stop import EmergencyStop, EmergencyStopManager
        from .layers.layer3_signals.signal_aggregator import SignalAggregator
        from .layers.layer4_intelligence.ensemble import IntelligenceEnsemble
        from .layers.layer5_execution.order_manager import OrderManager
        from .layers.layer6_orchestration.health_monitor import HealthMonitor
        from .layers.layer6_orchestration.integrated_healing import IntegratedHealingManager
        
        # Initialize VNPyDataBridge (replaces custom Binance clients)
        data_config = self.config.get('data', {})
        data_config['symbols'] = self.config.get('trading', {}).get('symbols', ['BTCUSDT'])
        self.data_bridge = get_data_bridge(data_config)
        
        self.risk_engine = RiskEngine(self.config.get('risk', {}))
        self.circuit_breaker = TradingCircuitBreaker()
        self.signal_aggregator = SignalAggregator()
        self.intelligence = IntelligenceEnsemble(self.config.get('intelligence', {}))
        self.order_manager = OrderManager(self.config.get('trading', {}))
        self.health_monitor = HealthMonitor(self.config.get('orchestration', {}))
        self.integrated_healing = IntegratedHealingManager(self.config.get('orchestration', {}))
        
        # Black Swan Layer: Emergency Stop
        self.bs_emergency_stop = EmergencyStop(self.config.get('risk', {}).get('black_swan', {}))
        
        # Use the singleton event bus — all layers share one instance
        self.event_bus = get_event_bus()
        
        from .layers.layer7_control.self_awareness import SelfAwarenessEngine
        self.self_awareness = SelfAwarenessEngine(
            self.config.get('orchestration', {}),
            engine_ref=self
        )
        
        from .layers.layer7_control.goal_manager import GoalManager
        from .layers.layer7_control.healing_effectiveness import HealingEffectivenessTracker
        from .layers.layer4_intelligence.meta_learner import MetaLearner
        
        self.goal_manager = GoalManager(self.config.get('goals', {}))
        self.healing_effectiveness = HealingEffectivenessTracker(self.config.get('healing_effectiveness', {}))
        self.meta_learner = MetaLearner(self.config.get('meta_learning', {}))
        
        from .layers.layer7_control.telegram_alert_handler import TelegramAlertHandler
        self.telegram_alert_handler = TelegramAlertHandler()
        
        self._wire_event_subscribers()
        self._wire_order_callback()
        self._register_healing_components()
        self.telegram_alert_handler.subscribe()
        
        if self.order_manager.mode == 'testnet':
            synced = self.order_manager.sync_positions_from_exchange()
            logger.info(f"Synced {synced} positions from testnet on startup")
        
        logger.info("All layers initialized with VNPyDataBridge")
    
    def _init_strategies(self):
        """Initialize trading strategies from config."""
        for strategy_config in self.config.get('strategies', []):
            if strategy_config.get('enabled', False):
                self.strategies[strategy_config['name']] = {
                    'class': strategy_config['class'],
                    'vt_symbol': strategy_config['vt_symbol'],
                    'parameters': strategy_config.get('parameters', {}),
                    'enabled': True
                }
                
                if self.active_strategy is None:
                    self.active_strategy = strategy_config['name']
        
        logger.info(f"Initialized strategies: {list(self.strategies.keys())}")
    
    def _wire_event_subscribers(self):
        """Subscribe to events so layers react through the event bus."""
        self.event_bus.subscribe(
            [EventType.RISK_LIMIT_BREACH, EventType.RISK_CHECK_PERFORMED],
            self._on_risk_event
        )
        self.event_bus.subscribe(
            [EventType.REGIME_DETECTED],
            self._on_regime_event
        )
        self.event_bus.subscribe(
            [EventType.SIGNAL_GENERATED],
            self._on_signal_event
        )
        self.event_bus.subscribe(
            [EventType.ORDER_EXECUTED],
            self._on_order_event
        )
        self.event_bus.subscribe(
            [EventType.SYSTEM_ERROR, EventType.CIRCUIT_BREAKER_TRIGGERED],
            self._on_error_event
        )
        logger.info("Event bus subscribers wired")
    
    def _wire_order_callback(self):
        """Register callback on OrderManager to track PnL and capital from fills."""
        self.order_manager.add_order_callback(self._on_order_filled)
    
    def _register_healing_components(self):
        """Register all components for integrated healing."""
        self.integrated_healing.register_component(
            name="data_bridge",
            check_func=lambda: self.data_bridge.is_connected() if hasattr(self, 'data_bridge') else False,
            restart_func=self._restart_data_bridge,
            critical=True
        )
        
        self.integrated_healing.register_component(
            name="intelligence",
            check_func=lambda: hasattr(self, 'intelligence') and self.intelligence is not None,
            restart_func=self._restart_intelligence,
            critical=True
        )
        
        self.integrated_healing.register_component(
            name="order_manager",
            check_func=lambda: hasattr(self, 'order_manager') and self.order_manager is not None,
            restart_func=self._restart_order_manager,
            critical=True
        )
        
        logger.info("All components registered for integrated healing")
    
    def _restart_data_bridge(self):
        """Restart data bridge connection."""
        logger.info("Restarting data bridge...")
        if hasattr(self, 'data_bridge'):
            self.data_bridge.disconnect()
            time.sleep(2)
            self.data_bridge.connect()
    
    def _restart_intelligence(self):
        """Restart intelligence module."""
        logger.info("Restarting intelligence module...")
        from .layers.layer4_intelligence.ensemble import IntelligenceEnsemble
        self.intelligence = IntelligenceEnsemble(self.config.get('intelligence', {}))
    
    def _restart_order_manager(self):
        """Restart order manager."""
        logger.info("Restarting order manager...")
        from .layers.layer5_execution.order_manager import OrderManager
        self.order_manager = OrderManager(self.config.get('trading', {}))
        self._wire_order_callback()
    
    def _on_order_filled(self, order):
        """Called on every order fill — updates daily_pnl and capital, feeds learning loop."""
        from .layers.layer5_execution.order_manager import OrderStatus
        
        if order.status == OrderStatus.FILLED:
            position = self.order_manager.get_position(order.symbol)
            position_size = abs(position.get('size', 0))
            
            if order.pnl != 0:
                self.daily_pnl += order.pnl
                self.capital += order.pnl
                
                entry_price = self._entry_prices.get(order.symbol, order.avg_fill_price or 0.0)
                self.intelligence.record_trade_outcome(
                    symbol=order.symbol,
                    action='buy' if order.side == 'sell' else 'sell',
                    pnl=order.pnl,
                    entry_price=entry_price,
                    exit_price=order.avg_fill_price,
                )
                self.self_awareness.record_trade({
                    'pnl': order.pnl,
                    'win_rate': 1.0 if order.pnl > 0 else 0.0,
                })
                
                # Update goal manager with trade result
                self.goal_manager.update_trade_result(order.pnl, self.capital)
                
                # Black Swan Feature 10: Fail-Safe tracking
                fail_safe_triggered = self.bs_emergency_stop.record_trade_pnl(order.pnl)
                if fail_safe_triggered:
                    logger.critical(f"FAIL-SAFE TRIGGERED: {self.bs_emergency_stop.trigger_reason}")
                    self._close_all_positions()
                
                # Black Swan Feature 4: Slippage Feedback
                predicted_price = self._entry_prices.get(order.symbol, 0)
                if predicted_price > 0:
                    self.order_manager.record_slippage(
                        symbol=order.symbol,
                        predicted_price=predicted_price,
                        actual_price=order.avg_fill_price,
                        side=order.side
                    )
                
                if position_size == 0:
                    self._entry_prices.pop(order.symbol, None)
                    
                    # Publish order executed event for Telegram alert
                    try:
                        from .layers.event_bus import get_event_bus, OrderExecutedEvent, EventType
                        bus = get_event_bus()
                        bus.publish(OrderExecutedEvent(
                            event_type=EventType.ORDER_EXECUTED,
                            symbol=order.symbol,
                            action=order.side.upper(),
                            quantity=abs(position_size),
                            price=order.avg_fill_price or 0,
                            order_id=order.order_id,
                        ))
                    except Exception as e:
                        logger.debug(f"Could not publish order event: {e}")
            
            if position_size > 0 and position.get('entry_price', 0) > 0:
                self._entry_prices[order.symbol] = position['entry_price']
            
            fee_deducted = self.order_manager.total_fees - getattr(self, '_last_tracked_fees', 0)
            if fee_deducted > 0:
                self.capital -= fee_deducted
                self._last_tracked_fees = self.order_manager.total_fees
            
            logger.info(f"PnL updated: daily_pnl=${self.daily_pnl:.2f}, capital=${self.capital:.2f}")
    
    def _on_risk_event(self, event):
        """React to risk events."""
        if hasattr(event, 'allowed') and not event.allowed:
            logger.warning(f"Risk breach via event bus: {getattr(event, 'reason', 'unknown')}")
            # Break the event loop: do NOT re-publish RISK_LIMIT_BREACH
            # TelegramAlertHandler handles notifications directly
            self._close_all_positions()
    
    def _on_regime_event(self, event):
        """React to regime change events."""
        regime = getattr(event, 'regime', None)
        confidence = getattr(event, 'confidence', 0.5)
        if regime and regime != self.current_regime:
            logger.info(f"Regime change via event bus: {self.current_regime} -> {regime} (conf={confidence:.2f})")
            self.current_regime = regime
            self._switch_strategy(regime)
            
            # Notify meta-learner about regime change
            self.meta_learner.transition_to_regime(regime, confidence)
    
    def _on_signal_event(self, event):
        """Process signal events from any source — drives execution."""
        action = getattr(event, 'action', 'HOLD')
        confidence = getattr(event, 'confidence', 0.0)
        symbol = getattr(event, 'symbol', 'BTCUSDT')
        indicators = getattr(event, 'indicators', {})
        
        logger.info(f"Signal via event bus: {action} {symbol} (conf={confidence:.2f})")
        
        if action == 'HOLD' or confidence < 0.4:
            logger.debug(f"Signal filtered: action={action}, confidence={confidence:.2f} < 0.4")
            return
        
        now = time.time()
        last_trade = self._last_trade_time.get(symbol, 0)
        if now - last_trade < self._trade_cooldown:
            logger.debug(f"Signal cooldown active for {symbol}: {now - last_trade:.0f}s < {self._trade_cooldown}s")
            return
        
        if not self.running:
            return
        
        position = self.order_manager.get_position(symbol)
        position_size = position.get('size', 0)
        abs_size = abs(position_size)
        side = position.get('side')
        
        price = self.data_bridge.get_price(symbol) if hasattr(self, 'data_bridge') else 0
        
        if price <= 0:
            logger.warning(f"No valid price for signal execution: {symbol}")
            return
        
        # =========================================================================
        # BLACK SWAN PRE-EXECUTION GATE
        # =========================================================================

        # Feature 0: Hard Expectancy Gate (FIRST — blocks all if models untrained)
        expectancy_result = self.risk_engine.check_expectancy(
            trade_logger=self.order_manager.trade_logger if hasattr(self.order_manager, 'trade_logger') else None,
            min_trades=10,
            min_win_rate=15.0,
            min_expectancy=0.0
        )
        if not expectancy_result.get('allowed', True):
            logger.critical(f"EXPECTANCY GATE: {expectancy_result.get('reason')}")
            return
        
        # Feature 10: Fail-Safe check
        if self.bs_emergency_stop.is_triggered():
            logger.critical(f"EMERGENCY STOP ACTIVE: {self.bs_emergency_stop.trigger_reason}")
            return
        
        # Feature 5: Regime Collapse Detection
        regime_status = self.risk_engine.detect_regime_collapse()
        if regime_status.get('defensive_mode'):
            logger.warning(f"DEFENSIVE MODE: {regime_status.get('reason')}")
        
        # Feature 9: Liquidity & Market Stress Filter
        market_data_check = {
            'spread_pct': indicators.get('spread_pct', 0),
            'volume_ratio': indicators.get('volume_ratio', 1.0),
            'order_book_depth': indicators.get('order_book_depth', 1.0)
        }
        liquidity_result = self.risk_engine.check_market_liquidity(market_data_check)
        if not liquidity_result.get('allowed', True):
            logger.warning(f"Trade rejected by liquidity filter: {liquidity_result.get('reason')}")
            return
        
        # Feature 2: Model Uncertainty Penalty
        uncertainty_result = self.intelligence.calculate_model_uncertainty(
            {**market_data_check, 'price': price, 'symbol': symbol}
        )
        if not uncertainty_result.get('allowed', True):
            logger.warning(f"Trade rejected by model uncertainty: {uncertainty_result.get('reason')}")
            return
        
        # Feature 3: Edge Decay Function
        signal_time = getattr(event, 'timestamp', time.time())
        edge_result = self.signal_aggregator.apply_edge_decay(
            {'action': action.lower(), 'confidence': confidence}, signal_time
        )
        if edge_result.get('action') is None:
            logger.warning(f"Trade rejected by edge decay: {edge_result.get('reason')}")
            return
        
        # Feature 12: Execution Conservatism (final conviction gate)
        conservatism_result = self.risk_engine.check_conservatism(
            uncertainty_result, edge_result
        )
        if not conservatism_result.get('allowed', True):
            logger.warning(f"Trade rejected by conservatism: {conservatism_result.get('reason')}")
            return
        
        # Feature 1: CVaR-based Tail Risk
        positions = self.order_manager.get_all_positions()
        current_prices = {sym: self.data_bridge.get_price(sym) for sym in positions}
        tail_result = self.risk_engine.check_tail_risk(positions, self.capital, current_prices)
        if not tail_result.get('allowed', True):
            logger.warning(f"Trade rejected by tail risk: {tail_result.get('reason')}")
            return
        
        # Feature 7: Risk of Ruin
        pnl_summary = self.order_manager.trade_logger.get_pnl_summary() if hasattr(self.order_manager, 'trade_logger') else {}
        daily_stats = pnl_summary.get('daily', {})
        trade_count = daily_stats.get('trade_count', 1)
        win_count = daily_stats.get('win_count', 0)
        win_rate = (win_count / trade_count) if trade_count > 0 else 0.5
        total_pnl = daily_stats.get('total_pnl', 0)
        avg_pnl = (total_pnl / trade_count) if trade_count > 0 else 0
        
        ruin_result = self.risk_engine.calculate_ruin_probability(
            win_rate=win_rate,
            avg_win=max(avg_pnl, 1) if avg_pnl > 0 else 1,
            avg_loss=abs(min(avg_pnl, -1)) if avg_pnl < 0 else 1,
            capital=self.capital,
            min_capital_threshold=self.risk_engine.black_swan.get('min_capital_threshold', 1000)
        )
        if not ruin_result.get('allowed', True):
            logger.critical(f"Trade rejected by risk of ruin: {ruin_result.get('reason')}")
            return
        
        # =========================================================================
        # END BLACK SWAN GATE
        # =========================================================================
        
        action_lower = action.lower()
        
        if action_lower == 'close':
            if abs_size == 0:
                logger.debug(f"Skipping close signal: no position in {symbol}")
                return
            quantity = abs_size
            self.order_manager.close_position(symbol, price, quantity)
            self._last_trade_time[symbol] = time.time()
            logger.info(f"Closed position: {symbol} {quantity} @ {price}")
            return
        
        if action_lower == 'buy':
            if side == 'long':
                logger.debug(f"Skipping buy signal: already long {abs_size} {symbol}")
                return
            if side == 'short':
                quantity = abs_size
                self.order_manager.close_position(symbol, price, quantity)
                self._last_trade_time[symbol] = time.time()
                logger.info(f"Closed short to flip long: {symbol} {quantity} @ {price}")
                return
            quantity = self._calculate_position_size(symbol)
            self.order_manager.execute(signal='buy', symbol=symbol, price=price, size=quantity, leverage=self.leverage)
            self._last_trade_time[symbol] = time.time()
            logger.info(f"Opened long: {symbol} {quantity} @ {price}")
            return
        
        if action_lower == 'sell':
            if side == 'short':
                logger.debug(f"Skipping sell signal: already short {abs_size} {symbol}")
                return
            if side == 'long':
                quantity = abs_size
                self.order_manager.close_position(symbol, price, quantity)
                self._last_trade_time[symbol] = time.time()
                logger.info(f"Closed long to flip short: {symbol} {quantity} @ {price}")
                return
            quantity = self._calculate_position_size(symbol)
            self.order_manager.execute(signal='sell', symbol=symbol, price=price, size=quantity, leverage=self.leverage)
            self._last_trade_time[symbol] = time.time()
            logger.info(f"Opened short: {symbol} {quantity} @ {price}")
            return
    
    def _on_order_event(self, event):
        """Track executed orders for audit trail."""
        symbol = getattr(event, 'symbol', '')
        action = getattr(event, 'action', '')
        price = getattr(event, 'price', 0)
        quantity = getattr(event, 'quantity', 0)
        logger.info(f"Order via event bus: {action} {symbol} {quantity} @ {price}")
    
    def _on_error_event(self, event):
        """React to system errors and circuit breaker trips."""
        logger.warning(f"System error via event bus: {event}")
    
    def start(self):
        """Start the trading engine."""
        if self.running:
            logger.warning("Engine already running")
            return
        
        # Publish startup event
        publish_command_received("start_engine", "engine", {
            "capital": self.capital,
            "leverage": self.leverage
        })
        
        self.running = True
        
        # Load PnL from TradeLogger if available
        if hasattr(self.order_manager, 'trade_logger'):
            try:
                summary = self.order_manager.trade_logger.get_pnl_summary()
                self.daily_pnl = summary.get('daily', {}).get('total_pnl', 0.0)
                logger.info(f"Loaded daily_pnl=${self.daily_pnl:.2f} from TradeLogger")
            except Exception as e:
                logger.warning(f"Could not load PnL from TradeLogger: {e}")
        
        # Start VNPyDataBridge (replaces data_client.connect())
        self.data_bridge.connect()
        
        self.health_monitor.start()
        self.self_awareness.start()
        
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        # Publish health check event
        publish_health_check("engine", "healthy", {
            "status": "started",
            "data_bridge": "connected" if self.data_bridge.is_connected() else "disconnected"
        })
        
        # Send Telegram startup notification
        self._send_startup_notification()
        
        logger.info("PaperTradingEngine started with VNPyDataBridge")
    
    def _send_startup_notification(self):
        """Send Telegram startup notification with HMM status."""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            import telegram_notify as tn
            
            hmm_status = "trained" if getattr(self.intelligence.hmm, 'model_trained', False) else "pending (will train on first 100 bars)"
            message = (
                f"🚀 *Paper Trading Engine Started*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Capital: ${self.capital:,.2f}\n"
                f"⚡ Leverage: {self.leverage}x\n"
                f"🧠 HMM: {hmm_status}\n"
                f"📊 Regime: {self.current_regime}\n"
                f"🎯 Strategy: {self.active_strategy}\n"
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            tn.send_to_admin(message)
            logger.info("Telegram startup notification sent")
        except Exception as e:
            logger.warning(f"Failed to send startup notification: {e}")
    
    def stop(self):
        """Stop the trading engine."""
        if not self.running:
            logger.warning("Engine not running")
            return
        
        # Publish shutdown event
        publish_command_received("stop_engine", "engine", {})
        
        self.running = False
        
        if self.update_thread:
            self.update_thread.join(timeout=5)
        
        # Stop VNPyDataBridge (replaces data_client.disconnect())
        self.data_bridge.disconnect()
        self.health_monitor.stop()
        
        self._close_all_positions()
        
        # Publish health check event
        publish_health_check("engine", "stopped", {
            "status": "stopped",
            "data_bridge": "disconnected"
        })
        
        logger.info("PaperTradingEngine stopped")
    
    def _update_loop(self):
        """Main update loop running at configured interval."""
        while self.running:
            try:
                self._process_update()
            except Exception as e:
                logger.error(f"Update loop error: {e}")
            
            time.sleep(self.update_interval)
    
    def _process_update(self):
        """Process one update cycle with event bus integration."""
        all_data = self.data_bridge.get_all_latest() if hasattr(self, 'data_bridge') else {}
        
        if not all_data:
            logger.warning("No market data available")
            return
        
        symbols = self.config.get('trading', {}).get('symbols', ['BTCUSDT'])
        
        for sym in symbols:
            sym = sym.upper()
            market_data = all_data.get(sym)
            if not market_data:
                continue
            
            if hasattr(self, 'data_bridge'):
                buffer = self.data_bridge.get_buffer(sym, n=100)
                market_data['price_history'] = [bar.get('close', 0) for bar in buffer if bar.get('close', 0) > 0]
                market_data['volume_history'] = [bar.get('volume', 0) for bar in buffer]
            
            publish_market_data_update(
                symbol=sym,
                price=market_data.get('close', 0),
                volume=market_data.get('volume', 0),
                timestamp_ms=market_data.get('timestamp', int(time.time() * 1000)),
                data=market_data
            )
        
        primary_symbol = symbols[0].upper()
        primary_data = all_data.get(primary_symbol, {})
        self._detect_regime(primary_data)
        
        # Black Swan Feature 5: Track volatility for regime collapse detection
        for sym in symbols:
            sym = sym.upper()
            md = all_data.get(sym, {})
            price = md.get('close', md.get('price', 0))
            if price > 0:
                self.risk_engine.update_volatility(price)
        
        for sym in symbols:
            sym = sym.upper()
            market_data = all_data.get(sym)
            if not market_data:
                continue
            
            signals = self._generate_signals(market_data)
            validated_signals = self._intelligence_validate(signals, market_data)
            
            v_action = validated_signals.get('ensemble_action', validated_signals.get('action', ''))
            v_confidence = validated_signals.get('confidence', 0.0)
            symbol = sym
            
            if symbol not in self._signal_history:
                self._signal_history[symbol] = []
            
            self._signal_history[symbol].append(v_action.lower() if v_action else 'hold')
            max_history = self._signal_stability_required + 1
            if len(self._signal_history[symbol]) > max_history:
                self._signal_history[symbol] = self._signal_history[symbol][-max_history:]
            
            recent_signals = self._signal_history[symbol]
            is_stable = (
                len(recent_signals) >= self._signal_stability_required and
                len(set(recent_signals[-self._signal_stability_required:])) == 1
            )
            
            if v_action and v_action.lower() != 'hold' and is_stable:
                logger.info(f"Signal confirmed stable: {v_action} {symbol} ({self._signal_stability_required}x)")
                publish_signal_generated(
                    symbol=symbol,
                    action=v_action.upper(),
                    confidence=v_confidence,
                    indicators=validated_signals.get('indicators', {}),
                )
            elif v_action and v_action.lower() != 'hold':
                logger.debug(f"Signal pending ({len(recent_signals)}/{self._signal_stability_required}): {v_action} {symbol}")
        
        risk_check = self.risk_engine.check_risk(
            self.capital,
            self.daily_pnl,
            self.order_manager.get_all_positions(),
            self.daily_start_capital
        )
        
        # Publish risk check event
        publish_risk_check(
            capital=self.capital,
            daily_pnl=self.daily_pnl,
            positions=self.order_manager.get_all_positions(),
            risk_score=risk_check.get('risk_score', 0),
            allowed=risk_check.get('allowed', False),
            reason=risk_check.get('reason', '')
        )
        
        if not risk_check['allowed']:
            logger.warning(f"Risk check failed: {risk_check['reason']}")
            self._handle_risk_breach(risk_check)
            return
        
        # =========================================================================
        # BLACK SWAN LAYER CHECKS (per update cycle)
        # =========================================================================
        
        # Feature 6: Correlation Shock Handling
        price_returns = {}
        for sym in symbols:
            sym = sym.upper()
            md = all_data.get(sym, {})
            hist = md.get('price_history', [])
            if len(hist) >= 10:
                returns = [(hist[i] - hist[i-1]) / hist[i-1] for i in range(1, len(hist)) if hist[i-1] > 0]
                if returns:
                    price_returns[sym] = returns
        
        if price_returns:
            corr_result = self.risk_engine.check_correlation_shock(price_returns)
            if corr_result.get('shock_detected'):
                logger.critical(f"Correlation shock detected: {corr_result.get('reason')}")
                # Reduce exposure globally
                self.risk_engine.defensive_mode = True
                self.risk_engine.defensive_mode_reason = corr_result.get('reason')
        
        # Feature 8: Drawdown Defense
        dd_result = self.risk_engine.check_drawdown_defense(self.capital)
        if not dd_result.get('allowed', True):
            logger.critical(f"Drawdown defense triggered: {dd_result.get('reason')}")
            self._close_all_positions()
            self._handle_risk_breach({'reason': dd_result.get('reason', 'Drawdown halt')})
            return
        
        # Feature 11: Meta-Learning Stability
        current_vol = self.risk_engine.volatility_history[-1] if self.risk_engine.volatility_history else 0
        recent_pnl = self.daily_pnl / self.daily_start_capital if self.daily_start_capital > 0 else 0
        stability_result = self.meta_learner.check_update_stability(
            current_volatility=current_vol,
            recent_performance=recent_pnl
        )
        if not stability_result.get('allowed', True):
            logger.warning(f"Meta-learning frozen: {stability_result.get('reason')}")
        
        # =========================================================================
        # END BLACK SWAN CHECKS
        # =========================================================================
        
        # Signals are executed via event bus in _on_signal_event (event-driven architecture)
        # Direct call removed to prevent double execution
        
        self._update_positions(primary_data)
        
        self._enforce_stop_loss_take_profit(primary_data)
        
        try:
            positions = self.order_manager.get_all_positions()
            pnl_summary = self.order_manager.trade_logger.get_pnl_summary() if hasattr(self.order_manager, 'trade_logger') else {}
            update_position_metrics(positions)
            update_trading_metrics(pnl_summary)
            update_capital_metrics(self.capital, self.capital - self.daily_pnl)
        except Exception as e:
            logger.warning(f"Could not update Prometheus metrics: {e}")
        
        # Update peak capital for drawdown tracking
        self.risk_engine.update_peak_capital(self.capital)
    
    def _detect_regime(self, market_data: Dict[str, Any]):
        """Detect market regime using HMM and publish event."""
        try:
            regime = self.intelligence.detect_regime(market_data)
            if regime != self.current_regime:
                logger.info(f"Regime change: {self.current_regime} -> {regime}")
                self.current_regime = regime
                self._switch_strategy(regime)
                
                regime_probs = self.intelligence.get_regime_probabilities()
                confidence = regime_probs.get(regime, 0.5)
                
                publish_regime_detected(
                    regime=regime,
                    confidence=confidence,
                    lookback_bars=100
                )
        except Exception as e:
            logger.error(f"Regime detection error: {e}")
    
    def _switch_strategy(self, regime: str):
        """Switch strategy based on regime."""
        regime_map = self.config.get('intelligence', {}).get('adaptive', {}).get('regime_strategy_map', {})
        strategy_name = regime_map.get(regime)
        
        if strategy_name and strategy_name in self.strategies:
            self.active_strategy = strategy_name
            logger.info(f"Switched to strategy: {strategy_name} for regime: {regime}")
    
    def _generate_signals(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading signals from multiple strategies (no event published yet)."""
        signals = self.signal_aggregator.generate(
            market_data,
            self.strategies.get(self.active_strategy, {})
        )
        
        symbol = market_data.get('symbol', 'BTCUSDT')
        signals['symbol'] = symbol
        action = signals.get('action', '')
        logger.debug(f"Raw signal: {action} {symbol} (conf={signals.get('confidence', 0):.2f})")
        
        if action and action.lower() != 'hold':
            self._pending_signals[symbol] = {
                'action': action,
                'market_data': market_data.copy(),
            }
        
        return signals
    
    def _intelligence_validate(self, signals: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate signals using ML ensemble."""
        try:
            validated = self.intelligence.validate(signals, market_data)
            dt_vote = validated.get('decision_tree', {}).get('action', '')
            sl_vote = validated.get('self_learning', {}).get('action', '')
            logger.debug(f"Validated signal: {validated.get('ensemble_action', '')} (conf={validated.get('confidence', 0):.2f}, votes={dt_vote}/{sl_vote})")
            return validated
        except Exception as e:
            logger.error(f"Intelligence validation error: {e}")
            return signals
    
    def _execute_signals(self, signals: Dict[str, Any], market_data: Dict[str, Any]):
        """Execute validated signals with circuit breaker protection."""
        if not signals.get('action'):
            return
        
        if not self.circuit_breaker.check_order_allowed():
            logger.warning("Order blocked by circuit breaker")
            return
        
        symbol = signals.get('symbol', market_data.get('symbol', 'BTCUSDT'))
        action = signals['action']
        price = market_data.get('close', market_data.get('price', 0))
        quantity = self._calculate_position_size(symbol)
        
        try:
            self.order_manager.execute(
                signal=action,
                symbol=symbol,
                price=price,
                size=quantity,
                leverage=self.leverage
            )
            self.circuit_breaker.record_order_success()
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            self.circuit_breaker.record_order_failure()
            return
        
        # Generate order ID and publish order executed event
        order_id = f"ord_{int(time.time() * 1000)}"
        publish_order_executed(
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            order_id=order_id,
            leverage=self.leverage
        )
        
        logger.info(f"Order executed: {action} {symbol} @ {price} x {quantity}")
    
    def _calculate_position_size(self, symbol: Optional[str] = None) -> float:
        """Calculate position size in units (not dollars) based on risk parameters."""
        position_pct = self.config.get('risk', {}).get('position_size_pct', 10) / 100
        dollar_size = self.capital * position_pct * self.leverage
        
        # Black Swan Feature 8: Drawdown Defense scaling
        dd_multiplier = self.risk_engine.get_defensive_multiplier()
        if dd_multiplier < 1.0:
            logger.info(f"Drawdown defense: position size scaled by {dd_multiplier:.2f}")
            dollar_size *= dd_multiplier
        
        # Black Swan Feature 5: Regime Collapse scaling
        if self.risk_engine.defensive_mode:
            logger.info(f"Regime collapse: position size scaled by 0.25")
            dollar_size *= 0.25
        
        # Convert dollar amount to quantity using current market price
        price = 0
        if symbol and hasattr(self, 'data_bridge'):
            price = self.data_bridge.get_price(symbol)
        if price <= 0:
            latest = self.data_bridge.get_latest_data() if hasattr(self, 'data_bridge') else {}
            price = latest.get('close', latest.get('price', 1))
        return dollar_size / price if price > 0 else dollar_size
    
    def _update_positions(self, market_data: Dict[str, Any]):
        """Update unrealized PnL on all positions via OrderManager."""
        for symbol in self.order_manager.get_all_positions():
            price = 0
            if hasattr(self, 'data_bridge'):
                price = self.data_bridge.get_price(symbol)
            if price <= 0:
                price = market_data.get('close', market_data.get('price', 0))
            if price > 0:
                self.order_manager.update_unrealized_pnl(symbol, price)
    
    def _enforce_stop_loss_take_profit(self, market_data: Dict[str, Any]):
        """Check each open position for SL/TP triggers and auto-close if hit."""
        for symbol, position in list(self.order_manager.get_all_positions().items()):
            if position.get('size', 0) == 0:
                continue
            
            price = 0
            if hasattr(self, 'data_bridge'):
                price = self.data_bridge.get_price(symbol)
            if price <= 0:
                price = market_data.get('close', market_data.get('price', 0))
            if price <= 0:
                continue
            
            risk_result = self.risk_engine.check_position_risk(position, price)
            
            if not risk_result.get('allowed', True):
                if risk_result.get('action') == 'close_position':
                    quantity = abs(position['size'])
                    self.order_manager.close_position(symbol, price, quantity)
                    logger.warning(f"Auto-closed {symbol} position: {risk_result['reason']}")
            elif risk_result.get('action') == 'consider_take_profit':
                quantity = abs(position['size'])
                self.order_manager.close_position(symbol, price, quantity)
                logger.info(f"Take profit closed {symbol} position: {risk_result['reason']}")
    
    def _close_all_positions(self):
        """Close all open positions at current market price."""
        for symbol in list(self.order_manager.get_all_positions().keys()):
            price = 0
            if hasattr(self, 'data_bridge'):
                price = self.data_bridge.get_price(symbol)
            if price <= 0:
                latest = self.data_bridge.get_latest_data() if hasattr(self, 'data_bridge') else {}
                price = latest.get('close', latest.get('price', 0))
            self.order_manager.close_position(symbol, price)
        logger.info("All positions closed")
    
    def _handle_risk_breach(self, risk_check: Dict[str, Any]):
        """Handle risk limit breach via event bus (Telegram handler subscribes)."""
        reason = risk_check.get('reason', 'Unknown')
        
        now = time.time()
        if now - self._last_breach_time < self._breach_cooldown:
            return
        self._last_breach_time = now
        
        logger.warning(f"Risk breach: {reason}")
        
        self._close_all_positions()
        
        if 'Daily loss' in reason:
            logger.info("Resetting daily PnL after loss breach to allow trading to resume")
            self.daily_pnl = 0.0
            self.daily_start_capital = self.capital
        
        if 'Drawdown' in reason:
            logger.info("Resetting peak capital after drawdown breach to allow trading to resume")
            self.risk_engine.peak_capital = self.capital
        
        from .layers.event_bus import RiskCheckEvent
        event = RiskCheckEvent(
            event_type=EventType.RISK_LIMIT_BREACH,
            risk_score=risk_check.get('risk_score', 100),
            daily_pnl=risk_check.get('daily_pnl', 0),
            capital=self.capital,
            positions=risk_check.get('positions', {}),
            allowed=False,
            reason=reason,
        )
        get_event_bus().publish(event)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        # Get current prices from data bridge
        prices = {}
        try:
            prices = self.data_bridge.get_all_prices()
        except Exception as e:
            logger.debug(f"Could not get prices: {e}")
        
        return {
            'running': self.running,
            'capital': self.capital,
            'leverage': self.leverage,
            'daily_pnl': self.daily_pnl,
            'positions': self.order_manager.get_all_positions(),
            'active_strategy': self.active_strategy,
            'current_regime': self.current_regime,
            'prices': prices,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions from OrderManager (single source of truth)."""
        return self.order_manager.get_all_positions()
    
    def get_pnl(self) -> float:
        """Get current P&L."""
        return self.daily_pnl
    
    def get_pnl_summary(self) -> Dict[str, Any]:
        """Get comprehensive PnL summary from TradeLogger."""
        try:
            if hasattr(self.order_manager, 'trade_logger'):
                return self.order_manager.trade_logger.get_pnl_summary()
        except Exception as e:
            logger.debug(f"Could not get PnL summary: {e}")
        
        return {
            'daily': {'total_pnl': self.daily_pnl, 'trade_count': 0},
            'cumulative': self.daily_pnl,
            'unrealized': 0.0,
            'open_positions': [],
            'trade_count': 0,
        }
    
    def switch_strategy(self, strategy_name: str) -> bool:
        """Switch to a different strategy."""
        if strategy_name not in self.strategies:
            logger.error(f"Strategy not found: {strategy_name}")
            return False
        
        self.active_strategy = strategy_name
        logger.info(f"Switched to strategy: {strategy_name}")
        return True
    
    def trigger_emergency_stop(self):
        """Emergency stop - close all positions and stop engine."""
        logger.critical("EMERGENCY STOP triggered")
        self._close_all_positions()
        self.stop()
    
    def get_learning_status(self) -> Dict[str, Any]:
        """Get comprehensive learning system status."""
        ensemble_status = self.intelligence.get_status()
        sl_status = ensemble_status.get('self_learning', {})
        adaptive_status = ensemble_status.get('adaptive', {})
        closed_loop = ensemble_status.get('closed_loop', {})
        
        sl_update_events = self.event_bus.get_events_by_type(
            EventType.SELF_LEARNING_UPDATE, limit=100
        )
        model_pred_events = self.event_bus.get_events_by_type(
            EventType.MODEL_PREDICTION, limit=100
        )
        
        return {
            'hmm': {
                'trained': getattr(self.intelligence.hmm, 'model_trained', False),
                'current_regime': self.intelligence.current_regime,
                'price_history_length': len(self.intelligence.price_history),
                'regime_probabilities': self.intelligence.get_regime_probabilities(),
            },
            'self_learning': {
                'buffer_size': sl_status.get('buffer_size', 0),
                'retrain_count': sl_status.get('retrain_count', 0),
                'min_samples_required': sl_status.get('min_samples_required', 0),
                'time_to_retrain': sl_status.get('time_to_retrain', 0),
                'is_training': sl_status.get('is_training', False),
                'model_accuracy': sl_status.get('model_accuracy', 0.0),
            },
            'decision_tree': {
                'is_trained': self.intelligence.decision_tree.is_trained,
                'accuracy': self.intelligence.get_decision_tree_accuracy(),
            },
            'adaptive': {
                'current_regime': adaptive_status.get('current_regime', ''),
                'current_strategy': adaptive_status.get('current_strategy', ''),
                'total_switches': adaptive_status.get('total_switches', 0),
                'regime_performance': adaptive_status.get('regime_performance', {}),
            },
            'self_awareness': {
                'trade_count_since_retrain': self.self_awareness.trade_count_since_retrain,
                'performance_records': len(self.self_awareness.model_performance_history),
                'last_retrain': self.self_awareness.last_model_retrain,
            },
            'closed_loop': {
                'trades_outcome_recorded': closed_loop.get('trades_outcome_recorded', 0),
                'total_reward_accumulated': closed_loop.get('total_reward_accumulated', 0.0),
                'pending_trades': closed_loop.get('pending_trades', 0),
            },
            'integrated_healing': self.integrated_healing.get_healing_report(),
            'goal_management': self.goal_manager.get_report(),
            'healing_effectiveness': self.healing_effectiveness.get_effectiveness_report(),
            'meta_learning': self.meta_learner.get_report(),
            'events': {
                'self_learning_updates': len(sl_update_events),
                'model_predictions': len(model_pred_events),
            },
            'timestamp': datetime.now().isoformat(),
        }


_engine: Optional[PaperTradingEngine] = None


def get_engine(config_path: str = None) -> PaperTradingEngine:
    """Get singleton engine instance."""
    global _engine
    if _engine is None:
        _engine = PaperTradingEngine(config_path)
    return _engine


def start_engine(config_path: str = None):
    """Start the paper trading engine."""
    engine = get_engine(config_path)
    engine.start()
    return engine


def stop_engine():
    """Stop the paper trading engine."""
    global _engine
    if _engine:
        _engine.stop()
        _engine = None


if __name__ == "__main__":
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / f"paper_trading.{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )
    logger.info("Starting Paper Trading Engine...")
    
    engine = PaperTradingEngine()
    engine.start()
    
    try:
        while True:
            time.sleep(10)
            status = engine.get_status()
            logger.info(f"Status: {status}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        engine.stop()
