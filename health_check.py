#!/usr/bin/env python3
"""
Health Check Script for Financial Orchestrator
Monitors system health and sends periodic reports to Telegram
"""
import os
import sys
import time
import json
import psutil
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from telegram_notify import send_to_admin, send_alert

COMPONENTS = {
    'telegram_watchtower/bot_controller.py': ('Telegram Bot', 'telegram.pid'),
    'monitoring/risk_monitor.py': ('Risk Monitor', 'risk.pid'),
    'validation/validation_engine.py': ('Validation Engine', 'validation.pid'),
    'optimization/agent_optimizer.py': ('Agent Optimizer', 'optimizer.pid'),
    'workflows/process_workflow.py': ('Workflow Processor', 'workflow.pid')
}

HEALTH_LOG = Path(__file__).parent / 'logs' / 'health_check.log'
STATUS_FILE = Path(__file__).parent / 'logs' / 'status_state.json'
HEARTBEAT_STATE_FILE = Path(__file__).parent / 'logs' / 'heartbeat_state.json'
HEARTBEAT_THROTTLE_SECONDS = 3600

def log(message):
    """Log to file and print"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    print(line)
    HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_LOG, 'a') as f:
        f.write(line + '\n')

def should_send_heartbeat():
    """Only send heartbeat once per hour max"""
    try:
        if HEARTBEAT_STATE_FILE.exists():
            with open(HEARTBEAT_STATE_FILE, 'r') as f:
                state = json.load(f)
            last_sent = state.get('last_heartbeat', 0)
            if time.time() - last_sent < HEARTBEAT_THROTTLE_SECONDS:
                return False
        return True
    except:
        return True

def record_heartbeat_sent():
    """Record that a heartbeat was sent"""
    try:
        with open(HEARTBEAT_STATE_FILE, 'w') as f:
            json.dump({'last_heartbeat': time.time()}, f)
    except Exception as e:
        log(f"Could not save heartbeat state: {e}")

def load_previous_status():
    """Load previous status from file"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        log(f"Could not load previous status: {e}")
    return {}

def save_current_status(status):
    """Save current status to file"""
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f)
    except Exception as e:
        log(f"Could not save status: {e}")

def detect_status_change(previous_status, current_status):
    """Detect status changes and return alert type and details"""
    prev_running = {k: v.get('running', False) for k, v in previous_status.items()}
    curr_running = {k: v.get('running', False) for k, v in current_status.items()}
    
    went_down = []
    recovered = []
    
    for component in curr_running:
        was_running = prev_running.get(component, False)
        is_running = curr_running[component]
        
        if not was_running and is_running:
            recovered.append(component)
        elif was_running and not is_running:
            went_down.append(component)
    
    if went_down and not recovered:
        return 'DOWN', went_down
    elif recovered and not went_down:
        return 'RECOVERY', recovered
    elif went_down and recovered:
        return 'PARTIAL', {'down': went_down, 'recovered': recovered}
    
    return 'OK', None

def check_component_running(name, pid_file):
    """Check if a component is running"""
    try:
        pid_path = Path(pid_file)
        if pid_path.exists():
            pid = int(pid_path.read_text().strip())
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                if process.is_running():
                    mem_mb = process.memory_info().rss / 1024 / 1024
                    cpu_percent = process.cpu_percent(interval=0.1)
                    return {'running': True, 'pid': pid, 'memory_mb': mem_mb, 'cpu_percent': cpu_percent}
        return {'running': False}
    except Exception as e:
        return {'running': False, 'error': str(e)}

def get_system_stats():
    """Get overall system statistics"""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu_percent': psutil.cpu_percent(interval=0.5),
            'memory_percent': memory.percent,
            'memory_used_gb': round(memory.used / (1024**3), 2),
            'memory_total_gb': round(memory.total / (1024**3), 2),
            'disk_percent': disk.percent,
            'disk_used_gb': round(disk.used / (1024**3), 2),
            'disk_total_gb': round(disk.total / (1024**3), 2)
        }
    except Exception as e:
        log(f"Error getting system stats: {e}")
        return None

def check_processes():
    """Check all monitored processes"""
    results = {}
    logs_dir = Path(__file__).parent / 'logs'
    
    for script, (name, pid_file_name) in COMPONENTS.items():
        pid_file = logs_dir / pid_file_name
        result = check_component_running(name, pid_file)
        results[name] = result
    
    return results

