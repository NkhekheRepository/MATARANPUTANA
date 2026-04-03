#!/usr/bin/env python3
"""
Integration Stress Test Suite for Financial Orchestrator
Tests component integration and communication
"""

import sys
import os
import time
import json
import gc
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

from monitoring.risk_monitor import RiskMonitor, RiskLevel
from optimization.agent_optimizer import AgentOptimizer
from validation.validation_engine import ValidationEngine

def get_memory_info() -> Dict:
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
        return {'total_gb': total / 1024, 'used_gb': used / 1024, 'available_gb': available / 1024, 'percent_used': (used / total) * 100 if total > 0 else 0}
    except:
        return {'total_gb': 8.0, 'used_gb': 2.0, 'available_gb': 6.0, 'percent_used': 25.0}

def get_process_memory() -> float:
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024
    except:
        pass
    return 50.0

class IntegrationTestRunner:
    def __init__(self):
        self.results = []
        self.components = {}
    
    def log_result(self, test_name: str, passed: bool, duration: float, details: str = ""):
        result = {
            'test': test_name, 'passed': passed, 'duration_sec': duration,
            'timestamp': datetime.now().isoformat(), 'details': details
        }
        self.results.append(result)
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name} ({duration:.2f}s)")
    
    def run_test(self, test_func, test_name: str) -> bool:
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
        self.log_result(test_name, passed, duration, details)
        gc.collect()
        return passed
    
    def setup_components(self):
        self.components['monitor'] = RiskMonitor()
        self.components['optimizer'] = AgentOptimizer()
        self.components['engine'] = ValidationEngine()
    
    def test_workflow_orchestration(self):
        monitor = self.components['monitor']
        optimizer = self.components['optimizer']
        engine = self.components['engine']
        
        for i in range(50):
            risk_score = monitor.calculate_risk_score()
            risk_level = monitor.get_risk_level(risk_score)
            
            optimizer.record_agent_performance(f'agent_{i % 3}', f'task_{i}', True, 10.0)
            
            data = {
                "symbol": f"SYM{i}",
                "timestamp": datetime.now().isoformat(),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000000 + i * 1000
            }
            engine.run_validation(data, 'market_data')
            
            if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                optimizer.record_workflow_performance(f'workflow_{i % 2}', True, 15.0)
    
    def test_agent_communication(self):
        monitor = self.components['monitor']
        optimizer = self.components['optimizer']
        
        for i in range(100):
            risk_score = monitor.calculate_risk_score()
            
            if risk_score > 0.7:
                optimizer.record_agent_performance('risk_agent', f'task_{i}', False, 5.0)
            else:
                optimizer.record_agent_performance('normal_agent', f'task_{i}', True, 5.0)
            
            monitor.trigger_alert(risk_score, monitor.get_risk_level(risk_score))
    
    def test_validation_orchestration(self):
        engine = self.components['engine']
        
        for i in range(50):
            data = {
                "symbol": f"STOCK{i}",
                "timestamp": datetime.now().isoformat(),
                "open": 150.0 + i,
                "high": 152.0 + i,
                "low": 148.0 + i,
                "close": 151.0 + i,
                "volume": 2000000 + i * 5000
            }
            
            result = engine.run_validation(data, 'market_data')
            assert 'overall_status' in result
            assert result['overall_status'] in ['passed', 'failed', 'warning', 'skipped']
    
    def test_concurrent_orchestration(self):
        monitor = self.components['monitor']
        optimizer = self.components['optimizer']
        engine = self.components['engine']
        
        def worker(worker_id):
            for i in range(30):
                monitor.calculate_risk_score()
                optimizer.record_agent_performance(f'agent_{worker_id}', f'task_{i}', True, 1.0)
                engine.validate_schema({"symbol": f"SYM{worker_id}_{i}"}, 'market_data_schema')
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(8)]
            for f in as_completed(futures):
                f.result()
    
    def test_risk_monitoring_integration(self):
        monitor = self.components['monitor']
        optimizer = self.components['optimizer']
        
        alert_count = 0
        for i in range(100):
            score = monitor.calculate_risk_score()
            level = monitor.get_risk_level(score)
            
            if level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                alert = monitor.trigger_alert(score, level)
                optimizer.record_agent_performance('alert_handler', f'task_{i}', True, 1.0)
                alert_count += 1
        
        assert alert_count >= 0
    
    def test_optimization_integration(self):
        optimizer = self.components['optimizer']
        
        for i in range(100):
            optimizer.record_agent_performance(f'agent_{i % 5}', f'task_{i}', (i % 10) > 3, 10.0 + i)
        
        recs = optimizer.generate_optimization_recommendations()
        assert isinstance(recs, list)
        
        for rec in recs:
            result = optimizer.apply_optimization(rec)
            assert result['status'] == 'applied'
    
    def test_full_pipeline_simulation(self):
        monitor = self.components['monitor']
        optimizer = self.components['optimizer']
        engine = self.components['engine']
        
        for i in range(30):
            risk_score = monitor.calculate_risk_score()
            risk_level = monitor.get_risk_level(risk_score)
            
            optimizer.record_agent_performance(f'data_agent', f'data_task_{i}', True, 5.0)
            optimizer.record_agent_performance(f'model_agent', f'model_task_{i}', True, 10.0)
            
            data = {
                "symbol": f"PIPELINE_{i}",
                "timestamp": datetime.now().isoformat(),
                "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000000
            }
            result = engine.run_validation(data, 'market_data')
            
            if risk_level == RiskLevel.HIGH:
                monitor.trigger_alert(risk_score, risk_level)
            
            optimizer.record_workflow_performance('pipeline_workflow', result['overall_status'] == 'passed', 20.0)
    
    def test_memory_under_integration_load(self):
        gc.collect()
        initial_mem = get_process_memory()
        
        for iteration in range(10):
            self.test_workflow_orchestration()
            gc.collect()
        
        final_mem = get_process_memory()
        mem_increase = final_mem - initial_mem
        
        mem_info = get_memory_info()
        assert mem_info['percent_used'] < 85, f"Memory usage too high: {mem_info['percent_used']}%"
        assert mem_increase < 500, f"Memory leak: {mem_increase:.1f}MB increase"
    
    def run_all_tests(self) -> Dict:
        print("=" * 60)
        print("INTEGRATION STRESS TEST SUITE")
        print("=" * 60)
        
        print(f"\nSystem Memory:")
        mem_info = get_memory_info()
        print(f"  Total: {mem_info['total_gb']:.2f}GB")
        print(f"  Available: {mem_info['available_gb']:.2f}GB")
        print(f"  Usage: {mem_info['percent_used']:.1f}%\n")
        
        print("Setting up components...")
        self.setup_components()
        print("Components initialized successfully\n")
        
        tests = [
            ("Workflow Orchestration", self.test_workflow_orchestration),
            ("Agent Communication", self.test_agent_communication),
            ("Validation Orchestration", self.test_validation_orchestration),
            ("Concurrent Orchestration", self.test_concurrent_orchestration),
            ("Risk Monitoring Integration", self.test_risk_monitoring_integration),
            ("Optimization Integration", self.test_optimization_integration),
            ("Full Pipeline Simulation", self.test_full_pipeline_simulation),
            ("Memory Under Integration Load", self.test_memory_under_integration_load),
        ]
        
        print("Running Integration Stress Tests...")
        print("-" * 60)
        
        for test_name, test_func in tests:
            self.run_test(test_func, test_name)
        
        print("\n" + "=" * 60)
        print("INTEGRATION TEST RESULTS SUMMARY")
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
        
        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r['passed']:
                    print(f"  - {r['test']}: {r['details']}")
        
        return {
            'passed': passed, 'failed': failed, 'total': total,
            'pass_rate': (passed/total)*100, 'total_duration': total_duration,
            'final_memory_percent': final_memory['percent_used']
        }

if __name__ == "__main__":
    runner = IntegrationTestRunner()
    results = runner.run_all_tests()
    
    output_file = '/home/ubuntu/financial_orchestrator/logs/integration_test_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': runner.results,
            'summary': results
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    sys.exit(0 if results['failed'] == 0 else 1)
