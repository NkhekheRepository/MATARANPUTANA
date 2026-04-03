#!/usr/bin/env python3
"""
Debug ArrayManager behavior.
"""

import sys
import site
from pathlib import Path

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)
sys.path.insert(0, '/home/ubuntu/financial_orchestrator/vnpy_engine')
sys.path.insert(0, '/home/ubuntu/financial_orchestrator/vnpy_engine/vnpy_local')
sys.path.insert(0, '/home/ubuntu/financial_orchestrator/vnpy_engine/tests')

from vnpy.trader.object import BarData
from conftest import SyntheticDataGenerator
from vnpy.trader.utility import ArrayManager

am = ArrayManager(100)

gen = SyntheticDataGenerator(initial_price=50000)
bars = gen.generate_trending_bars(n=50, trend="up")

print(f"Processing {len(bars)} bars...")

for i, bar in enumerate(bars):
    am.update_bar(bar)
    
    if i >= 14:
        ma5 = am.sma(5)
        ma15 = am.sma(15)
        print(f"Bar {i+1:3d}: am.inited={am.inited}, close={bar.close_price:.2f}, "
              f"ma5={ma5:.2f}, ma15={ma15:.2f}")
    
    if i == 15:
        print(f"am.count = {am.count}")
        print(f"am.close = {am.close[:20] if hasattr(am, 'close') else 'N/A'}")