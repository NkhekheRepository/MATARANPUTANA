"""
Layer 4: Intelligence Ensemble
Combines HMM, Decision Tree, PPO, and Adaptive Learning.
Closed-loop learning: trade outcomes feed back into all models.
Black Swan Resistant Execution Layer - Phase 2
"""

import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from .hmm import HMMRegimeDetector
from .decision_tree import DecisionTreeAgent
from .self_learning import SelfLearningEngine
from .adaptive_learning import AdaptiveLearning
from ..event_bus import publish_self_learning_update, publish_model_prediction
from .rl_agent import RLPredictor


class IntelligenceEnsemble:
    """Ensemble of ML models for trading intelligence."""
    
    def __init__(self, config: Dict[str, Any]):
        self.hmm_enabled = config.get('hmm', {}).get('enabled', True)
        self.decision_tree_enabled = config.get('decision_tree', {}).get('enabled', True)
        self.self_learning_enabled = config.get('self_learning', {}).get('enabled', True)
        self.adaptive_enabled = config.get('adaptive', {}).get('enabled', True)
        self.rl_enabled = config.get('rl', {}).get('enabled', True)
        
        self.hmm = HMMRegimeDetector(config.get('hmm', {}))
        self.decision_tree = DecisionTreeAgent(config.get('decision_tree', {}))
        self.self_learning = SelfLearningEngine(config.get('self_learning', {}))
        self.adaptive = AdaptiveLearning(config.get('adaptive', {}))
        self.rl_predictor = RLPredictor(
            symbols=config.get('rl', {}).get('symbols', ["BTCUSDT", "ETHUSDT"]),
            config=config.get('rl', {})
        ) if self.rl_enabled else None
        
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        
        self.current_regime = 'sideways'
        
        self.pending_trades: Dict[str, Dict[str, Any]] = {}
        
        self.trades_outcome_recorded = 0
        self.total_reward_accumulated = 0.0
        
        self._last_dt_X: List[List[float]] = []
        self._last_dt_y: List[int] = []
        
        # Black Swan Parameters - Phase 2
        self.black_swan = config.get('black_swan', {})
        self.uncertainty_beta = self.black_swan.get('uncertainty_beta', 0.3)
        self.uncertainty_threshold = self.black_swan.get('uncertainty_threshold', 0.5)  # Widened from 0.2 for more trades
        
        self.model_predictions: List[Dict[str, Any]] = []
        self.max_prediction_history = 100
        
        logger.info("Intelligence Ensemble initialized")
    
    def update(self, price: float, volume: float = 0):
        """Update all models with new data."""
        self.price_history.append(price)
        if volume > 0:
            self.volume_history.append(volume)
        
        if len(self.price_history) >= 20:
            self.hmm.update(price, volume)
            
            self.current_regime = self.hmm.get_current_regime()
    
    def detect_regime(self, market_data: Dict[str, Any]) -> str:
        """Detect current market regime."""
        price = market_data.get('price', market_data.get('close', 0))
        volume = market_data.get('volume', 0)
        
        if price > 0:
            self.update(price, volume)
        
        return self.current_regime
    
    def get_regime_probabilities(self) -> Dict[str, float]:
        """Get probability distribution over regimes from HMM."""
        return self.hmm.get_regime_probabilities()
    
    def record_signal(self, symbol: str, action: str, market_data: Dict[str, Any]):
        """Record a signal for later reward resolution when the trade closes."""
        if action and action.lower() != 'hold':
            self.pending_trades[symbol] = {
                'action': action.lower(),
                'market_data': market_data.copy(),
                'timestamp': time.time(),
                'regime': self.current_regime,
            }
    
    def record_trade_outcome(self, symbol: str, action: str, pnl: float,
                              entry_price: float, exit_price: float):
        """
        Feed actual trade outcome back into all learning components.
        Called by the engine when a position is closed.
        """
        reward = 0.0
        if entry_price > 0:
            direction = 1 if action == 'buy' else -1
            price_change = (exit_price - entry_price) / entry_price
            reward = price_change * direction
        
        self.total_reward_accumulated += reward
        self.trades_outcome_recorded += 1
        
        pending = self.pending_trades.pop(symbol, None)
        market_data = pending['market_data'] if pending else {}
        original_action = pending['action'] if pending else action
        regime = pending.get('regime', self.current_regime) if pending else self.current_regime
        
        if self.self_learning_enabled:
            self._update_self_learning(market_data, original_action, reward)
        
        if self.adaptive_enabled:
            strategy = self.adaptive.current_strategy or 'unknown'
            self.adaptive.record_trade(
                regime=regime,
                strategy=strategy,
                pnl=pnl,
                was_winning=pnl > 0,
            )
         
        # RL-specific outcome tracking
        if self.rl_enabled and self.rl_predictor:
            self.rl_predictor.record_trade_outcome(symbol, action, pnl)
         
        logger.info(
            f"Trade outcome recorded: {symbol} {action} "
            f"pnl={pnl:.2f} reward={reward:.4f} "
            f"entry={entry_price:.2f} exit={exit_price:.2f}"
        )
    
    def _update_self_learning(self, market_data: Dict[str, Any],
                               action: str, reward: float):
        """Update self-learning model with actual reward and retrain if needed."""
        self.self_learning.add_experience(market_data, action, reward)
        
        if self.self_learning.should_retrain():
            retrained = self.self_learning.retrain()
            
            if retrained:
                self._retrain_decision_tree()
                
                publish_self_learning_update(
                    retrain_count=self.self_learning.retrain_count,
                    buffer_size=len(self.self_learning.experience_buffer),
                    model_accuracy=self._estimate_model_accuracy(),
                    decision_tree_trained=self.decision_tree.is_trained,
                )
                
                logger.info(
                    f"Self-learning retrain #{self.self_learning.retrain_count}: "
                    f"buffer={len(self.self_learning.experience_buffer)}, "
                    f"dt_trained={self.decision_tree.is_trained}"
                )
    
    def _retrain_decision_tree(self):
        """Retrain decision tree from self-learning experience buffer."""
        if not self.self_learning_enabled:
            return

        experiences = list(self.self_learning.experience_buffer)
        if len(experiences) < self.self_learning.min_samples:
            return

        X = []
        y = []
        action_map = {'hold': 0, 'buy': 1, 'sell': 2}

        for exp in experiences:
            features = self.self_learning._extract_features(exp['state'])
            label = action_map.get(exp['action'], 0)
            X.append(features)
            y.append(label)

        self._last_dt_X = X
        self._last_dt_y = y

        try:
            self.decision_tree.train(X, y)
            logger.info(f"Decision tree retrained from {len(X)} experiences")
        except Exception as e:
            logger.error(f"Decision tree retrain failed: {e}")
    
    def _estimate_model_accuracy(self) -> float:
        """Estimate model accuracy from recent experience buffer."""
        if not self.self_learning.model or len(self.self_learning.experience_buffer) < 10:
            return 0.0
        
        experiences = list(self.self_learning.experience_buffer)[-100:]
        correct = 0
        
        for exp in experiences:
            features = self.self_learning._extract_features(exp['state'])
            import numpy as np
            features_arr = np.array(features).reshape(1, -1)
            predicted_idx = self.self_learning.model.predict(features_arr)[0]
            action_map = {'hold': 0, 'buy': 1, 'sell': 2}
            actual_idx = action_map.get(exp['action'], 0)
            if predicted_idx == actual_idx:
                correct += 1
        
        return correct / len(experiences) if experiences else 0.0
    
    def validate(self, signals: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate signals using ensemble."""
        regime = self.detect_regime(market_data)
        
        validated_signals = signals.copy()
        validated_signals['regime'] = regime
        
        ensemble_votes = []
        dt_vote = ''
        sl_vote = ''
        rl_vote = ''
        
        if self.decision_tree_enabled:
            dt_result = self.decision_tree.predict(market_data)
            if dt_result and dt_result.get('action'):
                dt_vote = dt_result['action']
                if dt_vote:  # Only append non-empty votes
                    ensemble_votes.append(dt_vote)
                validated_signals['decision_tree'] = dt_result
        
        if self.self_learning_enabled and self.self_learning.model:
            sl_result = self.self_learning.predict(market_data)
            if sl_result and sl_result.get('action'):
                sl_vote = sl_result['action']
                if sl_vote:  # Only append non-empty votes
                    ensemble_votes.append(sl_vote)
                validated_signals['self_learning'] = sl_result
        
        # RL prediction
        if self.rl_enabled and self.rl_predictor:
            rl_prediction = self.rl_predictor.predict()
            if rl_prediction:
                rl_action_idx, rl_action = rl_prediction
                if rl_action:  # Only append non-empty votes
                    rl_vote = rl_action
                    ensemble_votes.append(rl_vote)
                    validated_signals['rl_prediction'] = {
                        'action': rl_action,
                        'action_idx': rl_action_idx,
                        'vote_weight': self.rl_predictor.get_vote_weight()
                    }
        
        if self.adaptive_enabled:
            strategy = self.adaptive.select_strategy(regime, market_data)
            validated_signals['recommended_strategy'] = strategy
        
        base_action = signals.get('action')
        
        has_aggregator_action = base_action and base_action not in (None, 'hold')
        
        if has_aggregator_action:
            final_action = base_action
        elif ensemble_votes and any(v in ('buy', 'sell') for v in ensemble_votes):
            final_action = self._combine_votes(ensemble_votes, 'hold')
        else:
            dt_result = validated_signals.get('decision_tree', {})
            if dt_result and dt_result.get('action') and dt_result['action'] != 'hold':
                final_action = dt_result['action']
            else:
                final_action = 'hold'
        
        validated_signals['ensemble_action'] = final_action
        
        if has_aggregator_action:
            validated_signals['confidence'] = signals.get('confidence', 0.5)
        elif ensemble_votes:
            validated_signals['confidence'] = self._calculate_confidence(ensemble_votes, final_action)
        else:
            validated_signals['confidence'] = signals.get('confidence', 0.5)
        
        base_signal = signals.get('action', '')
        publish_model_prediction(
            ensemble_action=final_action,
            confidence=validated_signals['confidence'],
            regime=regime,
            decision_tree_vote=dt_vote,
            self_learning_vote=sl_vote,
            rl_vote=rl_vote,
            base_signal=base_signal,
        )
        
        if self.self_learning_enabled:
            action = signals.get('action')
            if action and action != 'hold':
                self.self_learning.add_experience(
                    market_data, action, 0
                )
                
                if self.self_learning.should_retrain():
                    self.self_learning.retrain()
        
        return validated_signals
    
    def _combine_votes(self, votes: List[str], base_action: Optional[str] = None) -> str:
        """Combine votes from different models."""
        # Filter out None or empty votes
        filtered_votes = [vote for vote in votes if vote]
        if not filtered_votes:
            return base_action if base_action else 'hold'
        
        vote_counts = {}
        for vote in filtered_votes:
            vote_counts[vote] = vote_counts.get(vote, 0) + 1
        
        best_vote = max(vote_counts, key=lambda k: vote_counts[k])
        
        return best_vote
    
    def _calculate_confidence(self, votes: List[str], action: str) -> float:
        """Calculate confidence of ensemble decision."""
        # Filter out None or empty votes
        filtered_votes = [vote for vote in votes if vote]
        if not filtered_votes:
            return 0.5
        
        action_count = filtered_votes.count(action)
        return action_count / len(filtered_votes)
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 2 (Feature 2: Model Uncertainty)
    # =========================================================================
    
    def calculate_model_uncertainty(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Feature 2: Model Uncertainty Penalty
        Measure disagreement between models.
        P_final = P_win - β × uncertainty
        Reject trade if disagreement > threshold.
        """
        model_predictions = []
        
        if self.decision_tree_enabled and self.decision_tree.is_trained:
            try:
                dt_result = self.decision_tree.predict(market_data)
                if dt_result:
                    model_predictions.append({
                        'model': 'decision_tree',
                        'action': dt_result.get('action'),
                        'confidence': dt_result.get('confidence', 0.5)
                    })
            except Exception as e:
                logger.warning(f"Decision tree prediction failed: {e}")
        
        if self.self_learning_enabled and self.self_learning.model:
            try:
                sl_result = self.self_learning.predict(market_data)
                if sl_result:
                    model_predictions.append({
                        'model': 'self_learning',
                        'action': sl_result.get('action'),
                        'confidence': sl_result.get('confidence', 0.5)
                    })
            except Exception as e:
                logger.warning(f"Self-learning prediction failed: {e}")
        
        regime_probs = self.hmm.get_regime_probabilities()
        if regime_probs:
            model_predictions.append({
                'model': 'hmm',
                'action': regime_probs,
                'confidence': max(regime_probs.values()) if regime_probs else 0
            })
        
        if len(model_predictions) < 2:
            return {
                'uncertainty': 0.0,
                'disagreement': 0.0,
                'model_predictions': model_predictions,
                'allowed': True,
                'reason': 'Insufficient models for uncertainty calculation'
            }
        
        action_votes = {}
        for pred in model_predictions:
            action = pred.get('action')
            if isinstance(action, dict):
                continue
            action_votes[action] = action_votes.get(action, 0) + 1
        
        total_votes = len(model_predictions)
        if total_votes == 0:
            return {'uncertainty': 0.0, 'disagreement': 0.0, 'allowed': True}
        
        max_vote_count = max(action_votes.values()) if action_votes else 0
        disagreement = 1.0 - (max_vote_count / total_votes)
        
        confidence_scores = [p.get('confidence', 0) for p in model_predictions]
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0.5
        
        uncertainty = disagreement
        
        adjusted_prob = avg_confidence - (self.uncertainty_beta * uncertainty)
        
        if disagreement > self.uncertainty_threshold:
            logger.warning(
                f"Trade rejected: High model disagreement {disagreement:.2f} > {self.uncertainty_threshold}"
            )
            return {
                'uncertainty': uncertainty,
                'disagreement': disagreement,
                'adjusted_prob': adjusted_prob,
                'model_predictions': model_predictions,
                'allowed': False,
                'reason': f'Model disagreement {disagreement:.2f} > threshold {self.uncertainty_threshold}'
            }
        
        return {
            'uncertainty': uncertainty,
            'disagreement': disagreement,
            'adjusted_prob': adjusted_prob,
            'model_predictions': model_predictions,
            'allowed': True,
            'reason': 'Model uncertainty OK'
        }
    
    def get_decision_tree_accuracy(self) -> float:
        """Get decision tree accuracy on the last training data."""
        if not self._last_dt_X or not self._last_dt_y:
            return 0.0
        return self.decision_tree.get_accuracy(self._last_dt_X, self._last_dt_y)

    def get_status(self) -> Dict[str, Any]:
        """Get ensemble status."""
        # Get feature importance
        feature_importance = self._get_feature_importance()
        
        status = {
            'current_regime': self.current_regime,
            'price_history_len': len(self.price_history),
            'hmm': {
                'enabled': self.hmm_enabled,
                'current_regime': self.hmm.get_current_regime()
            },
            'decision_tree': {
                'enabled': self.decision_tree_enabled,
                'is_trained': self.decision_tree.is_trained,
                'accuracy': self.get_decision_tree_accuracy(),
                'feature_importance': feature_importance,
            },
            'self_learning': self.self_learning.get_status() if self.self_learning else {},
            'adaptive': self.adaptive.get_performance_report() if self.adaptive else {},
            'closed_loop': {
                'trades_outcome_recorded': self.trades_outcome_recorded,
                'total_reward_accumulated': round(self.total_reward_accumulated, 4),
                'pending_trades': len(self.pending_trades),
            }
        }
        
        # Add RL status if enabled
        if self.rl_enabled and self.rl_predictor:
            status['rl'] = self.rl_predictor.get_status()
            
        return status
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from decision tree."""
        importance_dict = {}
        
        # Try to get from decision tree model
        if self.decision_tree and self.decision_tree.is_trained:
            try:
                dt_model = getattr(self.decision_tree, 'model', None)
                if dt_model and hasattr(dt_model, 'feature_importances_'):
                    importances = dt_model.feature_importances_
                    feature_names = self.decision_tree.feature_names
                    for i, name in enumerate(feature_names):
                        if i < len(importances):
                            importance_dict[name] = float(importances[i])
            except Exception as e:
                logger.debug(f"Could not get DT feature importance: {e}")
        
        # If no importance from model, use default weights based on common indicators
        if not importance_dict:
            importance_dict = {
                'rsi': 0.25,
                'macd': 0.20,
                'ma_cross': 0.18,
                'volume_change': 0.15,
                'volatility': 0.12,
                'momentum': 0.10
            }
        
        # Sort by importance and return top 5
        sorted_imp = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_imp[:5])


def create_ensemble(config: Optional[Dict[str, Any]] = None) -> IntelligenceEnsemble:
    """Create intelligence ensemble."""
    return IntelligenceEnsemble(config or {})
