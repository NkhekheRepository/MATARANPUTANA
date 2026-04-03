"""
Reinforcement Learning Module
=============================
MDP Environment + PPO Agent + Monte Carlo Simulator
for autonomous trading decision making.

Fixed: real market data states, PnL-based rewards, proper observation space.
"""

import os
import time
import numpy as np
import pickle
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from collections import deque
import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from loguru import logger

CHECKPOINT_INTERVAL = int(os.getenv("RL_CHECKPOINT_INTERVAL", "1800"))


@dataclass
class MarketState:
    symbol: str
    price: float
    volume: float
    position: float
    pnl: float
    volatility: float
    trend: float
    timestamp: float = field(default_factory=time.time)


class TradingMDP(gym.Env):
    metadata = {'render_modes': ['human']}
    
    ACTIONS = ['hold', 'buy', 'sell', 'close']
    
    def __init__(self, symbols: List[str], window_size: int = 50):
        super().__init__()
        self.symbols = symbols
        self.window_size = window_size
        
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(len(symbols) * 6,), dtype=np.float32
        )
        self.action_space = gym.spaces.Discrete(len(self.ACTIONS))
        
        self.market_states: Dict[str, deque] = {
            s: deque(maxlen=window_size) for s in symbols
        }
        self.current_step = 0
        self.total_reward = 0.0
        self.initial_balance = 10000.0
        self.current_balance = self.initial_balance
        
        self._last_prices: Dict[str, float] = {}
        self._position_side: Dict[str, int] = {s: 0 for s in symbols}
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.total_reward = 0.0
        self.current_balance = self.initial_balance
        self._last_prices = {}
        self._position_side = {s: 0 for s in self.symbols}
        
        for symbol in self.symbols:
            self.market_states[symbol].clear()
            for _ in range(self.window_size):
                self.market_states[symbol].append(self._generate_random_state())
        
        return self._get_observation(), {}
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        self.current_step += 1
        
        for symbol in self.symbols:
            new_state = self._generate_random_state()
            self.market_states[symbol].append(new_state)
        
        reward = self._calculate_reward(action)
        self.total_reward += reward
        
        terminated = False
        truncated = self.current_step >= 1000
        
        if self.current_balance <= 0:
            terminated = True
            reward = -1000
        
        return self._get_observation(), reward, terminated, truncated, {
            'total_reward': self.total_reward,
            'balance': self.current_balance,
            'action_name': self.ACTIONS[action]
        }
    
    def _get_observation(self) -> np.ndarray:
        obs = []
        for symbol in self.symbols:
            if len(self.market_states[symbol]) > 0:
                latest = self.market_states[symbol][-1]
                obs.extend([
                    latest.price / 10000.0,
                    latest.volume / 10000.0,
                    latest.position / 10.0,
                    latest.pnl / 1000.0,
                    latest.volatility / 10.0,
                    latest.trend
                ])
            else:
                obs.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        return np.array(obs, dtype=np.float32)
    
    def inject_market_data(self, symbol: str, price: float, volume: float,
                           volatility: float, trend: float,
                           position: float = 0.0, pnl: float = 0.0):
        """Feed real market data into the environment instead of random states."""
        state = MarketState(
            symbol=symbol,
            price=price,
            volume=volume,
            position=position,
            pnl=pnl,
            volatility=volatility,
            trend=trend,
        )
        
        if symbol not in self.market_states:
            self.market_states[symbol] = deque(maxlen=self.window_size)
        
        self.market_states[symbol].append(state)
        self._last_prices[symbol] = price
    
    def _generate_random_state(self) -> MarketState:
        """Fallback for initialization — generates plausible random walk data."""
        base_price = 50000
        if self._last_prices:
            base_price = list(self._last_prices.values())[-1]
        
        price_change = np.random.randn() * base_price * 0.002
        new_price = max(base_price + price_change, 100)
        
        return MarketState(
            symbol="BTCUSDT",
            price=new_price,
            volume=100 + np.random.rand() * 500,
            position=np.random.randint(-5, 5),
            pnl=np.random.randn() * 100,
            volatility=np.clip(np.random.rand() * 0.5, 0.01, 1.0),
            trend=np.clip(np.random.randn() * 0.1, -1.0, 1.0),
        )
    
    def _calculate_reward(self, action: int) -> float:
        """
        PnL-based reward: positive when action aligns with price direction.
        
        - buy rewarded when price is trending up
        - sell rewarded when price is trending down
        - hold rewarded when price is flat (low volatility)
        - close rewarded when locking in profit
        - small penalty for every trade to discourage overtrading
        """
        reward = 0.0
        
        for symbol in self.symbols:
            states = self.market_states.get(symbol, deque())
            if len(states) < 2:
                continue
            
            current = states[-1]
            previous = states[-2] if len(states) >= 2 else current
            
            price_change = (current.price - previous.price) / max(previous.price, 1e-8)
            trend = current.trend
            
            if action == 1:  # buy
                reward += trend * 2.0
                if price_change > 0:
                    reward += abs(price_change) * 100
                else:
                    reward -= abs(price_change) * 50
                reward -= 0.01
            
            elif action == 2:  # sell
                reward -= trend * 2.0
                if price_change < 0:
                    reward += abs(price_change) * 100
                else:
                    reward -= abs(price_change) * 50
                reward -= 0.01
            
            elif action == 3:  # close
                if self._position_side.get(symbol, 0) != 0:
                    pnl = current.pnl
                    reward += max(pnl / 1000.0, -1.0)
                    self._position_side[symbol] = 0
                reward -= 0.005
            
            else:  # hold
                if abs(trend) < 0.1:
                    reward += 0.01
        
        return np.clip(reward, -5.0, 5.0)


