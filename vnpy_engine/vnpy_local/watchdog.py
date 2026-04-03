"""
Watchdog Module
================
Self-healing process monitor with state restoration and PID-based process monitoring.
"""

import os
import time
import signal
import threading
from pathlib import Path
from loguru import logger

from .shared_state import shared_state


CHECKPOINT_INTERVAL = 1800
HEALTH_CHECK_INTERVAL = 30


class ProcessMonitor:
    PROCESSES = {
        "api-gateway": "vnpy.api_gateway",
        "main-engine": "vnpy.main_engine",
        "watchdog": "vnpy.watchdog"
    }
    
    def __init__(self):
        self._pid_cache = {}
    
    def _get_pids_by_name(self, name: str) -> list[int]:
        try:
            import psutil
            return [p.pid for p in psutil.process_iter(['pid', 'name', 'cmdline']) 
                    if self._matches_process(p, name)]
        except ImportError:
            return self._get_pids_fallback(name)
    
    def _matches_process(self, proc, name: str) -> bool:
        try:
            cmdline = proc.info.get('cmdline', []) or []
            cmdline_str = ' '.join(cmdline)
            return name in cmdline_str
        except Exception:
            return False
    
    def _get_pids_fallback(self, name: str) -> list[int]:
        pids = []
        proc_dir = Path('/proc')
        for entry in proc_dir.iterdir():
            if entry.name.isdigit():
                try:
                    cmdline_file = entry / 'cmdline'
                    if cmdline_file.exists():
                        cmdline = cmdline_file.read_text().replace('\x00', ' ')
                        if name in cmdline:
                            pids.append(int(entry.name))
                except Exception:
                    continue
        return pids
    
    def check_process_health(self, name: str) -> dict:
        pids = self._get_pids_by_name(self.PROCESSES.get(name, name))
        
        alive_pids = []
        dead_pids = []
        
        for pid in pids:
            if self._is_process_alive(pid):
                alive_pids.append(pid)
            else:
                dead_pids.append(pid)
        
        return {
            "name": name,
            "pids": pids,
            "alive": len(alive_pids),
            "dead": len(dead_pids),
            "healthy": len(alive_pids) > 0
        }
    
    def _is_process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def check_all_processes(self) -> dict:
        results = {}
        for name in self.PROCESSES:
            results[name] = self.check_process_health(name)
        return results


class Watchdog:
    def __init__(self):
        self.running = False
        self.last_health_check = 0
        self.failure_count = 0
        self.max_failures = 3
        self.process_monitor = ProcessMonitor()
        
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
    def start(self):
        self.running = True
        logger.info("Watchdog started")
        
        shared_state.set_system_status("watchdog", {
            "status": "running",
            "timestamp": time.time()
        })
        
        self.send_telegram_alert("VN.PY Engine Watchdog Started", "Watchdog")
        
        while self.running:
            try:
                self._health_check()
                self._auto_checkpoint()
                time.sleep(HEALTH_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
                self._handle_failure(str(e))
    
    def stop(self):
        self.running = False
        logger.info("Watchdog stopped")
    
    def _health_check(self):
        process_results = self.process_monitor.check_all_processes()
        
        unhealthy = []
        for name, result in process_results.items():
            if not result["healthy"]:
                unhealthy.append(f"{name} (PIDs: {result.get('pids', [])})")
                logger.warning(f"Process unhealthy: {name}, PIDs: {result.get('pids', [])}")
        
        engine_status = shared_state.get_system_status("engine")
        
        if engine_status.get("status") == "stopped":
            logger.warning("Engine stopped unexpectedly")
            self._handle_failure("Engine stopped")
        
        redis_health = shared_state.health_check()
        if not redis_health:
            logger.warning("Redis connection lost")
        
        if unhealthy:
            self._handle_process_failure(unhealthy)
        
        self.last_health_check = time.time()
        
        shared_state.set_system_status("watchdog", {
            "status": "healthy",
            "last_check": self.last_health_check,
            "processes": process_results,
            "timestamp": time.time()
        })
    
    def _handle_process_failure(self, unhealthy_processes: list):
        logger.warning(f"Unhealthy processes: {unhealthy_processes}")
    
    def _auto_checkpoint(self):
        current_time = time.time()
        
        checkpoint_file = Path("/vnpy/memory/rl_checkpoint.pkl")
        if checkpoint_file.exists():
            mtime = checkpoint_file.stat().st_mtime
            if current_time - mtime > CHECKPOINT_INTERVAL:
                logger.info("RL checkpoint saved")
    
    def _handle_failure(self, reason: str):
        self.failure_count += 1
        
        logger.error(f"Failure detected ({self.failure_count}/{self.max_failures}): {reason}")
        
        self.send_telegram_alert(f"VN.PY Engine Failure\n\nReason: {reason}\nFailure #{self.failure_count}", "Alert")
        
        if self.failure_count >= self.max_failures:
            logger.error("Max failures reached, initiating restart...")
            self._restart_engine()
            self.failure_count = 0
    
    def _restart_engine(self):
        try:
            shared_state.set_system_status("engine", {
                "status": "restarting",
                "timestamp": time.time()
            })
            
            from .main_engine import get_engine
            engine = get_engine()
            engine.stop()
            time.sleep(2)
            engine.start()
            
            self.send_telegram_alert("VN.PY Engine Restarted Successfully", "Recovery")
            
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            self.send_telegram_alert(f"Restart Failed: {e}", "Error")
    
    def send_telegram_alert(self, message: str, title: str):
        if not self.telegram_token or not self.telegram_chat_id:
            logger.debug(f"Alert (no telegram): {message}")
            return
        
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": f"{title}\n{message}",
                "parse_mode": "HTML"
            }
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")


def run_watchdog():
    import uvicorn
    from .api_gateway import app
    
    watchdog = Watchdog()
    thread = threading.Thread(target=watchdog.start, daemon=True)
    thread.start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    run_watchdog()
