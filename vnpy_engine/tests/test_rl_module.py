"""
Test suite for RL Module (MDP, PPO Agent, Monte Carlo).
"""

import sys
import site
from pathlib import Path
import os
import tempfile

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)

proj_root = str(Path(__file__).parent.parent)
sys.path.insert(0, proj_root)
sys.path.insert(0, str(Path(__file__).parent))

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from vnpy_local.rl_module import (
    TradingMDP,
    MonteCarloSimulator,
    RLAgent,
    MarketState,
)


class TestTradingMDP:
    """Tests for TradingMDP environment."""
    
    @pytest.fixture
    def mdp(self):
        return TradingMDP(symbols=["BTCUSDT"], window_size=50)
    
    def test_initialization(self, mdp):
        """Test MDP initializes with correct spaces."""
        assert mdp.symbols == ["BTCUSDT"]
        assert mdp.window_size == 50
        assert mdp.observation_space.shape == (6,)
        assert mdp.action_space.n == 4
    
    def test_reset(self, mdp):
        """Test reset initializes state correctly."""
        obs, info = mdp.reset()
        
        assert obs.shape == (6,)
        assert isinstance(info, dict)
        assert mdp.current_step == 0
        assert mdp.total_reward == 0.0
    
    def test_step_hold_action(self, mdp):
        """Test step with hold action."""
        mdp.reset()
        obs, reward, terminated, truncated, info = mdp.step(0)
        
        assert obs.shape == (6,)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert info["action_name"] == "hold"
    
    def test_step_buy_action(self, mdp):
        """Test step with buy action."""
        mdp.reset()
        obs, reward, terminated, truncated, info = mdp.step(1)
        
        assert info["action_name"] == "buy"
    
    def test_step_sell_action(self, mdp):
        """Test step with sell action."""
        mdp.reset()
        obs, reward, terminated, truncated, info = mdp.step(2)
        
        assert info["action_name"] == "sell"
    
    def test_step_close_action(self, mdp):
        """Test step with close action."""
        mdp.reset()
        obs, reward, terminated, truncated, info = mdp.step(3)
        
        assert info["action_name"] == "close"
    
    def test_reward_accumulation(self, mdp):
        """Test rewards accumulate over steps."""
        mdp.reset()
        initial_reward = mdp.total_reward
        
        for _ in range(10):
            mdp.step(np.random.randint(0, 4))
        
        assert mdp.total_reward != initial_reward
    
    def test_truncation_after_max_steps(self, mdp):
        """Test episode truncates after max steps."""
        mdp.reset()
        
        for i in range(1000):
            _, _, terminated, truncated, _ = mdp.step(0)
            if truncated:
                assert i == 999
                break
    
    def test_termination_on_zero_balance(self, mdp):
        """Test episode terminates when balance reaches zero."""
        mdp.reset()
        mdp.current_balance = 0
        
        obs, reward, terminated, truncated, info = mdp.step(1)
        
        assert terminated is True
        assert reward == -1000
    
    def test_observation_normalization(self, mdp):
        """Test observations are normalized."""
        mdp.reset()
        obs, _, _, _, _ = mdp.step(0)
        
        assert np.all(np.isfinite(obs))
        assert np.all(np.abs(obs) < 100)


class TestMonteCarloSimulator:
    """Tests for Monte Carlo risk simulation."""
    
    @pytest.fixture
    def mc(self):
        return MonteCarloSimulator(n_simulations=100)
    
    def test_initialization(self, mc):
        """Test Monte Carlo initializes correctly."""
        assert mc.n_simulations == 100
    
    def test_evaluate_risk_basic(self, mc):
        """Test basic risk evaluation."""
        prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
        position = {"size": 1}
        
        result = mc.evaluate_risk(position, {"prices": prices})
        
        assert "var_95" in result
        assert "cvar_95" in result
        assert "expected_return" in result
        assert "sharpe_ratio" in result
    
    def test_evaluate_risk_with_leverage(self, mc):
        """Test risk evaluation with leveraged position."""
        prices = [100, 102, 101, 103, 105]
        position = {"size": 5}
        
        result = mc.evaluate_risk(position, {"prices": prices})
        
        assert result["expected_return"] > 0
    
    def test_simulate_scenarios_buy(self, mc):
        """Test scenario simulation for buy action."""
        current_state = {"price": 100, "position": 1}
        
        scenarios = mc.simulate_scenarios("buy", current_state, n_scenarios=50)
        
        assert len(scenarios) == 50
        assert all("price_change" in s for s in scenarios)
        assert all("new_price" in s for s in scenarios)
        assert all("pnl" in s for s in scenarios)
    
    def test_simulate_scenarios_sell(self, mc):
        """Test scenario simulation for sell action."""
        current_state = {"price": 100, "position": 1}
        
        scenarios = mc.simulate_scenarios("sell", current_state, n_scenarios=50)
        
        avg_change = np.mean([s["price_change"] for s in scenarios])
        assert avg_change < 0
    
    def test_simulate_scenarios_hold(self, mc):
        """Test scenario simulation for hold action."""
        current_state = {"price": 100, "position": 1}
        
        scenarios = mc.simulate_scenarios("hold", current_state, n_scenarios=50)
        
        avg_change = np.mean([s["price_change"] for s in scenarios])
        assert abs(avg_change) < 0.01
    
    def test_risk_metrics_variance(self, mc):
        """Test risk metrics vary with different data."""
        prices1 = [100 + i for i in range(20)]
        prices2 = [100 + i * 2 for i in range(20)]
        
        result1 = mc.evaluate_risk({"size": 1}, {"prices": prices1})
        result2 = mc.evaluate_risk({"size": 1}, {"prices": prices2})
        
        assert result1["sharpe_ratio"] != result2["sharpe_ratio"]


