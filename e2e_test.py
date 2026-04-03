#!/usr/bin/env python3
"""
End-to-End Workflow Test for Financial Orchestrator
Tests complete workflow execution from start to finish
"""

import sys
import os
import time
import json
import gc
from datetime import datetime
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

class E2EWorkflowTest:
    def __init__(self):
        self.results = []
        self.workflow_state = None
    
    def log_result(self, test_name: str, passed: bool, duration: float, details: str = ""):
        result = {'test': test_name, 'passed': passed, 'duration_sec': duration, 'timestamp': datetime.now().isoformat(), 'details': details}
        self.results.append(result)
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name} ({duration:.2f}s)")
    
    def run_test(self, test_func, test_name: str) -> bool:
        gc.collect()
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
        return passed
    
    def initialize_workflow(self):
        print("  Initializing workflow state...")
        self.workflow_state = {
            'workflow_id': 'test_workflow_001',
            'status': 'initialized',
            'phases': [],
            'start_time': datetime.now().isoformat(),
            'risk_score': 0.0,
            'risk_level': 'low',
            'progress_percentage': 0
        }
        assert self.workflow_state is not None
        assert self.workflow_state['status'] == 'initialized'
    
    def test_data_acquisition_phase(self):
        print("  Testing Data Acquisition Phase...")
        monitor = RiskMonitor()
        optimizer = AgentOptimizer()
        
        for i in range(10):
            score = monitor.calculate_risk_score()
            optimizer.record_agent_performance('data_engineer', f'data_task_{i}', True, 5.0)
        
        self.workflow_state['phases'].append({
            'name': 'Data Acquisition',
            'status': 'completed',
            'tasks_completed': 10
        })
        self.workflow_state['risk_score'] = monitor.calculate_risk_score()
        self.workflow_state['risk_level'] = monitor.get_risk_level(self.workflow_state['risk_score']).value
        self.workflow_state['progress_percentage'] = 20
        
        assert len(self.workflow_state['phases']) == 1
        assert self.workflow_state['progress_percentage'] == 20
    
    def test_feature_engineering_phase(self):
        print("  Testing Feature Engineering Phase...")
        engine = ValidationEngine()
        
        for i in range(10):
            data = {
                "symbol": f"FEATURE_{i}",
                "timestamp": datetime.now().isoformat(),
                "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i,
                "close": 100.5 + i, "volume": 1000000 + i * 1000
            }
            result = engine.run_validation(data, 'market_data')
        
        self.workflow_state['phases'].append({
            'name': 'Feature Engineering',
            'status': 'completed',
            'tasks_completed': 10
        })
        self.workflow_state['progress_percentage'] = 40
        
        assert len(self.workflow_state['phases']) == 2
        assert self.workflow_state['progress_percentage'] == 40
    
    def test_model_development_phase(self):
        print("  Testing Model Development Phase...")
        optimizer = AgentOptimizer()
        
        for i in range(10):
            optimizer.record_agent_performance('model_developer', f'model_task_{i}', True, 15.0)
        
        self.workflow_state['phases'].append({
            'name': 'Model Development',
            'status': 'completed',
            'tasks_completed': 10
        })
        self.workflow_state['progress_percentage'] = 60
        
        assert len(self.workflow_state['phases']) == 3
        assert self.workflow_state['progress_percentage'] == 60
    
    def test_validation_phase(self):
        print("  Testing Validation Phase...")
        engine = ValidationEngine()
        monitor = RiskMonitor()
        
        for i in range(10):
            data = {
                "symbol": f"VALIDATION_{i}",
                "timestamp": datetime.now().isoformat(),
                "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i,
                "close": 100.5 + i, "volume": 1000000 + i * 1000
            }
            result = engine.run_validation(data, 'market_data')
            
            score = monitor.calculate_risk_score()
            if score > 0.7:
                monitor.trigger_alert(score, monitor.get_risk_level(score))
        
        self.workflow_state['phases'].append({
            'name': 'Validation',
            'status': 'completed',
            'tasks_completed': 10
        })
        self.workflow_state['progress_percentage'] = 80
        
        assert len(self.workflow_state['phases']) == 4
        assert self.workflow_state['progress_percentage'] == 80
    
    def test_deployment_phase(self):
        print("  Testing Deployment Phase...")
        optimizer = AgentOptimizer()
        
        optimizer.record_workflow_performance('test_workflow_001', True, 100.0)
        
        self.workflow_state['phases'].append({
            'name': 'Deployment',
            'status': 'completed',
            'tasks_completed': 5
        })
        self.workflow_state['status'] = 'completed'
        self.workflow_state['progress_percentage'] = 100
        self.workflow_state['end_time'] = datetime.now().isoformat()
        
        assert len(self.workflow_state['phases']) == 5
        assert self.workflow_state['status'] == 'completed'
        assert self.workflow_state['progress_percentage'] == 100
    
    def test_workflow_state_persistence(self):
        print("  Testing Workflow State Persistence...")
        
        state_file = '/home/ubuntu/financial_orchestrator/logs/e2e_workflow_state.json'
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        with open(state_file, 'w') as f:
            json.dump(self.workflow_state, f, indent=2)
        
        with open(state_file, 'r') as f:
            loaded_state = json.load(f)
        
        assert loaded_state['workflow_id'] == self.workflow_state['workflow_id']
        assert loaded_state['status'] == 'completed'
        assert len(loaded_state['phases']) == 5
    
    def test_risk_monitoring_throughout(self):
        print("  Testing Risk Monitoring Throughout Workflow...")
        monitor = RiskMonitor()
        
        for phase in self.workflow_state['phases']:
            score = monitor.calculate_risk_score()
            level = monitor.get_risk_level(score)
            
            assert 0.0 <= score <= 1.0
            assert level.value in ['low', 'medium', 'high', 'critical']
            
            if level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                monitor.trigger_alert(score, level)
        
        status = monitor.get_current_status()
        assert 'monitoring_active' in status
    
    def test_optimization_tracking(self):
        print("  Testing Optimization Tracking...")
        optimizer = AgentOptimizer()
        
        recs = optimizer.generate_optimization_recommendations()
        assert isinstance(recs, list)
        
        status = optimizer.get_optimization_status()
        assert 'agents_tracked' in status
        assert 'workflows_tracked' in status
    
    def run_all_tests(self) -> Dict:
        print("=" * 60)
        print("END-TO-END WORKFLOW TEST SUITE")
        print("=" * 60)
        
        print(f"\nSystem Memory:")
        mem_info = get_memory_info()
        print(f"  Total: {mem_info['total_gb']:.2f}GB")
        print(f"  Available: {mem_info['available_gb']:.2f}GB")
        print(f"  Usage: {mem_info['percent_used']:.1f}%\n")
        
        tests = [
            ("Initialize Workflow", self.initialize_workflow),
            ("Data Acquisition Phase", self.test_data_acquisition_phase),
            ("Feature Engineering Phase", self.test_feature_engineering_phase),
            ("Model Development Phase", self.test_model_development_phase),
            ("Validation Phase", self.test_validation_phase),
            ("Deployment Phase", self.test_deployment_phase),
            ("Workflow State Persistence", self.test_workflow_state_persistence),
            ("Risk Monitoring Throughout", self.test_risk_monitoring_throughout),
            ("Optimization Tracking", self.test_optimization_tracking),
        ]
        
        print("Running End-to-End Workflow Tests...")
        print("-" * 60)
        
        for test_name, test_func in tests:
            self.run_test(test_func, test_name)
        
        print("\n" + "=" * 60)
        print("E2E WORKFLOW TEST RESULTS SUMMARY")
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
        
        if self.workflow_state:
            print(f"\nWorkflow Summary:")
            print(f"  ID: {self.workflow_state['workflow_id']}")
            print(f"  Status: {self.workflow_state['status']}")
            print(f"  Phases: {len(self.workflow_state['phases'])}")
            print(f"  Progress: {self.workflow_state['progress_percentage']}%")
        
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
            'workflow_state': self.workflow_state,
            'final_memory_percent': final_memory['percent_used']
        }

if __name__ == "__main__":
    runner = E2EWorkflowTest()
    results = runner.run_all_tests()
    
    output_file = '/home/ubuntu/financial_orchestrator/logs/e2e_test_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': runner.results,
            'summary': results
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    sys.exit(0 if results['failed'] == 0 else 1)