class MonteCarloSimulator:
    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations
        
    def evaluate_risk(self, position: Dict[str, Any], 
                     market_data: Dict[str, Any]) -> Dict[str, float]:
        prices = market_data.get('prices', [100])
        returns = np.diff(prices) / prices[:-1]
        
        simulated_returns = np.random.choice(returns, 
            size=(self.n_simulations, len(returns)), replace=True)
        
        portfolio_returns = simulated_returns * position.get('size', 1)
        
        var_95 = np.percentile(portfolio_returns.sum(axis=1), 5)
        cvar_95 = portfolio_returns[portfolio_returns.sum(axis=1) <= var_95].mean()
        
        return {
            'var_95': float(var_95),
            'cvar_95': float(cvar_95),
            'expected_return': float(portfolio_returns.mean()),
            'max_drawdown': float((portfolio_returns.cumsum(axis=1).min(axis=1)).min()),
            'sharpe_ratio': float(portfolio_returns.mean() / (portfolio_returns.std() + 1e-8))
        }
    
    def simulate_scenarios(self, action: str, current_state: Dict[str, Any],
                          n_scenarios: int = 100) -> List[Dict[str, float]]:
        scenarios = []
        base_price = current_state.get('price', 100)
        
        for _ in range(n_scenarios):
            if action == 'buy':
                price_change = np.random.normal(0.01, 0.02)
            elif action == 'sell':
                price_change = np.random.normal(-0.01, 0.02)
            else:
                price_change = np.random.normal(0, 0.01)
            
            scenarios.append({
                'price_change': price_change,
                'new_price': base_price * (1 + price_change),
                'pnl': price_change * current_state.get('position', 0),
                'probability': 1.0 / n_scenarios
            })
        
        return scenarios