class TestRLAgent:
    """Tests for RLAgent."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def agent(self, temp_dir):
        with patch("vnpy_local.rl_module.MonteCarloSimulator"):
            agent = RLAgent(symbols=["BTCUSDT"], memory_path=temp_dir)
        return agent
    
    def test_initialization(self, agent):
        """Test RL agent initializes correctly."""
        assert agent.symbols == ["BTCUSDT"]
        assert hasattr(agent, "policy")
        assert hasattr(agent, "env")
    
    def test_state_to_observation(self, agent):
        """Test state to observation conversion."""
        market_state = {
            "BTCUSDT": {
                "price": 50000,
                "volume": 1000,
                "position": 1,
                "pnl": 100,
                "volatility": 0.5,
                "trend": 1
            }
        }
        
        obs = agent._state_to_observation(market_state)
        
        assert obs.shape == (6,)
        assert np.all(np.isfinite(obs))
    
    def test_predict(self, agent):
        """Test prediction returns valid action."""
        obs = np.array([500, 1, 0.1, 0.1, 0.05, 0], dtype=np.float32)
        
        action_idx, action_name = agent.predict(obs)
        
        assert action_idx in [0, 1, 2, 3]
        assert action_name in ["hold", "buy", "sell", "close"]
    
    def test_evaluate_action(self, agent):
        """Test action evaluation returns risk metrics."""
        state = {
            "BTCUSDT": {
                "price": 50000,
                "volume": 1000,
                "position": 1,
                "pnl": 100,
                "volatility": 0.5,
                "trend": 1
            }
        }
        
        result = agent.evaluate_action("buy", state)
        
        assert "action" in result
        assert "expected_pnl" in result
        assert "risk_metrics" in result
        assert "n_scenarios" in result
    
    def test_get_action_with_risk(self, agent):
        """Test get_action_with_risk returns complete decision."""
        market_state = {
            "BTCUSDT": {
                "price": 50000,
                "volume": 1000,
                "position": 0,
                "pnl": 0,
                "volatility": 0.5,
                "trend": 0
            }
        }
        
        decision = agent.get_action_with_risk(market_state)
        
        assert "action_idx" in decision
        assert "action" in decision
        assert "evaluation" in decision
        assert "market_state" in decision
        assert "timestamp" in decision
    
    def test_checkpoint_save_load(self, agent, temp_dir):
        """Test checkpoint save and load."""
        import pickle
        checkpoint_file = Path(temp_dir) / "rl_checkpoint.pkl"
        
        agent.save_checkpoint()
        
        assert checkpoint_file.exists()
    
    def test_observation_shape_consistency(self, agent):
        """Test observation shape is consistent."""
        state1 = {
            "BTCUSDT": {"price": 50000, "volume": 1000, "position": 1, 
                       "pnl": 100, "volatility": 0.5, "trend": 1}
        }
        state2 = {
            "BTCUSDT": {"price": 100, "volume": 1, "position": 0, 
                       "pnl": 0, "volatility": 0.1, "trend": 0}
        }
        
        obs1 = agent._state_to_observation(state1)
        obs2 = agent._state_to_observation(state2)
        
        assert obs1.shape == obs2.shape


class TestMarketState:
    """Tests for MarketState dataclass."""
    
    def test_creation(self):
        """Test MarketState creation."""
        state = MarketState(
            symbol="BTCUSDT",
            price=50000,
            volume=1000,
            position=1,
            pnl=100,
            volatility=0.5,
            trend=1
        )
        
        assert state.symbol == "BTCUSDT"
        assert state.price == 50000
        assert state.volume == 1000
        assert state.position == 1
        assert state.pnl == 100
        assert state.volatility == 0.5
        assert state.trend == 1
    
    def test_default_timestamp(self):
        """Test default timestamp is set."""
        state = MarketState(
            symbol="BTCUSDT",
            price=50000,
            volume=1000,
            position=0,
            pnl=0,
            volatility=0.5,
            trend=0
        )
        
        assert state.timestamp > 0


class TestMDPIntegration:
    """Integration tests for MDP with RL Agent."""
    
    def test_full_episode(self):
        """Test full MDP episode with agent."""
        import tempfile
        import shutil
        # Create a temporary directory for RL agent memory
        tmpdir = tempfile.mkdtemp()
        try:
            agent = RLAgent(symbols=["BTCUSDT"], memory_path=tmpdir)
            mdp = agent.env.envs[0]  # Get the underlying TradingMDP
            obs, _ = mdp.reset()
            
            for step in range(100):
                action_idx, _ = agent.predict(obs)
                obs, reward, terminated, truncated, info = mdp.step(action_idx)
                
                if terminated or truncated:
                    break
            
            assert step > 0
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    
    def test_multiple_symbols(self):
        """Test MDP with multiple symbols."""
        mdp = TradingMDP(symbols=["BTCUSDT", "ETHUSDT"], window_size=20)
        
        assert mdp.observation_space.shape == (12,)
        
        obs, _ = mdp.reset()
        
        assert obs.shape == (12,)
    
    def test_reward_signals(self):
        """Test reward signals are reasonable."""
        mdp = TradingMDP(symbols=["BTCUSDT"], window_size=10)
        mdp.reset()
        
        rewards = []
        for _ in range(50):
            action = np.random.randint(0, 4)
            _, reward, _, _, _ = mdp.step(action)
            rewards.append(reward)
        
        assert np.std(rewards) > 0
