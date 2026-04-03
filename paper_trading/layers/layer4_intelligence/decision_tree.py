"""
Layer 4: Markov Decision Tree
Interpretable decision tree for state-based actions.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from loguru import logger

try:
    from sklearn.tree import DecisionTreeClassifier, export_text
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class DecisionTreeAgent:
    """Decision tree for trading decisions."""
    
    def __init__(self, config: Dict[str, Any]):
        self.max_depth = config.get('max_depth', 5)
        self.model = None
        
        self.feature_names = [
            'price_change', 'volume_change', 'volatility',
            'rsi', 'ma_cross', 'momentum'
        ]
        
        self.action_map = {0: 'hold', 1: 'buy', 2: 'sell'}
        
        if SKLEARN_AVAILABLE:
            self._init_model()
        
        self.is_trained = False
    
    def _init_model(self):
        """Initialize decision tree model."""
        self.model = DecisionTreeClassifier(
            max_depth=self.max_depth,
            random_state=42,
            min_samples_leaf=10
        )
    
    def prepare_features(self, market_data: Dict[str, Any]) -> np.ndarray:
        """Prepare features from market data."""
        price = market_data.get('price', market_data.get('close', 0))
        volume = market_data.get('volume', 0)
        
        price_history = market_data.get('price_history', [])
        volume_history = market_data.get('volume_history', [])
        
        if len(price_history) < 20:
            return np.zeros(6)
        
        prices = np.array(price_history[-20:])
        volumes = np.array(volume_history[-20:]) if volume_history else np.ones(20)
        
        returns = np.diff(prices) / prices[:-1]
        
        price_change = (prices[-1] - prices[0]) / prices[0]
        volume_change = (volumes[-1] - np.mean(volumes[:-5])) / np.mean(volumes[:-5]) if len(volumes) > 5 else 0
        volatility = np.std(returns)
        
        sma_fast = np.mean(prices[-10:])
        sma_slow = np.mean(prices[-20:])
        ma_cross = 1 if sma_fast > sma_slow else -1
        
        gains = np.sum(returns[returns > 0]) if len(returns) > 0 else 0
        losses = abs(np.sum(returns[returns < 0])) if len(returns) > 0 else 0
        rs = gains / (losses + 1e-8)
        rsi = 100 - (100 / (1 + rs))
        
        momentum = np.mean(returns[-5:]) if len(returns) >= 5 else 0
        
        return np.array([price_change, volume_change, volatility, rsi / 100, ma_cross, momentum])
    
    def predict(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict action based on market data."""
        features = self.prepare_features(market_data).reshape(1, -1)
        
        if not self.is_trained or self.model is None:
            return self._default_prediction(features)
        
        try:
            action_idx = self.model.predict(features)[0]
            action = self.action_map.get(action_idx, 'hold')
            
            proba = self.model.predict_proba(features)[0]
            
            return {
                'action': action,
                'confidence': float(max(proba)),
                'action_idx': int(action_idx),
                'features': features[0].tolist()
            }
        except Exception as e:
            logger.error(f"Decision tree prediction error: {e}")
            return self._default_prediction(features)
    
    def _default_prediction(self, features: np.ndarray) -> Dict[str, Any]:
        """Default prediction when not trained."""
        price_change = features[0, 0]
        momentum = features[0, 5] if features.shape[1] > 5 else 0
        
        trend_strength = abs(price_change)
        if trend_strength > 0.02 and momentum > 0:
            return {'action': 'buy', 'confidence': 0.5}
        elif trend_strength > 0.02 and momentum < 0:
            return {'action': 'sell', 'confidence': 0.5}
        else:
            return {'action': 'hold', 'confidence': 0.7}
    
    def train(self, X: List[List[float]], y: List[int]):
        """Train decision tree on historical data."""
        if not SKLEARN_AVAILABLE or self.model is None:
            logger.warning("Sklearn not available, skipping training")
            return
        
        try:
            X_array = np.array(X)
            y_array = np.array(y)
            
            self.model.fit(X_array, y_array)
            self.is_trained = True
            
            tree_rules = export_text(self.model, feature_names=self.feature_names)
            logger.info(f"Decision tree trained\n{tree_rules}")
            
        except Exception as e:
            logger.error(f"Decision tree training failed: {e}")
    
    def get_rules(self) -> str:
        """Get decision tree rules as text."""
        if not SKLEARN_AVAILABLE or self.model is None:
            return "Model not available"

        try:
            return export_text(self.model, feature_names=self.feature_names)
        except Exception as e:
            return f"Error: {e}"

    def get_accuracy(self, X: List[List[float]], y: List[int]) -> float:
        """Compute accuracy of the model on provided data."""
        if not SKLEARN_AVAILABLE or self.model is None or not self.is_trained:
            return 0.0
        try:
            X_arr = np.array(X)
            y_arr = np.array(y)
            predictions = self.model.predict(X_arr)
            return float(np.mean(predictions == y_arr))
        except Exception as e:
            logger.error(f"Accuracy computation error: {e}")
            return 0.0


def create_decision_tree(trading_data: List[Dict[str, Any]], 
                         actions: List[int]) -> DecisionTreeAgent:
    """Create and train decision tree from historical data."""
    config = {'max_depth': 5}
    agent = DecisionTreeAgent(config)
    
    X = []
    for data in trading_data:
        features = agent.prepare_features(data)
        X.append(features.tolist())
    
    agent.train(X, actions)
    
    return agent
