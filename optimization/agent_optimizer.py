#!/usr/bin/env python3
"""
Agent Optimization System
Analyzes agent performance and workflow efficiency to make continuous improvements
"""

import yaml
import json
import time
import threading
from datetime import datetime, timedelta
import os
import statistics
from collections import defaultdict, deque
import sys

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')
try:
    from telegram_notify import (
        send_startup_notification,
        send_shutdown_notification,
        send_alert
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[WARN] Telegram notifications not available")

class AgentOptimizer:
    def __init__(self, memory_base_path='/home/ubuntu/financial_orchestrator/memory'):
        self.memory_base_path = memory_base_path
        self.optimization_active = False
        self.optimize_thread = None
        
        # Performance tracking
        self.agent_performance = defaultdict(lambda: {
            'tasks_completed': 0,
            'success_rate': 0.0,
            'average_duration': 0.0,
            'last_active': None,
            'performance_history': deque(maxlen=100)
        })
        
        self.workflow_metrics = defaultdict(lambda: {
            'executions': 0,
            'success_rate': 0.0,
            'average_duration': 0.0,
            'bottlenecks': [],
            'performance_history': deque(maxlen=50)
        })
        
        # Load existing data
        self.load_performance_data()
        
    def load_performance_data(self):
        """Load historical performance data from memory"""
        try:
            # Load agent performance data
            agent_dir = os.path.join(self.memory_base_path, 'execution_history')
            if os.path.exists(agent_dir):
                for filename in os.listdir(agent_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(agent_dir, filename)
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                            self._process_historical_data(data)
        except Exception as e:
            print(f"Warning: Could not load performance data: {e}")
    
    def _process_historical_data(self, data):
        """Process historical execution data"""
        # This would process actual execution records
        # For now, we'll simulate some data
        pass
    
    def record_agent_performance(self, agent_id, task_id, success, duration_seconds):
        """Record performance metrics for an agent"""
        if agent_id not in self.agent_performance:
            self.agent_performance[agent_id] = {
                'tasks_completed': 0,
                'success_rate': 0.0,
                'average_duration': 0.0,
                'last_active': None,
                'performance_history': deque(maxlen=100)
            }
        
        agent_data = self.agent_performance[agent_id]
        agent_data['tasks_completed'] += 1
        agent_data['last_active'] = datetime.now().isoformat()
        
        # Update success rate (running average)
        old_success_rate = agent_data['success_rate']
        new_success = 1.0 if success else 0.0
        agent_data['success_rate'] = (
            (old_success_rate * (agent_data['tasks_completed'] - 1) + new_success) /
            agent_data['tasks_completed']
        )
        
        # Update average duration
        old_avg_duration = agent_data['average_duration']
        agent_data['average_duration'] = (
            (old_avg_duration * (agent_data['tasks_completed'] - 1) + duration_seconds) /
            agent_data['tasks_completed']
        )
        
        # Add to history
        agent_data['performance_history'].append({
            'timestamp': datetime.now().isoformat(),
            'task_id': task_id,
            'success': success,
            'duration': duration_seconds
        })
    
    def record_workflow_performance(self, workflow_id, success, duration_seconds, bottlenecks=None):
        """Record performance metrics for a workflow"""
        if workflow_id not in self.workflow_metrics:
            self.workflow_metrics[workflow_id] = {
                'executions': 0,
                'success_rate': 0.0,
                'average_duration': 0.0,
                'bottlenecks': [],
                'performance_history': deque(maxlen=50)
            }
        
        workflow_data = self.workflow_metrics[workflow_id]
        workflow_data['executions'] += 1
        
        # Update success rate
        old_success_rate = workflow_data['success_rate']
        new_success = 1.0 if success else 0.0
        workflow_data['success_rate'] = (
            (old_success_rate * (workflow_data['executions'] - 1) + new_success) /
            workflow_data['executions']
        )
        
        # Update average duration
        old_avg_duration = workflow_data['average_duration']
        workflow_data['average_duration'] = (
            (old_avg_duration * (workflow_data['executions'] - 1) + duration_seconds) /
            workflow_data['executions']
        )
        
        # Update bottlenecks
        if bottlenecks:
            workflow_data['bottlenecks'] = list(set(
                workflow_data['bottlenecks'] + bottlenecks
            ))[-10:]  # Keep last 10 unique bottlenecks
        
        # Add to history
        workflow_data['performance_history'].append({
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'duration': duration_seconds,
            'bottlenecks': bottlenecks or []
        })
    
    def analyze_agent_efficiency(self):
        """Analyze agent performance and identify optimization opportunities"""
        optimizations = []
        
        for agent_id, metrics in self.agent_performance.items():
            # Skip agents with insufficient data
            if metrics['tasks_completed'] < 5:
                continue
                
            # Identify underperforming agents
            if metrics['success_rate'] < 0.8:  # Less than 80% success rate
                optimizations.append({
                    'type': 'agent_retraining',
                    'agent_id': agent_id,
                    'reason': f'Low success rate: {metrics["success_rate"]:.2%}',
                    'suggestion': 'Consider additional training or reduced task complexity'
                })
            
            # Identify overqualified agents (could handle more complex tasks)
            if metrics['success_rate'] > 0.95 and metrics['average_duration'] < 300:  # Very fast and reliable
                optimizations.append({
                    'type': 'agent_promotion',
                    'agent_id': agent_id,
                    'reason': f'High performance: {metrics["success_rate"]:.2%} success, {metrics["average_duration"]:.0f}s avg duration',
                    'suggestion': 'Consider assigning more complex tasks or mentoring other agents'
                })
            
            # Identify slow agents
            if metrics['average_duration'] > 1800:  # Slower than 30 minutes average
                optimizations.append({
                    'type': 'process_improvement',
                    'agent_id': agent_id,
                    'reason': f'Slow performance: {metrics["average_duration"]:.0f}s average duration',
                    'suggestion': 'Review task assignments for optimization opportunities'
                })
        
        return optimizations
    
    def analyze_workflow_efficiency(self):
        """Analyze workflow performance and identify optimization opportunities"""
        optimizations = []
        
        for workflow_id, metrics in self.workflow_metrics.items():
            # Skip workflows with insufficient data
            if metrics['executions'] < 3:
                continue
                
            # Identify failing workflows
            if metrics['success_rate'] < 0.7:  # Less than 70% success rate
                optimizations.append({
                    'type': 'workflow_redesign',
                    'workflow_id': workflow_id,
                    'reason': f'Low success rate: {metrics["success_rate"]:.2%}',
                    'suggestion': 'Review workflow design and task dependencies'
                })
            
            # Identify slow workflows
            if metrics['average_duration'] > 7200:  # Slower than 2 hours average
                optimizations.append({
                    'type': 'workflow_streamlining',
                    'workflow_id': workflow_id,
                    'reason': f'Long duration: {metrics["average_duration"]:.0f}s average',
                    'suggestion': 'Identify and eliminate bottlenecks'
                })
            
            # Identify workflows with recurring bottlenecks
            if len(metrics['bottlenecks']) > 3:
                optimizations.append({
                    'type': 'bottleneck_resolution',
                    'workflow_id': workflow_id,
                    'reason': f'Recurring bottlenecks: {metrics["bottlenecks"]}',
                    'suggestion': 'Address persistent workflow bottlenecks'
                })
        
        return optimizations
    
    def generate_optimization_recommendations(self):
        """Generate optimization recommendations based on analysis"""
        agent_optimizations = self.analyze_agent_efficiency()
        workflow_optimizations = self.analyze_workflow_efficiency()
        
        all_optimizations = agent_optimizations + workflow_optimizations
        
        # Prioritize optimizations
        prioritized = sorted(all_optimizations, key=lambda x: self._get_priority_score(x), reverse=True)
        
        return prioritized[:10]  # Return top 10 recommendations
    
    def _get_priority_score(self, optimization):
        """Calculate priority score for an optimization"""
        score = 0
        
        # Higher priority for critical issues
        if optimization['type'] in ['agent_retraining', 'workflow_redesign']:
            score += 3
        elif optimization['type'] in ['process_improvement', 'workflow_streamlining']:
            score += 2
        else:
            score += 1
            
        # Higher priority for agents/workflows with more data
        if 'agent_id' in optimization:
            agent_data = self.agent_performance.get(optimization['agent_id'], {})
            score += min(agent_data.get('tasks_completed', 0) // 10, 5)
        elif 'workflow_id' in optimization:
            workflow_data = self.workflow_metrics.get(optimization['workflow_id'], {})
            score += min(workflow_data.get('executions', 0) // 5, 5)
        
        return score
    
    def apply_optimization(self, optimization):
        """Apply an optimization recommendation"""
        # In a real implementation, this would make actual changes
        # For now, we'll log the optimization attempt
        
        optimization_record = {
            'timestamp': datetime.now().isoformat(),
            'optimization': optimization,
            'status': 'applied',
            'notes': 'Optimization recommendation processed'
        }
        
        # Save optimization record
        self._save_optimization_record(optimization_record)
        
        return optimization_record
    
    def _save_optimization_record(self, record):
        """Save optimization record to memory"""
        try:
            opt_dir = os.path.join(self.memory_base_path, 'optimization_knowledge')
            os.makedirs(opt_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"optimization_{timestamp}.json"
            filepath = os.path.join(opt_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(record, f, indent=2)
                
        except Exception as e:
            print(f"Failed to save optimization record: {e}")
    
    def optimization_loop(self):
        """Main optimization loop"""
        print("Starting agent optimization loop")
        
        while self.optimization_active:
            try:
                # Generate recommendations
                recommendations = self.generate_optimization_recommendations()
                
                if recommendations:
                    print(f"Generated {len(recommendations)} optimization recommendations")
                    
                    # Apply top recommendations (in real system, might require approval)
                    for opt in recommendations[:3]:  # Apply top 3
                        result = self.apply_optimization(opt)
                        print(f"Applied optimization: {opt['type']} for {opt.get('agent_id', opt.get('workflow_id', 'unknown'))}")
                
                # Sleep for optimization interval (e.g., every hour)
                time.sleep(3600)
                
            except Exception as e:
                print(f"Error in optimization loop: {e}")
                time.sleep(300)  # Sleep 5 minutes on error
    
    def start_optimization(self):
        """Start the optimization system"""
        if not self.optimization_active:
            self.optimization_active = True
            self.optimize_thread = threading.Thread(target=self.optimization_loop, daemon=True)
            self.optimize_thread.start()
            print("Agent optimization started")
            return True
        else:
            print("Optimization already active")
            return False
    
    def stop_optimization(self):
        """Stop the optimization system"""
        if self.optimization_active:
            self.optimization_active = False
            if self.optimize_thread:
                self.optimize_thread.join(timeout=5)
            print("Optimization stopped")
            return True
        else:
            print("Optimization not active")
            return False
    
    def get_optimization_status(self):
        """Get current optimization status"""
        return {
            'optimization_active': self.optimization_active,
            'agents_tracked': len(self.agent_performance),
            'workflows_tracked': len(self.workflow_metrics),
            'last_analysis': datetime.now().isoformat() if self.optimization_active else None
        }

# Example usage
if __name__ == "__main__":
    print("Starting Agent Optimizer...")
    
    if TELEGRAM_AVAILABLE:
        send_startup_notification("Agent Optimizer")
    
    optimizer = AgentOptimizer()
    
    # Start optimization
    optimizer.start_optimization()
    
    try:
        # Run indefinitely
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\nShutting down Agent Optimizer...")
    finally:
        optimizer.stop_optimization()
        if TELEGRAM_AVAILABLE:
            send_shutdown_notification("Agent Optimizer")