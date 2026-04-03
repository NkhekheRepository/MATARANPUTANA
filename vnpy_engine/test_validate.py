import sys
import site
from pathlib import Path
from unittest.mock import Mock, patch

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)
proj_root = str(Path(__file__).parent)
sys.path.insert(0, proj_root)
sys.path.insert(0, str(Path(__file__).parent / "tests"))

from vnpy.trader.object import BarData
from vnpy.trader.constant import Interval, Exchange
from datetime import datetime
from conftest import SyntheticDataGenerator
from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy

def test_validate_with_rl():
    print("=== Testing _validate_with_rl method ===")
    
    mock_rl_agent = Mock()
    
    with patch('vnpy_local.rl_module.get_rl_agent', create=True) as mock_get_rl:
        mock_get_rl.return_value = mock_rl_agent
        
        # Create mock CTA engine with write_log method
        mock_cta_engine = Mock()
        mock_cta_engine.write_log = Mock()
        
        # Create mock strategy with required attributes
        strategy = RlEnhancedCtaStrategy.__new__(RlEnhancedCtaStrategy)
        strategy.rl_agent = mock_rl_agent
        strategy.rl_enabled = True
        strategy.pos = 0
        strategy.vt_symbol = "BTCUSDT"
        strategy.cta_engine = mock_cta_engine
        strategy.write_log = mock_cta_engine.write_log
        
        # Create a mock bar
        bar = BarData(
            gateway_name="mock",
            symbol="BTCUSDT",
            exchange=Exchange.SMART,
            datetime=datetime.now(),
            interval=Interval.MINUTE,
            open_price=50000,
            high_price=51000,
            low_price=49000,
            close_price=50000,
            volume=100,
            turnover=0,
            open_interest=0
        )
        
        # Test 1: RL says "hold" for bullish signal -> should return False
        mock_rl_agent.get_action_with_risk.return_value = {
            "action": "hold",
            "action_idx": 0,
            "evaluation": {"expected_pnl": -50, "risk_metrics": {"var_95": -0.1}},
            "market_state": {},
            "timestamp": 0
        }
        
        result = strategy._validate_with_rl(bar, 1)  # bullish signal
        print(f"Test 1 - Bullish signal, RL hold: {result} (expected: False)")
        
        # Test 2: RL says "hold" for bearish signal -> should return False
        result = strategy._validate_with_rl(bar, -1)  # bearish signal
        print(f"Test 2 - Bearish signal, RL hold: {result} (expected: False)")
        
        # Test 3: RL says "buy" for bullish signal -> should return True
        mock_rl_agent.get_action_with_risk.return_value = {
            "action": "buy",
            "action_idx": 1,
            "evaluation": {"expected_pnl": 50, "risk_metrics": {"var_95": -0.02}},
            "market_state": {},
            "timestamp": 0
        }
        
        result = strategy._validate_with_rl(bar, 1)  # bullish signal
        print(f"Test 3 - Bullish signal, RL buy: {result} (expected: True)")
        
        # Test 4: RL says "sell" for bearish signal -> should return True
        result = strategy._validate_with_rl(bar, -1)  # bearish signal
        print(f"Test 4 - Bearish signal, RL sell: {result} (expected: True)")
        
        # Test 5: RL says "buy" for bearish signal -> should return False
        result = strategy._validate_with_rl(bar, -1)  # bearish signal
        print(f"Test 5 - Bearish signal, RL buy: {result} (expected: False)")
        
        # Test 6: RL says "sell" for bullish signal -> should return False
        result = strategy._validate_with_rl(bar, 1)  # bullish signal
        print(f"Test 6 - Bullish signal, RL sell: {result} (expected: False)")

if __name__ == "__main__":
    test_validate_with_rl()