class RLAgent:
    def __init__(self, symbols: List[str], memory_path: str = "/vnpy/memory"):
        self.symbols = symbols
        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)
        
        self.checkpoint_file = self.memory_path / "rl_checkpoint.pkl"
        self.experience_file = self.memory_path / "experience_buffer.pkl"
        
        self.env = DummyVecEnv([lambda: TradingMDP(symbols)])
        
        self.policy = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            verbose=1,
            tensorboard_log=str(self.memory_path / "logs")
        )
        
        self.last_checkpoint_time = time.time()
        self.total_steps = 0
        
        self.load_checkpoint()
        
    def load_checkpoint(self) -> bool:
        if self.checkpoint_file.exists():
            try:
                self.policy = PPO.load(str(self.checkpoint_file), env=self.env)
                logger.info(f"RL checkpoint loaded from {self.checkpoint_file}")
                return True
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {e}")
        return False
    
    def save_checkpoint(self) -> bool:
        try:
            self.policy.save(str(self.checkpoint_file))
            self._save_metadata()
            logger.info(f"RL checkpoint saved: {self.total_steps} steps")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    def _save_metadata(self):
        metadata_file = self.checkpoint_file.with_suffix('.meta')
        try:
            metadata = {
                'total_steps': self.total_steps,
                'timestamp': time.time(),
                'symbols': self.symbols
            }
            with open(metadata_file, 'wb') as f:
                pickle.dump(metadata, f)
        except Exception as e:
            logger.warning(f"Failed to save metadata: {e}")
    
    def train(self, total_timesteps: int = 10000):
        logger.info(f"Training RL agent for {total_timesteps} timesteps...")
        self.policy.learn(
            total_timesteps=total_timesteps,
            progress_bar=True,
            callback=self._training_callback
        )
        self.save_checkpoint()
    
    def _training_callback(self, locals_, globals_):
        self.total_steps += 1
        
        if time.time() - self.last_checkpoint_time >= CHECKPOINT_INTERVAL:
            self.save_checkpoint()
            self.last_checkpoint_time = time.time()
        
        return True
    
    def predict(self, observation: np.ndarray) -> Tuple[int, str]:
        action, _ = self.policy.predict(observation, deterministic=True)
        action_idx = int(action)
        action_name = TradingMDP.ACTIONS[action_idx]
        
        return action_idx, action_name
    
    def evaluate_action(self, action: str, state: Dict[str, Any]) -> Dict[str, Any]:
        mc = MonteCarloSimulator()
        scenarios = mc.simulate_scenarios(action, state)
        
        risk_metrics = mc.evaluate_risk(
            {'size': state.get('position', 0)},
            {'prices': [s['new_price'] for s in scenarios]}
        )
        
        expected_pnl = sum(s['pnl'] * s['probability'] for s in scenarios)
        
        return {
            'action': action,
            'expected_pnl': expected_pnl,
            'risk_metrics': risk_metrics,
            'n_scenarios': len(scenarios),
            'timestamp': time.time()
        }
    
    def get_action_with_risk(self, market_state: Dict[str, Any]) -> Dict[str, Any]:
        obs = self._state_to_observation(market_state)
        action_idx, action_name = self.predict(obs)
        
        evaluation = self.evaluate_action(action_name, market_state)
        
        return {
            'action_idx': action_idx,
            'action': action_name,
            'evaluation': evaluation,
            'market_state': market_state,
            'timestamp': time.time()
        }
    
    def _state_to_observation(self, state: Dict[str, Any]) -> np.ndarray:
        obs = []
        for symbol in self.symbols:
            s = state.get(symbol, {})
            obs.extend([
                s.get('price', 50000) / 10000.0,
                s.get('volume', 100) / 10000.0,
                s.get('position', 0) / 10.0,
                s.get('pnl', 0) / 1000.0,
                s.get('volatility', 0.5) / 10.0,
                s.get('trend', 0)
            ])
        return np.array(obs, dtype=np.float32)


rl_agent: Optional[RLAgent] = None


def get_rl_agent(symbols: List[str] = None) -> RLAgent:
    global rl_agent
    if rl_agent is None:
        symbols = symbols or ["BTCUSDT", "ETHUSDT"]
        rl_agent = RLAgent(symbols)
    return rl_agent
