#!/usr/bin/env python3
"""
Log Tailer for Telegram Watch Tower
Efficient log file monitoring with pattern matching
"""

import threading
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Callable
from collections import deque

logger = logging.getLogger('LogTailer')

class LogTailer:
    def __init__(self, config: Dict):
        self.config = config
        self.log_config = config.get('watchtower', {}).get('log_files', [])
        self.memory_config = config.get('watchtower', {}).get('memory', {})
        
        self.tailing_active = False
        self.tailer_thread = None
        self.log_callbacks: List[Callable] = []
        
        self.file_positions: Dict[str, int] = {}
        self.recent_logs: deque = deque(maxlen=100)
        
        self.initialized = False
        
    def start(self):
        """Start log tailing"""
        if self.tailing_active:
            return
        
        self._initialize_positions()
        self.tailing_active = True
        self.tailer_thread = threading.Thread(target=self._tailing_loop, daemon=True)
        self.tailer_thread.start()
        logger.info(f"Log tailing started for {len(self.log_config)} files")
    
    def stop(self):
        """Stop log tailing"""
        self.tailing_active = False
        if self.tailer_thread:
            self.tailer_thread.join(timeout=5)
        logger.info("Log tailing stopped")
    
    def register_callback(self, callback: Callable):
        """Register a callback for log events"""
        self.log_callbacks.append(callback)
    
    def _initialize_positions(self):
        """Initialize file positions for all log files"""
        for log_file in self.log_config:
            path = log_file.get('path')
            if path and os.path.exists(path):
                with open(path, 'rb') as f:
                    f.seek(0, 2)
                    self.file_positions[path] = f.tell()
        self.initialized = True
    
    def _tailing_loop(self):
        """Main tailing loop"""
        while self.tailing_active:
            try:
                for log_file in self.log_config:
                    self._check_log_file(log_file)
                time.sleep(2)
            except Exception as e:
                logger.error(f"Tailing loop error: {e}")
                time.sleep(5)
    
    def _check_log_file(self, log_file_config: Dict):
        """Check a single log file for new entries"""
        path = log_file_config.get('path')
        name = log_file_config.get('name', os.path.basename(path))
        patterns = log_file_config.get('event_patterns', [])
        
        if not path or not os.path.exists(path):
            return
        
        try:
            current_pos = self.file_positions.get(path, 0)
            
            with open(path, 'rb') as f:
                f.seek(current_pos)
                new_lines = f.readlines()
                self.file_positions[path] = f.tell()
            
            for line in new_lines:
                try:
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    if line_str:
                        self._process_log_line(name, line_str, patterns)
                except Exception as e:
                    logger.error(f"Line processing error: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking {path}: {e}")
            self.file_positions[path] = 0
    
    def _process_log_line(self, source: str, line: str, patterns: List[str]):
        """Process a single log line"""
        if not patterns:
            return
        
        matched_pattern = None
        for pattern in patterns:
            if pattern.upper() in line.upper():
                matched_pattern = pattern
                break
        
        if matched_pattern:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'source': source,
                'pattern': matched_pattern,
                'line': line
            }
            
            self.recent_logs.append(log_entry)
            
            for callback in self.log_callbacks:
                try:
                    callback(log_entry)
                except Exception as e:
                    logger.error(f"Log callback error: {e}")
    
    def get_recent_logs(self, limit: int = 20, source: str = None) -> List[Dict]:
        """Get recent log entries"""
        logs = list(self.recent_logs)
        if source:
            logs = [l for l in logs if l['source'] == source]
        return logs[-limit:]
    
    def get_log_summary(self) -> Dict:
        """Get log summary statistics"""
        sources = {}
        for log in self.recent_logs:
            source = log['source']
            sources[source] = sources.get(source, 0) + 1
        
        return {
            'total_entries': len(self.recent_logs),
            'sources': sources,
            'tailing_active': self.tailing_active,
            'files_tracked': len(self.log_config)
        }
    
    def format_log_message(self, log_entry: Dict) -> str:
        """Format a log entry for Telegram"""
        severity_emoji = {
            'CRITICAL': '\u26a0\ufe0f',
            'ERROR': '\u274c',
            'WARNING': '\u1f7e1',
            'ALERT': '\u1f7e2',
            'INFO': '\u2139\ufe0f'
        }
        
        emoji = '\u2139\ufe0f'
        line = log_entry['line']
        for sev, em in severity_emoji.items():
            if sev in line.upper():
                emoji = em
                break
        
        return f"{emoji} *{log_entry['source']}*\n" \
               f"_{log_entry['timestamp']}_\n" \
               f"`{log_entry['line'][:200]}`"
