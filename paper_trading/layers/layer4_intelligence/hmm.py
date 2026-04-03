"""
Layer 4: Hidden Markov Model (HMM) Regime Detection
Detects market regimes: bull, bear, volatile, sideways
"""

from typing import Dict, Any, List, Optional
import numpy as np
from loguru import logger

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    GaussianHMM = None  # type: ignore

try:
    from sklearn.preprocessing import StandardScaler
    SCALER_AVAILABLE = True
except ImportError:
    SCALER_AVAILABLE = False
    StandardScaler = None  # type: ignore


REGIME_NAMES = ['bull', 'bear', 'sideways', 'volatile']


class HMMRegimeDetector:
    """Hidden Markov Model for market regime detection."""
    
    def __init__(self, config: Dict[str, Any]):
        self.n_states = config.get('n_states', 4)
        self.lookback_bars = config.get('lookback_bars', 100)
        self.retrain_interval = config.get('retrain_interval', 50)
        
        self.model = None
        self.scaler = None
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        
        self.current_regime = 'sideways'
        self.model_trained = False
        self._last_train_bar = 0
        
        if HMM_AVAILABLE:
            self._init_model()
    
    def _init_model(self):
        """Initialize HMM model and scaler."""
        try:
            self.model = GaussianHMM(  # type: ignore[operator]
                n_components=self.n_states,
                covariance_type="full",
                n_iter=100,
                random_state=42
            )
            if SCALER_AVAILABLE:
                self.scaler = StandardScaler()
            logger.info(f"HMM model initialized with {self.n_states} states, scaler={'yes' if self.scaler else 'no'}")
        except Exception as e:
            logger.error(f"Failed to initialize HMM: {e}")
    
    def update(self, price: float, volume: float = 0) -> str:
        """Update with new price/volume and detect regime."""
        self.price_history.append(price)
        if volume > 0:
            self.volume_history.append(volume)
        
        if len(self.price_history) < self.lookback_bars:
            self.current_regime = self._estimate_regime_simple()
            return self.current_regime
        
        regime, _ = self._predict_regime()
        self.current_regime = regime
        return self.current_regime
    
    def detect_regime(self) -> str:
        """Detect current market regime."""
        if len(self.price_history) < self.lookback_bars:
            return self._estimate_regime_simple()
        
        regime, _ = self._predict_regime()
        return regime
    
    def _predict_regime(self) -> tuple:
        """
        Unified prediction path. Returns (regime_name, probabilities_dict).
        Handles training cadence, feature scaling, and learned state mapping.
        """
        if not HMM_AVAILABLE or self.model is None:
            return self._estimate_regime_simple(), self._uniform_probs()
        
        try:
            features = self._extract_features()
            
            if features is None or len(features) == 0:
                return self._estimate_regime_simple(), self._uniform_probs()
            
            should_train = (
                not self.model_trained or
                (len(self.price_history) - self._last_train_bar) >= self.retrain_interval
            )
            
            if should_train:
                self._train_on_features(features)
            
            hidden_states = self.model.predict(features)
            current_state = int(hidden_states[-1])
            
            regime = self._map_state_to_regime(current_state, features)
            probs = self._get_state_probabilities(features)
            
            return regime, probs
            
        except Exception as e:
            logger.error(f"HMM prediction error: {e}")
            return self._estimate_regime_simple(), self._uniform_probs()
    
    def _train_on_features(self, features: np.ndarray):
        """Train the HMM model on scaled features."""
        scaled = self._scale_features(features, fit=True)
        if scaled is None:
            return
        
        self.model.fit(scaled)
        
        if hasattr(self.model, 'transmat_') and self.model.transmat_ is not None:
            row_sums = self.model.transmat_.sum(axis=1)
            bad_rows = np.where(np.abs(row_sums - 1.0) > 1e-6)[0]
            if len(bad_rows) > 0:
                n = self.model.transmat_.shape[0]
                self.model.transmat_ = np.ones((n, n), dtype=np.float64) / n
                logger.debug("HMM transmat repaired: rows did not sum to 1, reset to uniform")
        
        self.model_trained = True
        self._last_train_bar = len(self.price_history)
        logger.info(f"HMM model trained on {len(features)} bars (bar {self._last_train_bar})")
    
    def _scale_features(self, features: np.ndarray, fit: bool = False) -> Optional[np.ndarray]:
        """Scale features and sanitize NaN/Inf values."""
        features = np.asarray(features, dtype=np.float64)
        
        features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
        
        if not np.isfinite(features).all():
            logger.warning("Non-finite values detected after sanitization, falling back")
            return None
        
        if self.scaler is not None:
            if fit:
                return self.scaler.fit_transform(features)
            else:
                return self.scaler.transform(features)
        
        return features
    
    def _extract_features(self) -> Optional[np.ndarray]:
        """Extract features from price history."""
        n = min(len(self.price_history), self.lookback_bars)
        if n < 2:
            return None
        
        prices = np.array(self.price_history[-n:], dtype=np.float64)
        
        if np.any(prices <= 0):
            logger.warning("Non-positive prices detected in feature extraction")
            return None
        
        returns = np.diff(prices) / prices[:-1]
        returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
        
        if len(returns) < 5:
            return None
        
        vol_5 = np.array([np.std(returns[max(0, i-5):i+1]) for i in range(len(returns))])
        vol_20 = np.array([np.std(returns[max(0, i-20):i+1]) for i in range(len(returns))])
        vol_ratio = vol_5 / (vol_20 + 1e-10)
        
        features = np.column_stack([
            returns,
            vol_ratio,
            np.abs(returns),
        ])
        
        features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
        
        if not np.isfinite(features).all():
            return None
        
        return features
    
    def _estimate_regime_simple(self) -> str:
        """Simple regime estimation without HMM."""
        if len(self.price_history) < 20:
            return 'sideways'
        
        prices = self.price_history[-20:]
        returns = np.diff(prices) / prices[:-1]
        
        trend = (prices[-1] - prices[0]) / prices[0]
        volatility = np.std(returns)
        
        if volatility > 0.03:
            return 'volatile'
        elif trend > 0.02:
            return 'bull'
        elif trend < -0.02:
            return 'bear'
        else:
            return 'sideways'
    
    def _map_state_to_regime(self, state: int, features: np.ndarray) -> str:
        """Map HMM state to regime name using learned model.means_."""
        if not hasattr(self.model, 'means_') or self.model.means_ is None:
            return REGIME_NAMES[state % len(REGIME_NAMES)]
        
        n_states = len(self.model.means_)
        
        state_returns = []
        state_vols = []
        for s in range(n_states):
            means = self.model.means_[s]
            if len(means) >= 2:
                state_returns.append(means[0])
                state_vols.append(means[1])
            else:
                state_returns.append(0.0)
                state_vols.append(0.0)
        
        state_returns = np.array(state_returns)
        state_vols = np.array(state_vols)
        
        vol_threshold = np.mean(state_vols) + 0.5 * np.std(state_vols) if len(state_vols) > 1 else 0.02
        
        if state_vols[state] > vol_threshold:
            return 'volatile'
        
        if state_returns[state] > 0.001:
            return 'bull'
        elif state_returns[state] < -0.001:
            return 'bear'
        else:
            return 'sideways'
    
    def _get_state_probabilities(self, features: np.ndarray) -> Dict[str, float]:
        """Get probability distribution over regimes for the latest bar."""
        try:
            scaled = self._scale_features(features[-1:].reshape(1, -1) if features.ndim == 2 else features, fit=False)
            if scaled is None:
                return self._uniform_probs()
            
            if hasattr(self.model, 'predict_proba'):
                probs = self.model.predict_proba(scaled)
                last_probs = probs[-1] if probs.ndim > 1 else probs
                
                state_regimes = []
                for s in range(self.n_states):
                    state_regimes.append(self._map_state_to_regime(s, features))
                
                regime_probs = self._uniform_probs()
                for s in range(self.n_states):
                    regime_name = state_regimes[s]
                    regime_probs[regime_name] += float(last_probs[s])
                
                total = sum(regime_probs.values())
                if total > 0:
                    regime_probs = {k: v / total for k, v in regime_probs.items()}
                
                return regime_probs
        except Exception as e:
            logger.debug(f"Probability estimation failed: {e}")
        
        return self._uniform_probs()
    
    def _uniform_probs(self) -> Dict[str, float]:
        """Return uniform probability distribution."""
        return {regime: 1.0 / len(REGIME_NAMES) for regime in REGIME_NAMES}
    
    def train(self, prices: List[float], volumes: Optional[List[float]] = None):
        """Train HMM on historical data."""
        if not HMM_AVAILABLE or self.model is None:
            logger.warning("HMM not available, skipping training")
            return
        
        if len(prices) < 100:
            logger.warning("Not enough data for training")
            return
        
        self.price_history = prices
        if volumes:
            self.volume_history = volumes
        
        try:
            features = self._extract_features()
            if features is not None:
                self._train_on_features(features)
                logger.info("HMM model trained successfully")
        except Exception as e:
            logger.error(f"HMM training failed: {e}")
    
    def get_current_regime(self) -> str:
        """Get current detected regime."""
        return self.current_regime
    
    def get_regime_probabilities(self) -> Dict[str, float]:
        """Get probability distribution over regimes."""
        if not HMM_AVAILABLE or self.model is None or len(self.price_history) < self.lookback_bars:
            return self._uniform_probs()
        
        try:
            features = self._extract_features()
            if features is None:
                return self._uniform_probs()
            return self._get_state_probabilities(features)
        except Exception:
            return self._uniform_probs()


def detect_market_regime(price: float, volume: float = 0, 
                         history: Optional[List[float]] = None) -> str:
    """Convenience function to detect regime."""
    detector = HMMRegimeDetector({'n_states': 4, 'lookback_bars': 100})
    
    if history:
        for p in history:
            detector.update(p)
    
    return detector.update(price, volume)