def format_health_report(system_stats, component_status):
    """Format health report for Telegram"""
    report = ["📊 *Financial Orchestrator Health Report*"]
    report.append(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    report.append("🖥️ *System Stats:*")
    if system_stats:
        report.append(f"  CPU: {system_stats['cpu_percent']:.1f}%")
        report.append(f"  RAM: {system_stats['memory_percent']:.1f}% ({system_stats['memory_used_gb']}/{system_stats['memory_total_gb']} GB)")
        report.append(f"  Disk: {system_stats['disk_percent']:.1f}% ({system_stats['disk_used_gb']}/{system_stats['disk_total_gb']} GB)")
    else:
        report.append("  ⚠️ Unable to retrieve system stats")
    
    report.append("\n🔧 *Components:*")
    all_running = True
    for name, status in component_status.items():
        if status.get('running'):
            mem = status.get('memory_mb', 0)
            cpu = status.get('cpu_percent', 0)
            report.append(f"  ✅ {name} (PID:{status['pid']}, RAM:{mem:.1f}MB, CPU:{cpu:.1f}%)")
        else:
            report.append(f"  ❌ {name} - NOT RUNNING")
            all_running = False
    
    if all_running:
        report.append("\n🎯 All systems operational")
    else:
        report.append("\n⚠️ Some components need attention")
    
    return '\n'.join(report)

def format_status_change_message(change_type, details, system_stats):
    """Format status change notification for Telegram"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if change_type == 'DOWN':
        components = ', '.join(details)
        return f"""🚨 *COMPONENT DOWN ALERT*

⚠️ Components stopped:
• {components}

Time: {timestamp}

Run health check manually to diagnose."""

    elif change_type == 'RECOVERY':
        components = ', '.join(details)
        return f"""✅ *RECOVERY ALERT*

🟢 Components recovered:
• {components}

Time: {timestamp}

All systems back online!"""

    elif change_type == 'PARTIAL':
        down = ', '.join(details['down'])
        recovered = ', '.join(details['recovered'])
        return f"""⚠️ *PARTIAL STATUS CHANGE*

🟢 Recovered:
• {recovered}

🔴 Down:
• {down}

Time: {timestamp}"""

    return None

def format_heartbeat_message(system_stats, component_status):
    """Format minimal heartbeat message for all OK"""
    timestamp = datetime.now().strftime('%H:%M')
    return f"""💚 *HEARTBEAT* - {timestamp}

✅ All 5 services running"""

def send_health_check():
    """Perform health check and send report"""
    log("Starting health check...")
    
    previous_status = load_previous_status()
    system_stats = get_system_stats()
    component_status = check_processes()
    
    change_type, change_details = detect_status_change(previous_status, component_status)
    
    save_current_status(component_status)
    
    all_running = all(s.get('running', False) for s in component_status.values())
    
    if change_type == 'DOWN':
        message = format_status_change_message(change_type, change_details, system_stats)
        send_to_admin(message if message else "🚨 Components down!")
        log(f"ALERT: Components down: {change_details}")
        
    elif change_type == 'RECOVERY':
        message = format_status_change_message(change_type, change_details, system_stats)
        send_to_admin(message if message else "✅ Components recovered!")
        log(f"RECOVERY: Components recovered: {change_details}")
        
    elif change_type == 'PARTIAL':
        message = format_status_change_message(change_type, change_details, system_stats)
        send_to_admin(message if message else "⚠️ Mixed status change")
        log(f"MIXED: {change_details}")
        
    elif all_running:
        if should_send_heartbeat():
            message = format_heartbeat_message(system_stats, component_status)
            send_to_admin(message)
            record_heartbeat_sent()
            log("Heartbeat: All systems OK")
        else:
            log("Heartbeat suppressed (throttled)")
    
    log("Health check completed")
    return all_running

def run_once():
    """Run health check once"""
    return send_health_check()

def run_continuous(interval=300):
    """Run health check continuously"""
    log(f"Starting continuous health monitoring (interval: {interval}s)")
    
    while True:
        try:
            send_health_check()
            time.sleep(interval)
        except KeyboardInterrupt:
            log("Health check stopped by user")
            break
        except Exception as e:
            log(f"Health check error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        run_continuous(interval)
    else:
        run_once()
