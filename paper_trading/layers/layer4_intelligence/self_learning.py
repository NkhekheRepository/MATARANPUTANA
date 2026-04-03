"""
Layer 4: Self-Learning Engine
Online training from live market data.
"""

import time
import threading
import numpy as np
from typing import Dict, Any, List, Optional
from collections import deque
from loguru import logger


class SelfLearningEngine:
    """Self-learning engine for continuous model improvement."""
    
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('enabled', True)
        self.retrain_interval = config.get('retrain_interval', 60)
        self.min_samples = config.get('min_samples', 20)
        
        self.experience_buffer: deque = deque(maxlen=1000)
        
        self.last_retrain_time = time.time()
        self.retrain_count = 0
        
        self.model = None
        self.is_training = False
        
        self.callbacks: List[callable] = []
    
    def add_experience(self, state: Dict[str, Any], action: str, reward: float, 
                      next_state: Dict[str, Any] = None):
        """Add experience to buffer for learning."""
        experience = {
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'timestamp': time.time()
        }
        
        self.experience_buffer.append(experience)
    
    def should_retrain(self) -> bool:
        """Check if model should be retrained."""
        if not self.enabled:
            return False
        
        if len(self.experience_buffer) < self.min_samples:
            return False
        
        time_since_retrain = time.time() - self.last_retrain_time
        
        return time_since_retrain >= self.retrain_interval
    
    def retrain(self) -> bool:
        """Retrain model with accumulated experiences."""
        if not self.enabled:
            return False
        
        if len(self.experience_buffer) < self.min_samples:
            logger.warning(f"Not enough samples for retrain: {len(self.experience_buffer)}/{self.min_samples}")
            return False
        
        if self.is_training:
            logger.warning("Training already in progress")
            return False
        
        self.is_training = True
        
        try:
            logger.info(f"Starting self-learning retrain with {len(self.experience_buffer)} samples")
            
            experiences = list(self.experience_buffer)
            
            X = []
            y = []
            
            for exp in experiences:
                features = self._extract_features(exp['state'])
                action_map = {'hold': 0, 'buy': 1, 'sell': 2}
                label = action_map.get(exp['action'], 0)
                
                X.append(features)
                y.append(label)
            
            if self._train_model(X, y):
                self.last_retrain_time = time.time()
                self.retrain_count += 1
                
                logger.info(f"Self-learning complete: {self.retrain_count} retrains")
                
                self._notify_callbacks()
                
                return True
            
        except Exception as e:
            logger.error(f"Self-learning failed: {e}")
        
        finally:
            self.is_training = False
        
        return False
    
    def _extract_features(self, state: Dict[str, Any]) -> List[float]:
        """Extract features from state."""
        price = state.get('price', 0)
        price_history = state.get('price_history', [])
        
        if len(price_history) < 20:
            return [0] * 6
        
        prices = list(price_history[-20:])
        
        returns = [(prices[i+1] - prices[i]) / prices[i] for i in range(len(prices)-1)]
        
        return [
            (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0,
            float(np.std(returns)) if returns else 0,
            float(np.mean(returns[-5:])) if len(returns) >= 5 else 0,
            float(np.mean(returns[-10:])) if len(returns) >= 10 else 0,
            state.get('rsi', 50) / 100,
            state.get('volume', 0) / 1000
        ]
    
    def _train_model(self, X: List[List[float]], y: List[int]) -> bool:
        """Train the model."""
        try:
            import numpy as np
            from sklearn.tree import DecisionTreeClassifier
            
            X_array = np.array(X)
            y_array = np.array(y)
            
            self.model = DecisionTreeClassifier(max_depth=5, random_state=42)
            self.model.fit(X_array, y_array)
            
            return True
            
        except Exception as e:
            logger.error(f"Model training error: {e}")
            return False
    
    def predict(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Predict action using learned model."""
        if self.model is None:
            return None
        
        try:
            features = np.array(self._extract_features(state)).reshape(1, -1)
            action_idx = self.model.predict(features)[0]
            
            action_map = {0: 'hold', 1: 'buy', 2: 'sell'}
            
            return {
                'action': action_map.get(action_idx, 'hold'),
                'confidence': float(max(self.model.predict_proba(features)[0])),
                'action_idx': int(action_idx)
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None
    
    def add_callback(self, callback: callable):
        """Add callback to be notified after retrain."""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self):
        """Notify all callbacks of retrain completion."""
        for callback in self.callbacks:
            try:
                callback(self.retrain_count)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_model_accuracy(self, X: Optional[List[List[float]]] = None, y: Optional[List[int]] = None) -> float:
        """Compute model accuracy on provided data or on the experience buffer."""
        if self.model is None:
            return 0.0

        try:
            if X is not None and y is not None:
                X_arr = np.array(X)
                y_arr = np.array(y)
            else:
                experiences = list(self.experience_buffer)
                if len(experiences) < 2:
                    return 0.0
                action_map = {'hold': 0, 'buy': 1, 'sell': 2}
                X_arr = np.array([self._extract_features(exp['state']) for exp in experiences])
                y_arr = np.array([action_map.get(exp['action'], 0) for exp in experiences])

            predictions = self.model.predict(X_arr)
            return float(np.mean(predictions == y_arr))
        except Exception as e:
            logger.error(f"Accuracy computation error: {e}")
            return 0.0

    def get_status(self) -> Dict[str, Any]:
        """Get self-learning status."""
        return {
            'enabled': self.enabled,
            'buffer_size': len(self.experience_buffer),
            'min_samples_required': self.min_samples,
            'last_retrain': self.last_retrain_time,
            'retrain_count': self.retrain_count,
            'is_training': self.is_training,
            'time_to_retrain': max(0, self.retrain_interval - (time.time() - self.last_retrain_time)),
            'model_accuracy': self.get_model_accuracy(),
        }


self_learning_engine = SelfLearningEngine({'enabled': True, 'retrain_interval': 1800, 'min_samples': 100})


def learn_from_trade(state: Dict[str, Any], action: str, reward: float):
    """Convenience function to add learning experience."""
    self_learning_engine.add_experience(state, action, reward)
    
    if self_learning_engine.should_retrain():
        self_learning_engine.retrain()
