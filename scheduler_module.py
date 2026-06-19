"""
Scheduler Module - Background task scheduler for tweet collection
Can be controlled via Flask web interface
"""
import asyncio
import logging
import schedule
import sys
import threading
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from logger import configure_logging
from main import collection_cycle
import config

logger = logging.getLogger(__name__)

# Global state
_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_config_file = Path(__file__).parent / 'scheduler_config.json'
_log_file = Path(__file__).parent / 'logs' / 'scheduler_history.json'
_log_history: list = []
_max_log_entries = 100
_current_config: Dict[str, Any] = {
    'interval': 1,
    'unit': 'hours',
    'running': False
}


# Ensure logs directory exists
_log_file.parent.mkdir(exist_ok=True)


def _collect_tweets():
    """Run the tweet collection script and log result"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {
        'timestamp': timestamp,
        'status': 'running',
        'message': 'Starting collection'
    }
    _add_log_entry(log_entry)

    try:
        success = asyncio.run(collection_cycle(headless=True))
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if success:
            log_entry['status'] = 'success'
            log_entry['message'] = 'Collection completed successfully'
        else:
            log_entry['status'] = 'error'
            log_entry['message'] = 'Collection completed with errors (see logs for details)'
    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry['status'] = 'error'
        log_entry['message'] = f'Collection failed: {str(e)[:200]}'
        logger.exception("Collection failed")

    log_entry['timestamp'] = timestamp
    _add_log_entry(log_entry)


def _add_log_entry(entry: Dict[str, Any]):
    """Add log entry to history and save to file"""
    global _log_history
    _log_history.insert(0, entry)
    if len(_log_history) > _max_log_entries:
        _log_history = _log_history[:_max_log_entries]
    _save_logs()


def _save_logs():
    """Save log history to file"""
    try:
        with open(_log_file, 'w', encoding='utf-8') as f:
            json.dump(_log_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save logs: {e}")


def _load_logs():
    """Load log history from file"""
    global _log_history
    if _log_file.exists():
        try:
            with open(_log_file, 'r', encoding='utf-8') as f:
                _log_history = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load logs: {e}")
            _log_history = []


def _run_scheduler_loop():
    """Main scheduler loop running in background thread"""
    while not _stop_event.is_set():
        schedule.run_pending()
        # Sleep in small increments to allow responsive stop
        for _ in range(6):  # 6 * 10 seconds = 60 seconds
            if _stop_event.is_set():
                break
            time.sleep(10)


def _setup_schedule(interval: int, unit: str):
    """Setup schedule based on interval and unit"""
    schedule.clear()
    
    if unit == 'minutes':
        schedule.every(interval).minutes.do(_collect_tweets)
    elif unit == 'hours':
        schedule.every(interval).hours.do(_collect_tweets)
    elif unit == 'days':
        schedule.every(interval).days.do(_collect_tweets)
    else:
        schedule.every().hour.do(_collect_tweets)  # default


def start_scheduler(interval: int = 1, unit: str = 'hours') -> bool:
    """
    Start the scheduler with given configuration
    
    Args:
        interval: Number of units between runs
        unit: 'minutes', 'hours', or 'days'
    
    Returns:
        True if started successfully, False if already running
    """
    global _scheduler_thread, _current_config
    
    if is_running():
        return False
    
    _stop_event.clear()
    _setup_schedule(interval, unit)

    # Ensure unified logging is configured for background thread
    configure_logging(config.LOG_DIR, config.LOG_LEVEL, config.LOG_RETENTION_DAYS)

    _scheduler_thread = threading.Thread(target=_run_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    
    _current_config = {
        'interval': interval,
        'unit': unit,
        'running': True,
        'started_at': datetime.now().isoformat()
    }
    _save_config()
    
    _add_log_entry({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'info',
        'message': f'Scheduler started: every {interval} {unit}'
    })
    
    return True


def stop_scheduler() -> bool:
    """
    Stop the running scheduler
    
    Returns:
        True if stopped successfully, False if not running
    """
    global _scheduler_thread, _current_config
    
    if not is_running():
        return False
    
    _stop_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)
    
    schedule.clear()
    _scheduler_thread = None
    
    _current_config['running'] = False
    _current_config['stopped_at'] = datetime.now().isoformat()
    _save_config()
    
    _add_log_entry({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'info',
        'message': 'Scheduler stopped'
    })
    
    return True


def is_running() -> bool:
    """Check if scheduler is currently running"""
    return _scheduler_thread is not None and _scheduler_thread.is_alive()


def get_status() -> Dict[str, Any]:
    """Get current scheduler status"""
    next_run = None
    if is_running() and schedule.default_scheduler.jobs:
        try:
            next_run = schedule.next_run().strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
    
    return {
        'running': is_running(),
        'config': _current_config,
        'next_run': next_run,
        'log_history': _log_history[:10]  # Last 10 entries
    }


def _save_config():
    """Save configuration to file"""
    try:
        with open(_config_file, 'w', encoding='utf-8') as f:
            json.dump(_current_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


def load_config() -> Dict[str, Any]:
    """Load configuration from file"""
    global _current_config
    if _config_file.exists():
        try:
            with open(_config_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                _current_config.update(loaded)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    return _current_config


def auto_start_if_enabled():
    """Auto-start scheduler if it was running before"""
    cfg = load_config()
    if cfg.get('running', False):
        interval = cfg.get('interval', 1)
        unit = cfg.get('unit', 'hours')
        start_scheduler(interval, unit)
        logger.info(f"Auto-started scheduler: every {interval} {unit}")


# Load config and logs on module import
load_config()
_load_logs()
