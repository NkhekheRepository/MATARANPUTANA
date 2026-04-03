#!/usr/bin/env python3
"""
Validation Engine for Financial Workflows
Validates outputs against schemas and business rules
"""

import json
import yaml
import jsonschema
from jsonschema import ValidationError
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional
import os
import sys

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')
try:
    from telegram_notify import (
        send_startup_notification,
        send_shutdown_notification,
        send_validation_result,
        send_alert
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[WARN] Telegram notifications not available")

class ValidationLevel(Enum):
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    PARANOID = "paranoid"

class ValidationStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"

class ValidationEngine:
    def __init__(self, config_path='/home/ubuntu/financial_orchestrator/validation/rules/validation_rules.yaml'):
        self.config_path = config_path
        self.config = self.load_config()
        self.validation_history = []
        
    def load_config(self):
        """Load validation configuration"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"Failed to load validation config: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """Return default configuration"""
        return {
            'validation_enabled': True,
            'validation_level': 'standard',
            'schema_validation': {},
            'data_quality': {},
            'model_validation': {},
            'business_logic': {}
        }
    
    def validate_schema(self, data: Dict, schema_name: str) -> Dict:
        """Validate data against a JSON schema"""
        schema_path = f"/home/ubuntu/financial_orchestrator/validation/schemas/{schema_name}"
        
        try:
            with open(f"{schema_path}.json", 'r') as f:
                schema = json.load(f)
            
            jsonschema.validate(data, schema)
            
            return {
                'status': ValidationStatus.PASSED.value,
                'schema': schema_name,
                'timestamp': datetime.now().isoformat(),
                'message': f"Data validated successfully against {schema_name}"
            }
        except ValidationError as e:
            return {
                'status': ValidationStatus.FAILED.value,
                'schema': schema_name,
                'timestamp': datetime.now().isoformat(),
                'message': f"Schema validation failed: {str(e)}",
                'error': e.message
            }
        except FileNotFoundError:
            return {
                'status': ValidationStatus.SKIPPED.value,
                'schema': schema_name,
                'timestamp': datetime.now().isoformat(),
                'message': f"Schema file not found: {schema_name}"
            }
    
    def validate_data_quality(self, data: List[Dict], checks: List[str]) -> Dict:
        """Run data quality checks on market data"""
        results = {
            'status': ValidationStatus.PASSED.value,
            'checks_passed': 0,
            'checks_failed': 0,
            'warnings': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Handle both single objects and lists
        if isinstance(data, dict):
            data = [data]
        
        for check in checks:
            if check == 'missing_values_check':
                missing = sum(1 for row in data if any(v is None for v in row.values()))
                if missing > 0:
                    results['checks_failed'] += 1
                    results['warnings'].append(f"Found {missing} rows with missing values")
                else:
                    results['checks_passed'] += 1
                    
            elif check == 'price_logic_check':
                logic_errors = 0
                for row in data:
                    if 'high' in row and 'low' in row:
                        if row.get('high', 0) < row.get('low', 0):
                            logic_errors += 1
                    if 'close' in row and 'open' in row:
                        if not (min(row.get('open', 0), row.get('close', 0)) <= row.get('close', 0) <= max(row.get('open', 0), row.get('close', 0))):
                            pass  # Close can be anywhere in range
                if logic_errors > 0:
                    results['checks_failed'] += 1
                    results['warnings'].append(f"Found {logic_errors} price logic violations")
                else:
                    results['checks_passed'] += 1
                    
            elif check == 'volume_non_negative':
                negative_vol = sum(1 for row in data if row.get('volume', 0) < 0)
                if negative_vol > 0:
                    results['checks_failed'] += 1
                    results['warnings'].append(f"Found {negative_vol} rows with negative volume")
                else:
                    results['checks_passed'] += 1
        
        if results['checks_failed'] > 0:
            results['status'] = ValidationStatus.FAILED.value
        elif results['warnings']:
            results['status'] = ValidationStatus.WARNING.value
            
        return results
    
    def validate_model_output(self, predictions: Dict, thresholds: Dict) -> Dict:
        """Validate quantitative model outputs"""
        results = {
            'status': ValidationStatus.PASSED.value,
            'checks': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Check confidence scores
        if 'confidence_scores' in predictions:
            conf = predictions['confidence_scores']
            
            if 'overall_confidence' in conf:
                if conf['overall_confidence'] < thresholds.get('min_confidence', 0.5):
                    results['checks'].append({
                        'check': 'confidence_threshold',
                        'status': 'warning',
                        'message': f"Overall confidence {conf['overall_confidence']:.2%} below threshold"
                    })
                else:
                    results['checks'].append({
                        'check': 'confidence_threshold',
                        'status': 'passed',
                        'message': "Confidence score within acceptable range"
                    })
        
        # Check prediction ranges
        if 'predictions' in predictions:
            for pred in predictions['predictions']:
                if 'predicted_return' in pred:
                    ret = pred['predicted_return']
                    if abs(ret) > thresholds.get('max_return', 10.0):
                        results['checks'].append({
                            'check': 'return_range',
                            'status': 'warning',
                            'message': f"Predicted return {ret:.2%} exceeds reasonable range"
                        })
        
        if any(c['status'] == 'warning' for c in results['checks']):
            results['status'] = ValidationStatus.WARNING.value
        if any(c['status'] == 'failed' for c in results['checks']):
            results['status'] = ValidationStatus.FAILED.value
            
        return results
    
    def validate_business_rules(self, data: Dict, rules: Dict) -> Dict:
        """Validate against business rules"""
        results = {
            'status': ValidationStatus.PASSED.value,
            'violations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Position limits
        if 'positions' in data and rules.get('position_limits', {}).get('enabled'):
            max_position = rules['position_limits'].get('max_position_size', 0.1)
            for position in data['positions']:
                if position.get('weight', 0) > max_position:
                    results['violations'].append({
                        'rule': 'position_limit',
                        'message': f"Position {position.get('symbol')} weight {position.get('weight'):.2%} exceeds limit {max_position:.2%}"
                    })
        
        # Risk limits
        if 'risk_metrics' in data and rules.get('risk_limits', {}).get('enabled'):
            max_dd = rules['risk_limits'].get('max_drawdown', 0.2)
            if data['risk_metrics'].get('current_drawdown', 0) > max_dd:
                results['violations'].append({
                    'rule': 'drawdown_limit',
                    'message': f"Current drawdown {data['risk_metrics']['current_drawdown']:.2%} exceeds limit {max_dd:.2%}"
                })
        
        if results['violations']:
            results['status'] = ValidationStatus.FAILED.value
            
        return results
    
    def run_validation(self, data: Any, validation_type: str, metadata: Optional[Dict] = None) -> Dict:
        """Run complete validation based on type"""
        result = {
            'validation_type': validation_type,
            'timestamp': datetime.now().isoformat(),
            'overall_status': ValidationStatus.PASSED.value,
            'results': []
        }
        
        if not self.config.get('validation_enabled', True):
            return {
                **result,
                'overall_status': ValidationStatus.SKIPPED.value,
                'message': 'Validation disabled in configuration'
            }
        
        # Schema validation
        if validation_type == 'market_data':
            schema_result = self.validate_schema(data, 'market_data_schema')
            result['results'].append(schema_result)
            
            # Data quality checks
            quality_result = self.validate_data_quality(data, ['missing_values_check', 'price_logic_check', 'volume_non_negative'])
            result['results'].append(quality_result)
            
        elif validation_type == 'model_output':
            schema_result = self.validate_schema(data, 'model_output_schema')
            result['results'].append(schema_result)
            
            thresholds = {'min_confidence': 0.5, 'max_return': 10.0}
            model_result = self.validate_model_output(data, thresholds)
            result['results'].append(model_result)
            
        elif validation_type == 'business_rules':
            business_result = self.validate_business_rules(data, self.config.get('business_logic', {}))
            result['results'].append(business_result)
        
        # Determine overall status
        statuses = [r.get('status') for r in result['results']]
        if ValidationStatus.FAILED.value in statuses:
            result['overall_status'] = ValidationStatus.FAILED.value
        elif ValidationStatus.WARNING.value in statuses:
            result['overall_status'] = ValidationStatus.WARNING.value
            
        # Store in history
        self.validation_history.append(result)
        
        return result
    
    def generate_report(self, validation_result: Dict) -> str:
        """Generate human-readable validation report"""
        report_lines = [
            "=" * 60,
            "VALIDATION REPORT",
            "=" * 60,
            f"Type: {validation_result['validation_type']}",
            f"Time: {validation_result['timestamp']}",
            f"Status: {validation_result['overall_status'].upper()}",
            "-" * 60,
            "Results:"
        ]
        
        for r in validation_result['results']:
            status_symbol = "✓" if r['status'] == 'passed' else "✗" if r['status'] == 'failed' else "⚠"
            report_lines.append(f"  {status_symbol} [{r['status']}] {r.get('schema', r.get('checks', [{}])[0].get('check', 'validation') if r.get('checks') else 'general')}")
            
            if 'message' in r:
                report_lines.append(f"      {r['message']}")
            if 'warnings' in r:
                for warning in r['warnings']:
                    report_lines.append(f"      Warning: {warning}")
            if 'violations' in r:
                for violation in r['violations']:
                    report_lines.append(f"      Violation: {violation['message']}")
        
        report_lines.append("=" * 60)
        return "\n".join(report_lines)

if __name__ == "__main__":
    print("Starting Validation Engine...")
    
    if TELEGRAM_AVAILABLE:
        send_startup_notification("Validation Engine")
    
    engine = ValidationEngine()
    
    try:
        # Run validation server mode
        print("Validation Engine running in server mode. Press Ctrl+C to stop.")
        
        while True:
            # In server mode, the engine would process validation requests
            # For demo, we'll just run sample validations periodically
            import time
            time.sleep(60)
            
    except KeyboardInterrupt:
        print("\nShutting down Validation Engine...")
    finally:
        if TELEGRAM_AVAILABLE:
            send_shutdown_notification("Validation Engine")