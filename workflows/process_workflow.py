#!/usr/bin/env python3
"""
Workflow Processing Simulator
Simulates the execution of financial workflows by updating status and progress
"""

import json
import time
import threading
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')
try:
    from telegram_notify import (
        send_startup_notification,
        send_shutdown_notification,
        send_workflow_update
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[WARN] Telegram notifications not available")

class WorkflowProcessor:
    def __init__(self, workflow_path='/home/ubuntu/financial_orchestrator/workflows/example_quant_research.json'):
        self.workflow_path = workflow_path
        self.workflow_data = self.load_workflow()
        self.processing_active = False
        self.process_thread = None
        
    def load_workflow(self):
        """Load workflow data from JSON file"""
        try:
            with open(self.workflow_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            print(f"Failed to load workflow: {e}")
            return self.get_default_workflow()
    
    def get_default_workflow(self):
        """Return a default workflow structure"""
        return {
            "workflow_id": "default",
            "workflow_name": "Default Workflow",
            "description": "Default workflow structure",
            "start_time": datetime.now().isoformat() + "Z",
            "status": "initialized",
            "current_phase": "Not Started",
            "progress_percentage": 0,
            "phases": [],
            "risk_score": 0.0,
            "risk_level": "low",
            "notes": "Workflow initialized"
        }
    
    def save_workflow(self):
        """Save workflow data to JSON file"""
        try:
            with open(self.workflow_path, 'w') as file:
                json.dump(self.workflow_data, file, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save workflow: {e}")
            return False
    
    def update_task_progress(self, phase_index, task_index, progress):
        """Update progress for a specific task"""
        if (0 <= phase_index < len(self.workflow_data['phases']) and 
            0 <= task_index < len(self.workflow_data['phases'][phase_index]['tasks'])):
            
            task = self.workflow_data['phases'][phase_index]['tasks'][task_index]
            task['progress_percentage'] = min(100, max(0, progress))
            
            # Update task status based on progress
            if progress == 0:
                task['status'] = 'pending'
            elif progress < 100:
                task['status'] = 'running'
            else:
                task['status'] = 'completed'
                
            # If task just completed, set completion time
            if progress == 100 and task.get('actual_end_time') is None:
                task['actual_end_time'] = datetime.now().isoformat() + "Z"
                
            return True
        return False
    
    def calculate_phase_progress(self, phase_index):
        """Calculate overall progress for a phase based on task progress"""
        if 0 <= phase_index < len(self.workflow_data['phases']):
            phase = self.workflow_data['phases'][phase_index]
            tasks = phase['tasks']
            
            if not tasks:
                return 0
                
            total_progress = sum(task['progress_percentage'] for task in tasks)
            return total_progress // len(tasks)
        return 0
    
    def calculate_overall_progress(self):
        """Calculate overall workflow progress"""
        if not self.workflow_data['phases']:
            return 0
            
        phase_progresses = []
        for i, phase in enumerate(self.workflow_data['phases']):
            phase_progress = self.calculate_phase_progress(i)
            phase_progresses.append(phase_progress)
            
        return sum(phase_progresses) // len(phase_progresses) if phase_progresses else 0
    
    def update_workflow_status(self):
        """Update overall workflow status and progress"""
        overall_progress = self.calculate_overall_progress()
        self.workflow_data['progress_percentage'] = overall_progress
        
        # Determine current phase
        current_phase_idx = None
        for i, phase in enumerate(self.workflow_data['phases']):
            phase_progress = self.calculate_phase_progress(i)
            if phase_progress < 100:  # Found first incomplete phase
                current_phase_idx = i
                break
                
        if current_phase_idx is not None:
            self.workflow_data['current_phase'] = self.workflow_data['phases'][current_phase_idx]['name']
            
            # Update phase status
            for i, phase in enumerate(self.workflow_data['phases']):
                phase_progress = self.calculate_phase_progress(i)
                if i < current_phase_idx:
                    phase['status'] = 'completed'
                elif i == current_phase_idx:
                    phase['status'] = 'in_progress' if phase_progress > 0 else 'pending'
                else:
                    phase['status'] = 'pending'
        else:
            # All phases complete
            self.workflow_data['current_phase'] = 'Completed'
            self.workflow_data['status'] = 'completed'
            for phase in self.workflow_data['phases']:
                phase['status'] = 'completed'
        
        # Update overall status
        if overall_progress < 100:
            self.workflow_data['status'] = 'running'
        else:
            self.workflow_data['status'] = 'completed'
            
        # Update risk score (simulate based on progress)
        # Lower risk as workflow progresses successfully
        base_risk = 0.3
        progress_factor = (100 - overall_progress) / 100 * 0.2  # Risk decreases as we progress
        self.workflow_data['risk_score'] = max(0.1, base_risk - progress_factor)
        
        # Update risk level
        if self.workflow_data['risk_score'] >= 0.8:
            self.workflow_data['risk_level'] = 'high'
        elif self.workflow_data['risk_score'] >= 0.6:
            self.workflow_data['risk_level'] = 'medium'
        else:
            self.workflow_data['risk_level'] = 'low'
            
        # Update notes
        self.workflow_data['notes'] = f"Workflow {overall_progress}% complete. Current phase: {self.workflow_data['current_phase']}"
        
        # Update timestamp
        self.workflow_data['last_updated'] = datetime.now().isoformat() + "Z"
        
        return self.save_workflow()
    
    def processing_loop(self):
        """Main processing loop that simulates workflow execution"""
        print("Starting workflow processing simulation")
        
        # Simulate work on tasks
        task_sequence = [
            (0, 0),  # Phase 0, Task 0: Market Data Ingestion
            (0, 1),  # Phase 0, Task 1: Alternative Data Integration
            (1, 0),  # Phase 1, Task 0: Technical Indicator Calculation
        ]
        
        progress_steps = [0, 20, 40, 60, 80, 100]
        
        for phase_idx, task_idx in task_sequence:
            if not self.processing_active:
                break
                
            for progress in progress_steps:
                if not self.processing_active:
                    break
                    
                self.update_task_progress(phase_idx, task_idx, progress)
                self.update_workflow_status()
                print(f"Updated task ({phase_idx},{task_idx}) to {progress}%")
                time.sleep(5)  # Simulate work taking time
                
            # Small break between tasks
            time.sleep(2)
            
        # Mark workflow as complete
        self.processing_active = False
        self.update_workflow_status()
        print("Workflow processing simulation completed")
    
    def start_processing(self):
        """Start the workflow processing simulation"""
        if not self.processing_active:
            self.processing_active = True
            self.process_thread = threading.Thread(target=self.processing_loop, daemon=True)
            self.process_thread.start()
            print("Workflow processing started")
            return True
        else:
            print("Workflow processing already active")
            return False
    
    def stop_processing(self):
        """Stop the workflow processing simulation"""
        if self.processing_active:
            self.processing_active = False
            if self.process_thread:
                self.process_thread.join(timeout=5)
            print("Workflow processing stopped")
            return True
        else:
            print("Workflow processing not active")
            return False
    
    def get_status(self):
        """Get current workflow status"""
        return self.workflow_data.copy()

# Example usage
if __name__ == "__main__":
    print("Starting Workflow Processor...")
    
    if TELEGRAM_AVAILABLE:
        send_startup_notification("Workflow Processor")
    
    processor = WorkflowProcessor()
    
    # Start processing
    processor.start_processing()
    
    try:
        # Run indefinitely
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\nShutting down Workflow Processor...")
    finally:
        processor.stop_processing()
        if TELEGRAM_AVAILABLE:
            send_shutdown_notification("Workflow Processor")