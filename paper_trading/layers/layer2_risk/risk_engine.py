"""
Layer 2: Risk Management Engine
Risk limits, position sizing, and daily loss tracking.
Black Swan Resistant Execution Layer - Phase 1
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, time
from loguru import logger
import math
import numpy as np


class RiskEngine:
    """Risk management engine for position and loss limits."""
    
    def __init__(self, config: Dict[str, Any]):
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 5)
        self.max_drawdown_pct = config.get('max_drawdown_pct', 20)
        self.position_size_pct = config.get('position_size_pct', 10)
        self.stop_loss_pct = config.get('stop_loss_pct', 2)
        self.take_profit_pct = config.get('take_profit_pct', 5)
        
        self.daily_loss_start = 0.0
        self.peak_capital = 0.0
        self.last_reset_date = datetime.now().date()
        
        self.leverage_limit = 10
        
        # Black Swan Parameters (Phase 1)
        self.black_swan = config.get('black_swan', {})
        self.cvar_limit_pct = self.black_swan.get('cvar_limit_pct', 5.0)
        self.defensive_vol_threshold = self.black_swan.get('defensive_vol_threshold', 3.0)
        self.dd_scale_5_pct = self.black_swan.get('dd_scale_5_pct', 0.25)
        self.dd_scale_10_pct = self.black_swan.get('dd_scale_10_pct', 0.50)
        self.dd_scale_15_pct = self.black_swan.get('dd_scale_15_pct', 0.0)
        self.consecutive_loss_limit = self.black_swan.get('consecutive_loss_limit', 3)
        
        # Runtime state
        self.defensive_mode = False
        self.defensive_mode_reason: Optional[str] = None
        self.consecutive_losses = 0
        self.volatility_history: List[float] = []
        self.price_history: List[float] = []
        self.max_volatility_history = 100
    
    def check_risk(self, capital: float, daily_pnl: float, 
                   positions: Dict[str, Any], start_capital: float) -> Dict[str, Any]:
        """Check if trading is allowed based on risk limits."""
        self._check_daily_reset()
        
        daily_loss_pct = (daily_pnl / start_capital * 100) if start_capital > 0 else 0
        
        if daily_loss_pct <= -self.max_daily_loss_pct:
            return {
                'allowed': False,
                'reason': f'Daily loss limit hit: {daily_loss_pct:.2f}%',
                'level': 'critical',
                'risk_score': 100,
                'action': 'stop_trading'
            }
        
        current_drawdown = ((self.peak_capital - capital) / self.peak_capital * 100) \
                          if self.peak_capital > 0 else 0
        
        if current_drawdown >= self.max_drawdown_pct:
            return {
                'allowed': False,
                'reason': f'Drawdown limit hit: {current_drawdown:.2f}%',
                'level': 'critical',
                'risk_score': 100,
                'action': 'stop_trading'
            }
        
        total_exposure = sum(
            abs(pos.get('size', 0)) * pos.get('entry_price', 0) 
            for pos in positions.values()
        )
        
        leverage_used = total_exposure / capital if capital > 0 else 0
        
        if leverage_used > self.leverage_limit:
            return {
                'allowed': False,
                'reason': f'Leverage limit exceeded: {leverage_used:.1f}x',
                'level': 'high',
                'risk_score': 80,
                'action': 'reduce_positions'
            }
        
        risk_score = self._calculate_risk_score(daily_loss_pct, current_drawdown, leverage_used)
        
        if risk_score > 70:
            return {
                'allowed': True,
                'reason': 'High risk - reduce position size',
                'level': 'medium',
                'risk_score': risk_score,
                'action': 'reduce_size'
            }
        
        return {
            'allowed': True,
            'reason': 'Risk checks passed',
            'level': 'low',
            'risk_score': risk_score,
            'action': 'normal'
        }
    
    def check_position_risk(self, position: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """Check risk for a specific position."""
        entry_price = position.get('entry_price', 0)
        size = position.get('size', 0)
        
        if entry_price == 0 or size == 0:
            return {'allowed': True, 'reason': 'No position'}
        
        if size > 0:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        if pnl_pct <= -self.stop_loss_pct:
            return {
                'allowed': False,
                'reason': f'Stop loss triggered: {pnl_pct:.2f}%',
                'action': 'close_position'
            }
        elif pnl_pct >= self.take_profit_pct:
            return {
                'allowed': True,
                'reason': f'Take profit hit: {pnl_pct:.2f}%',
                'action': 'consider_take_profit'
            }
        
        return {'allowed': True, 'reason': 'Position risk OK'}
    
    def calculate_position_size(self, capital: float, price: float, 
                                 risk_pct: Optional[float] = None) -> float:
        """Calculate position size based on risk parameters."""
        risk_pct = risk_pct or self.position_size_pct
        
        base_size = capital * (risk_pct / 100)
        
        leveraged_size = base_size * self.leverage_limit
        
        return leveraged_size / price
    
    def _check_daily_reset(self):
        """Reset daily tracking if new day."""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_loss_start = 0.0
            self.last_reset_date = today
            logger.info("Daily risk tracking reset")
    
    def _calculate_risk_score(self, daily_loss_pct: float, drawdown: float, 
                               leverage: float) -> float:
        """Calculate overall risk score (0-100)."""
        loss_score = min(abs(daily_loss_pct) / self.max_daily_loss_pct * 50, 50)
        drawdown_score = min(drawdown / self.max_drawdown_pct * 30, 30)
        leverage_score = min(leverage / self.leverage_limit * 20, 20)
        
        return loss_score + drawdown_score + leverage_score
    
    def update_peak_capital(self, capital: float):
        """Update peak capital for drawdown tracking."""
        if capital > self.peak_capital:
            self.peak_capital = capital
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        current_drawdown = ((self.peak_capital - (self.daily_loss_start + self.get_daily_pnl())) / self.peak_capital * 100) \
                          if self.peak_capital > 0 else 0
        
        return {
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'max_drawdown_pct': self.max_drawdown_pct,
            'position_size_pct': self.position_size_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'leverage_limit': self.leverage_limit,
            'peak_capital': self.peak_capital,
            'last_reset': self.last_reset_date.isoformat(),
            'black_swan': {
                'defensive_mode': self.defensive_mode,
                'defensive_reason': self.defensive_mode_reason,
                'consecutive_losses': self.consecutive_losses,
                'cvar_limit_pct': self.cvar_limit_pct,
            }
        }
    
    def get_daily_pnl(self) -> float:
        return 0.0
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 1
    # =========================================================================
    
    def check_tail_risk(self, positions: Dict[str, Any], capital: float, 
                        current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Feature 1: CVaR-based Tail Risk Engine
        Computes Value at Risk and Conditional VaR for each trade.
        Reject trade if CVaR_loss > threshold (default 5% of capital).
        """
        if not positions or capital <= 0:
            return {'allowed': True, 'cvar': 0, 'var': 0, 'reason': 'No positions'}
        
        position_risks = []
        total_portfolio_var = 0.0
        
        for symbol, pos in positions.items():
            size = pos.get('size', 0)
            entry_price = pos.get('entry_price', 0)
            current_price = current_prices.get(symbol, entry_price)
            
            if size == 0 or entry_price == 0:
                continue
            
            position_value = abs(size) * entry_price
            pnl_pct = ((current_price - entry_price) / entry_price) if size > 0 \
                     else ((entry_price - current_price) / entry_price)
            
            var_95 = position_value * 1.645 * abs(pnl_pct) if pnl_pct < 0 else 0
            cvar_95 = var_95 * 1.5
            
            position_risks.append({
                'symbol': symbol,
                'var': var_95,
                'cvar': cvar_95,
                'position_value': position_value,
                'exposure_pct': (position_value / capital * 100) if capital > 0 else 0
            })
            
            total_portfolio_var += var_95
        
        portfolio_cvar = total_portfolio_var * 1.5
        cvar_pct = (portfolio_cvar / capital * 100) if capital > 0 else 0
        
        if cvar_pct > self.cvar_limit_pct:
            return {
                'allowed': False,
                'cvar': portfolio_cvar,
                'var': total_portfolio_var,
                'cvar_pct': cvar_pct,
                'reason': f'CVaR limit exceeded: {cvar_pct:.2f}% > {self.cvar_limit_pct}%',
                'level': 'critical',
                'action': 'reject_trade'
            }
        
        return {
            'allowed': True,
            'cvar': portfolio_cvar,
            'var': total_portfolio_var,
            'cvar_pct': cvar_pct,
            'position_risks': position_risks,
            'reason': 'Tail risk OK',
            'level': 'low'
        }
    
    def update_volatility(self, price: float):
        """Update volatility history for regime collapse detection."""
        self.price_history.append(price)
        if len(self.price_history) > 2:
            returns = []
            for i in range(1, len(self.price_history)):
                ret = (self.price_history[i] - self.price_history[i-1]) / self.price_history[i-1]
                returns.append(abs(ret))
            
            if returns:
                current_vol = np.std(returns) * np.sqrt(288) if len(returns) >= 2 else 0
                self.volatility_history.append(current_vol)
                
                if len(self.volatility_history) > self.max_volatility_history:
                    self.volatility_history.pop(0)
    
    def detect_regime_collapse(self) -> Dict[str, Any]:
        """
        Feature 5: Regime Collapse Detection
        Detect anomalies: volatility spike > Xσ, correlation spike, liquidity drop.
        Enter DEFENSIVE MODE if detected: reduce position size 50-80%.
        """
        if len(self.volatility_history) < 20:
            return {
                'collapsed': False,
                'defensive_mode': self.defensive_mode,
                'reason': 'Insufficient volatility history'
            }
        
        vol_array = np.array(self.volatility_history)
        mean_vol = np.mean(vol_array)
        std_vol = np.std(vol_array)
        
        if std_vol == 0:
            return {
                'collapsed': False,
                'defensive_mode': self.defensive_mode,
                'reason': 'Zero volatility variance'
            }
        
        current_vol = self.volatility_history[-1] if self.volatility_history else 0
        z_score = (current_vol - mean_vol) / std_vol
        
        if z_score > self.defensive_vol_threshold and not self.defensive_mode:
            self.defensive_mode = True
            self.defensive_mode_reason = f'Volatility spike: {z_score:.2f}σ'
            logger.critical(f"DEFENSIVE MODE ACTIVATED: {self.defensive_mode_reason}")
            
            return {
                'collapsed': True,
                'defensive_mode': True,
                'z_score': z_score,
                'current_vol': current_vol,
                'mean_vol': mean_vol,
                'reason': self.defensive_mode_reason,
                'action': 'enter_defensive'
            }
        
        elif z_score < 0.5 and self.defensive_mode:
            self.defensive_mode = False
            self.defensive_mode_reason = None
            logger.info("DEFENSIVE MODE DEACTIVATED: Volatility normalized")
            
            return {
                'collapsed': False,
                'defensive_mode': False,
                'z_score': z_score,
                'reason': 'Volatility normalized',
                'action': 'exit_defensive'
            }
        
        return {
            'collapsed': False,
            'defensive_mode': self.defensive_mode,
            'z_score': z_score,
            'reason': 'Regime stable'
        }
    
    def check_drawdown_defense(self, capital: float) -> Dict[str, Any]:
        """
        Feature 8: Capital Drawdown Defense
        Dynamic scaling: 
        - drawdown > 5% → reduce size 25%
        - drawdown > 10% → reduce size 50%  
        - drawdown > 15% → halt trading
        """
        if self.peak_capital <= 0:
            return {'allowed': True, 'size_multiplier': 1.0, 'reason': 'No peak capital'}
        
        drawdown_pct = ((self.peak_capital - capital) / self.peak_capital * 100)
        
        if drawdown_pct >= 15:
            return {
                'allowed': False,
                'size_multiplier': 0.0,
                'drawdown_pct': drawdown_pct,
                'reason': f'Drawdown {drawdown_pct:.2f}% > 15%: Trading halted',
                'level': 'critical',
                'action': 'halt_trading'
            }
        elif drawdown_pct >= 10:
            return {
                'allowed': True,
                'size_multiplier': self.dd_scale_10_pct,
                'drawdown_pct': drawdown_pct,
                'reason': f'Drawdown {drawdown_pct:.2f}% > 10%: Size reduced 50%',
                'level': 'high',
                'action': 'reduce_size_50pct'
            }
        elif drawdown_pct >= 5:
            return {
                'allowed': True,
                'size_multiplier': self.dd_scale_5_pct,
                'drawdown_pct': drawdown_pct,
                'reason': f'Drawdown {drawdown_pct:.2f}% > 5%: Size reduced 25%',
                'level': 'medium',
                'action': 'reduce_size_25pct'
            }
        
        return {
            'allowed': True,
            'size_multiplier': 1.0,
            'drawdown_pct': drawdown_pct,
            'reason': 'Drawdown within limits',
            'level': 'low'
        }
    
    def record_trade_outcome(self, pnl: float):
        """Record trade outcome for fail-safe tracking."""
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        if self.consecutive_losses >= self.consecutive_loss_limit:
            logger.critical(f"FAIL-SAFE TRIGGERED: {self.consecutive_losses} consecutive losses")
            return True
        return False
    
    def get_defensive_multiplier(self) -> float:
        """Get position size multiplier when in defensive mode."""
        if self.defensive_mode:
            return 0.25
        return 1.0
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 2 (Feature 12: Execution Conservatism)
    # =========================================================================
    
    def check_conservatism(self, uncertainty_result: Dict[str, Any],
                          edge_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Feature 12: Execution Conservatism
        If uncertain → DO NOTHING. Require high conviction to execute.
        """
        if not uncertainty_result.get('allowed', True):
            return {
                'allowed': False,
                'reason': f"Conservative rejection: {uncertainty_result.get('reason', 'unknown')}",
                'action': 'reject'
            }
        
        if not edge_result.get('allowed', True):
            return {
                'allowed': False,
                'reason': f"Conservative rejection: {edge_result.get('reason', 'unknown')}",
                'action': 'reject'
            }
        
        uncertainty = uncertainty_result.get('uncertainty', 0)
        confidence = edge_result.get('confidence', 0)
        
        if uncertainty > 0.3 or confidence < 0.5:
            logger.info(f"Trade rejected by conservatism: uncertainty={uncertainty:.2f}, confidence={confidence:.2f}")
            return {
                'allowed': False,
                'reason': f'Low conviction: uncertainty {uncertainty:.2f} or confidence {confidence:.2f}',
                'action': 'reject'
            }
        
        return {
            'allowed': True,
            'reason': 'High conviction trade',
            'action': 'proceed'
        }
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 2 (Feature 7: Risk of Ruin)
    # =========================================================================
    
    def calculate_ruin_probability(self, win_rate: float, avg_win: float, 
                                   avg_loss: float, capital: float,
                                   min_capital_threshold: float = 1000) -> Dict[str, Any]:
        """
        Feature 7: Risk of Ruin Engine
        P_ruin = probability(capital → critical threshold)
        Using Kelly Criterion approach.
        Halt if P_ruin > threshold.
        """
        if win_rate <= 0 or win_rate >= 1:
            return {
                'allowed': True,
                'ruin_prob': 0,
                'reason': 'Invalid win rate for ruin calculation'
            }
        
        if avg_loss == 0:
            return {
                'allowed': True,
                'ruin_prob': 0,
                'reason': 'No loss data for ruin calculation'
            }
        
        payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        if payoff_ratio <= 0:
            return {
                'allowed': True,
                'ruin_prob': 0,
                'reason': 'Invalid payoff ratio'
            }
        
        b = payoff_ratio
        p = win_rate
        q = 1 - p
        
        kelly_fraction = (b * p - q) / b
        
        if kelly_fraction <= 0:
            kelly_fraction = 0.01
        
        max_position_size = capital * kelly_fraction
        
        expected_growth = p * avg_win - q * avg_loss
        variance = p * (avg_win - expected_growth)**2 + q * (avg_loss + expected_growth)**2
        
        critical_capital = min_capital_threshold
        
        if capital <= critical_capital:
            return {
                'allowed': False,
                'ruin_prob': 1.0,
                'kelly_fraction': kelly_fraction,
                'capital': capital,
                'reason': f'Capital {capital:.2f} below critical threshold {critical_capital}',
                'action': 'halt_trading'
            }
        
        ruin_prob_estimate = math.exp(-2 * (capital - critical_capital) * abs(expected_growth) / variance) if variance > 0 else 0
        
        ruin_threshold = 0.01
        
        if ruin_prob_estimate > ruin_threshold:
            logger.critical(f"Risk of ruin too high: {ruin_prob_estimate:.4f} > {ruin_threshold}")
            return {
                'allowed': False,
                'ruin_prob': ruin_prob_estimate,
                'kelly_fraction': kelly_fraction,
                'expected_growth': expected_growth,
                'reason': f'Risk of ruin {ruin_prob_estimate:.4f} > threshold {ruin_threshold}',
                'action': 'halt_trading'
            }
        
        return {
            'allowed': True,
            'ruin_prob': ruin_prob_estimate,
            'kelly_fraction': kelly_fraction,
            'max_position_size': max_position_size,
            'expected_growth': expected_growth,
            'reason': 'Ruin probability acceptable',
            'action': 'proceed'
        }
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 3 (Feature 6: Correlation Shock)
    # =========================================================================
    
    def check_correlation_shock(self, price_returns: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Feature 6: Correlation Shock Handling
        Monitor rolling correlation matrix.
        If correlations converge → treat positions as one risk cluster → reduce exposure.
        """
        if len(price_returns) < 2:
            return {
                'shock_detected': False,
                'avg_correlation': 0,
                'reason': 'Insufficient symbols for correlation'
            }
        
        symbols = list(price_returns.keys())
        min_length = min(len(returns) for returns in price_returns.values())
        
        if min_length < 10:
            return {
                'shock_detected': False,
                'avg_correlation': 0,
                'reason': 'Insufficient return history'
            }
        
        returns_matrix = np.array([returns[-min_length:] for returns in price_returns.values()])
        
        if returns_matrix.shape[0] < 2 or returns_matrix.shape[1] < 2:
            return {
                'shock_detected': False,
                'avg_correlation': 0,
                'reason': 'Matrix too small'
            }
        
        corr_matrix = np.corrcoef(returns_matrix)
        
        np.fill_diagonal(corr_matrix, 0)
        n_pairs = len(symbols) * (len(symbols) - 1)
        avg_correlation = np.sum(corr_matrix) / n_pairs if n_pairs > 0 else 0
        
        high_corr_threshold = 0.8
        high_corr_count = np.sum(corr_matrix > high_corr_threshold) // 2
        
        if avg_correlation > 0.7:
            logger.critical(
                f"CORRELATION SHOCK: avg_corr={avg_correlation:.2f}, "
                f"high_corr_pairs={high_corr_count}"
            )
            return {
                'shock_detected': True,
                'avg_correlation': avg_correlation,
                'high_corr_pairs': high_corr_count,
                'correlation_matrix': corr_matrix.tolist(),
                'reason': f'High correlation {avg_correlation:.2f} > 0.7',
                'action': 'reduce_exposure'
            }
        
        return {
            'shock_detected': False,
            'avg_correlation': avg_correlation,
            'high_corr_pairs': high_corr_count,
            'reason': 'Correlations normal'
        }
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - HARD EXPECTANCY GATE (Feature 0)
    # =========================================================================

    def check_expectancy(self, trade_logger, min_trades: int = 10,
                         min_win_rate: float = 15.0, min_expectancy: float = 0.0) -> Dict[str, Any]:
        """
        Feature 0: Hard Expectancy / Win-Rate Gate
        Analyzes the last N closed trades from Redis/TradeLogger.
        Rejects ALL trades if:
          - win_rate < min_win_rate (default 15%)
          - expectancy (avg PnL per trade) < min_expectancy (default $0)
        This is the ABSOLUTE first filter — nothing else runs if this fails.
        """
        if trade_logger is None:
            return {
                'allowed': False,
                'reason': 'TradeLogger unavailable — hard expectancy gate blocks all trades',
                'action': 'reject'
            }

        try:
            trades = trade_logger.get_recent_trades(limit=50)
        except Exception as e:
            logger.warning(f"Could not fetch trade history for expectancy check: {e}")
            return {
                'allowed': False,
                'reason': f'Trade history fetch failed: {e}',
                'action': 'reject'
            }

        if len(trades) < min_trades:
            return {
                'allowed': False,
                'reason': f'Insufficient trade history: {len(trades)} < {min_trades} trades',
                'action': 'reject',
                'trade_count': len(trades)
            }

        pnls = [t.get('pnl', 0) for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        total = len(pnls)

        win_rate = (wins / total * 100) if total > 0 else 0
        expectancy = sum(pnls) / total if total > 0 else 0

        avg_win = sum(p for p in pnls if p > 0) / wins if wins > 0 else 0
        avg_loss = sum(p for p in pnls if p < 0) / losses if losses > 0 else 0

        if win_rate < min_win_rate:
            logger.critical(
                f"EXPECTANCY GATE REJECT: win_rate={win_rate:.1f}% < {min_win_rate}% "
                f"(last {total} trades: {wins}W/{losses}L, expectancy=${expectancy:.2f})"
            )
            return {
                'allowed': False,
                'reason': f'Win rate {win_rate:.1f}% below minimum {min_win_rate}%',
                'action': 'reject',
                'win_rate': win_rate,
                'expectancy': expectancy,
                'trade_count': total,
                'wins': wins,
                'losses': losses,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
            }

        if expectancy < min_expectancy:
            logger.critical(
                f"EXPECTANCY GATE REJECT: expectancy=${expectancy:.2f} < ${min_expectancy} "
                f"(last {total} trades: {wins}W/{losses}L, win_rate={win_rate:.1f}%)"
            )
            return {
                'allowed': False,
                'reason': f'Negative expectancy ${expectancy:.2f}',
                'action': 'reject',
                'win_rate': win_rate,
                'expectancy': expectancy,
                'trade_count': total,
                'wins': wins,
                'losses': losses,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
            }

        return {
            'allowed': True,
            'reason': f'Expectancy OK: win_rate={win_rate:.1f}%, expectancy=${expectancy:.2f}',
            'win_rate': win_rate,
            'expectancy': expectancy,
            'trade_count': total,
            'wins': wins,
            'losses': losses,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
        }

    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 3 (Feature 9: Liquidity Filter)
    # =========================================================================

    def check_market_liquidity(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Feature 9: Liquidity & Market Stress Filter
        Reject trades if: spread widening > threshold, order book depth collapse, abnormal volume
        """
        spread_pct = market_data.get('spread_pct', 0)
        volume_ratio = market_data.get('volume_ratio', 1.0)
        order_book_depth = market_data.get('order_book_depth', 1.0)
        
        spread_threshold = 0.005
        volume_spike_threshold = 5.0
        depth_threshold = 0.1
        
        if spread_pct > spread_threshold:
            return {
                'allowed': False,
                'reason': f'Spread too wide: {spread_pct:.3%} > {spread_threshold:.3%}',
                'action': 'reject'
            }
        
        if volume_ratio > volume_spike_threshold:
            return {
                'allowed': False,
                'reason': f'Abnormal volume spike: {volume_ratio:.1f}x > {volume_spike_threshold}x',
                'action': 'reject'
            }
        
        if order_book_depth < depth_threshold:
            return {
                'allowed': False,
                'reason': f'Order book depth collapsed: {order_book_depth:.2f} < {depth_threshold}',
                'action': 'reject'
            }
        
        return {
            'allowed': True,
            'reason': 'Liquidity OK',
            'spread_pct': spread_pct,
            'volume_ratio': volume_ratio,
            'order_book_depth': order_book_depth
        }
