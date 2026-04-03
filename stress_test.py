#!/usr/bin/env python3
"""
Stress Test Suite for Financial Orchestrator
Tests all components under load with 8GB RAM constraint
"""

import sys
import os
import time
import json
import threading
import gc
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

from monitoring.risk_monitor import RiskMonitor, RiskLevel
from optimization.agent_optimizer import AgentOptimizer
from validation.validation_engine import ValidationEngine

def get_memory_info() -> Dict:
    """Get current memory usage from /proc/meminfo"""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        mem_info = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(':')
                value = int(parts[1])
                mem_info[key] = value
        total = mem_info.get('MemTotal', 0) / (1024**2)
        available = mem_info.get('MemAvailable', mem_info.get('MemFree', 0)) / (1024**2)
        used = total - available
        return {
            'total_gb': total / 1024,
            'used_gb': used / 1024,
            'available_gb': available / 1024,
            'percent_used': (used / total) * 100 if total > 0 else 0
        }
    except:
        return {'total_gb': 8.0, 'used_gb': 2.0, 'available_gb': 6.0, 'percent_used': 25.0}

def get_process_memory() -> float:
    """Get current process memory in MB"""
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024
    except:
        pass
    return 50.0

class StressTestRunner:
    def __init__(self):
        self.results = []
        self.start_memory = None
        self.baseline_memory = None
    
    def log_result(self, test_name: str, passed: bool, duration: float, memory_delta: float, details: str = ""):
        """Log test result"""
        result = {
            'test': test_name,
            'passed': passed,
            'duration_sec': duration,
            'memory_delta_mb': memory_delta,
            'timestamp': datetime.now().isoformat(),
            'details': details
        }
        self.results.append(result)
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name} ({duration:.2f}s, mem: {memory_delta:+.1f}MB)")
    
    def run_test(self, test_func, test_name: str) -> Tuple[bool, float, float]:
        """Run a single test and measure performance"""
        gc.collect()
        mem_before = get_process_memory()
        start_time = time.time()
        
        try:
            test_func()
            passed = True
            details = "Test completed successfully"
        except Exception as e:
            passed = False
            details = f"Error: {str(e)}"
            print(f"    Exception: {e}")
        
        duration = time.time() - start_time
        mem_after = get_process_memory()
        mem_delta = mem_after - mem_before
        
        self.log_result(test_name, passed, duration, mem_delta, details)
        gc.collect()
        
        return passed, duration, mem_delta
    
    def test_risk_monitor_initialization(self):
        """Test risk monitor can be initialized multiple times"""
        for i in range(10):
            monitor = RiskMonitor()
            assert monitor.current_risk_score == 0.0
            assert monitor.risk_level.value == "low"
    
    def test_risk_monitor_calculation(self):
        """Test risk score calculation under load"""
        monitor = RiskMonitor()
        for i in range(100):
            score = monitor.calculate_risk_score()
            assert 0.0 <= score <= 1.0
            level = monitor.get_risk_level(score)
            assert level.value in ["low", "medium", "high", "critical"]
    
    def test_risk_monitor_alerts(self):
        """Test alert generation"""
        monitor = RiskMonitor()
        for i in range(50):
            score = 0.9
            level = RiskLevel.HIGH
            alert = monitor.trigger_alert(score, level)
            assert alert['risk_score'] == score
            assert alert['risk_level'] == 'high'
    
    def test_risk_monitor_monitoring_loop(self):
        """Test monitoring loop starts and stops correctly"""
        monitor = RiskMonitor()
        monitor.start_monitoring()
        time.sleep(5)
        status = monitor.get_current_status()
        assert status['monitoring_active'] == True
        monitor.stop_monitoring()
        time.sleep(1)
        status = monitor.get_current_status()
        assert status['monitoring_active'] == False
    
    def test_agent_optimizer_initialization(self):
        """Test optimizer initialization"""
        for i in range(10):
            optimizer = AgentOptimizer()
            assert optimizer.optimization_active == False
    
    def test_agent_optimizer_performance_recording(self):
        """Test performance recording under load"""
        optimizer = AgentOptimizer()
        for i in range(100):
            optimizer.record_agent_performance(
                f'agent_{i % 5}',
                f'task_{i}',
                success=(i % 10) > 2,
                duration_seconds=10.0 + (i % 50)
            )
        status = optimizer.get_optimization_status()
        assert status['agents_tracked'] <= 5
    
    def test_agent_optimizer_workflow_recording(self):
        """Test workflow performance recording"""
        optimizer = AgentOptimizer()
        for i in range(50):
            optimizer.record_workflow_performance(
                f'workflow_{i % 3}',
                success=(i % 5) > 0,
                duration_seconds=100.0 + (i % 200),
                bottlenecks=['data_fetch', 'model_training'] if i % 10 == 0 else None
            )
    
    def test_agent_optimizer_recommendations(self):
        """Test optimization recommendation generation"""
        optimizer = AgentOptimizer()
        for i in range(20):
            optimizer.record_agent_performance(
                f'agent_{i % 3}',
                f'task_{i}',
                success=(i % 10) > 3,
                duration_seconds=30.0 + i
            )
        recs = optimizer.generate_optimization_recommendations()
        assert isinstance(recs, list)
    
    def test_validation_engine_initialization(self):
        """Test validation engine initialization"""
        for i in range(10):
            engine = ValidationEngine()
            assert engine.config is not None
    
    def test_validation_schema_checks(self):
        """Test schema validation under load"""
        engine = ValidationEngine()
        sample_data = {
            "symbol": "AAPL",
            "timestamp": "2026-03-29T10:00:00Z",
            "open": 175.0,
            "high": 176.5,
            "low": 174.5,
            "close": 176.0,
            "volume": 50000000
        }
        for i in range(100):
            result = engine.validate_schema(sample_data, 'market_data_schema')
            assert 'status' in result
    
    def test_validation_data_quality(self):
        """Test data quality checks"""
        engine = ValidationEngine()
        sample_data = [
            {"symbol": "AAPL", "open": 175.0, "high": 176.0, "low": 174.0, "close": 175.5, "volume": 50000},
            {"symbol": "GOOGL", "open": 140.0, "high": 141.0, "low": 139.0, "close": 140.5, "volume": 30000},
        ]
        for i in range(100):
            result = engine.validate_data_quality(sample_data, [
                'missing_values_check', 'price_logic_check', 'volume_non_negative'
            ])
            assert 'status' in result
    
    def test_validation_model_output(self):
        """Test model output validation"""
        engine = ValidationEngine()
        predictions = {
            'confidence_scores': {'overall_confidence': 0.85},
            'predictions': [{'predicted_return': 0.05}]
        }
        for i in range(100):
            result = engine.validate_model_output(predictions, {'min_confidence': 0.5, 'max_return': 10.0})
            assert 'status' in result
    
    def test_validation_business_rules(self):
        """Test business rules validation"""
        engine = ValidationEngine()
        data = {
            'positions': [
                {'symbol': 'AAPL', 'weight': 0.05},
                {'symbol': 'GOOGL', 'weight': 0.08}
            ],
            'risk_metrics': {'current_drawdown': 0.05}
        }
        for i in range(100):
            result = engine.validate_business_rules(data, {
                'position_limits': {'enabled': True, 'max_position_size': 0.1},
                'risk_limits': {'enabled': True, 'max_drawdown': 0.2}
            })
            assert 'status' in result
    
    def test_concurrent_component_access(self):
        """Test concurrent access to multiple components"""
        monitor = RiskMonitor()
        optimizer = AgentOptimizer()
        engine = ValidationEngine()
        
        def worker(worker_id):
            for i in range(20):
                monitor.calculate_risk_score()
                optimizer.record_agent_performance(f'agent_{worker_id}', f'task_{i}', True, 1.0)
                engine.validate_schema({"symbol": "TEST"}, 'market_data_schema')
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            for f in as_completed(futures):
                f.result()
    
    def test_memory_stress_large_data(self):
        """Test handling of large datasets"""
        optimizer = AgentOptimizer()
        
        for i in range(1000):
            optimizer.record_agent_performance(
                f'agent_{i % 10}',
                f'task_{i}',
                success=(i % 100) > 10,
                duration_seconds=10.0
            )
        
        gc.collect()
        mem = get_memory_info()
        assert mem['percent_used'] < 85, f"Memory usage too high: {mem['percent_used']}%"
    
    def test_rapid_initialization(self):
        """Test rapid creation and destruction of components"""
        for i in range(50):
            monitor = RiskMonitor()
            optimizer = AgentOptimizer()
            engine = ValidationEngine()
            
            monitor.calculate_risk_score()
            optimizer.record_agent_performance('test', 't1', True, 1.0)
            engine.validate_schema({}, 'market_data_schema')
            
            del monitor, optimizer, engine
        
        gc.collect()
    
    def test_full_validation_run(self):
        """Test complete validation workflow"""
        engine = ValidationEngine()
        
        for i in range(50):
            data = {
                "symbol": f"SYM{i}",
                "timestamp": datetime.now().isoformat(),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000000 + i * 1000
            }
            result = engine.run_validation(data, 'market_data')
            assert 'overall_status' in result
    
    def test_stress_memory_limit(self):
        """Test that memory stays under 85% threshold"""
        gc.collect()
        initial_mem = get_process_memory()
        
        optimizer = AgentOptimizer()
        for i in range(500):
            optimizer.record_agent_performance(f'agent_{i % 20}', f'task_{i}', True, 1.0)
            if i % 100 == 0:
                gc.collect()
        
        final_mem = get_process_memory()
        mem_increase = final_mem - initial_mem
        
        mem_info = get_memory_info()
        assert mem_info['percent_used'] < 85, f"System memory too high: {mem_info['percent_used']}%"
        assert mem_increase < 500, f"Memory leak detected: {mem_increase:.1f}MB increase"
    
    def run_all_tests(self) -> Dict:
        """Run all stress tests"""
        print("=" * 60)
        print("FINANCIAL ORCHESTRATOR STRESS TEST SUITE")
        print("=" * 60)
        print(f"\nBaseline Memory Check:")
        self.baseline_memory = get_memory_info()
        print(f"  Total: {self.baseline_memory['total_gb']:.2f}GB")
        print(f"  Available: {self.baseline_memory['available_gb']:.2f}GB")
        print(f"  Usage: {self.baseline_memory['percent_used']:.1f}%\n")
        
        tests = [
            ("Risk Monitor Initialization", self.test_risk_monitor_initialization),
            ("Risk Score Calculation", self.test_risk_monitor_calculation),
            ("Risk Alert Generation", self.test_risk_monitor_alerts),
            ("Risk Monitoring Loop", self.test_risk_monitor_monitoring_loop),
            ("Agent Optimizer Initialization", self.test_agent_optimizer_initialization),
            ("Agent Performance Recording", self.test_agent_optimizer_performance_recording),
            ("Workflow Performance Recording", self.test_agent_optimizer_workflow_recording),
            ("Optimization Recommendations", self.test_agent_optimizer_recommendations),
            ("Validation Engine Initialization", self.test_validation_engine_initialization),
            ("Schema Validation Checks", self.test_validation_schema_checks),
            ("Data Quality Checks", self.test_validation_data_quality),
            ("Model Output Validation", self.test_validation_model_output),
            ("Business Rules Validation", self.test_validation_business_rules),
            ("Concurrent Component Access", self.test_concurrent_component_access),
            ("Memory Stress - Large Data", self.test_memory_stress_large_data),
            ("Rapid Initialization", self.test_rapid_initialization),
            ("Full Validation Run", self.test_full_validation_run),
            ("Memory Limit Stress Test", self.test_stress_memory_limit),
        ]
        
        print("Running Component-Level Stress Tests...")
        print("-" * 60)
        
        for test_name, test_func in tests:
            self.run_test(test_func, test_name)
        
        print("\n" + "=" * 60)
        print("STRESS TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r['passed'])
        failed = sum(1 for r in self.results if not r['passed'])
        total = len(self.results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Pass Rate: {(passed/total)*100:.1f}%")
        
        total_duration = sum(r['duration_sec'] for r in self.results)
        print(f"Total Duration: {total_duration:.2f}s")
        
        final_memory = get_memory_info()
        print(f"\nFinal Memory Usage: {final_memory['percent_used']:.1f}%")
        print(f"Available Memory: {final_memory['available_gb']:.2f}GB")
        
        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r['passed']:
                    print(f"  - {r['test']}: {r['details']}")
        
        return {
            'passed': passed,
            'failed': failed,
            'total': total,
            'pass_rate': (passed/total)*100,
            'total_duration': total_duration,
            'final_memory_percent': final_memory['percent_used']
        }

if __name__ == "__main__":
    runner = StressTestRunner()
    results = runner.run_all_tests()
    
    output_file = '/home/ubuntu/financial_orchestrator/logs/stress_test_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': runner.results,
            'summary': results
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    sys.exit(0 if results['failed'] == 0 else 1)
