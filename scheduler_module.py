"""
Scheduler Module - Background task scheduler for tweet collection
Can be controlled via Flask web interface
"""
import asyncio
import logging
import os
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
from main import collection_cycle, login_flow_auto, score_history, rescore_news
import config

logger = logging.getLogger(__name__)

# Global state
_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_config_file = config.DATA_ROOT / 'scheduler_config.json'
_pid_file = config.DATA_ROOT / 'scheduler.pid'
_log_file = config.LOG_DIR / 'scheduler_history.json'
_log_history: list = []
_max_log_entries = 100
_current_config: Dict[str, Any] = {
    'interval': 1,
    'unit': 'hours',
    'running': False
}

# Global job mutex: scheduled and manual jobs are serialized to avoid
# concurrent browser instances on the shared browser_state and SQLite locks
_job_lock = threading.Lock()
_busy_job: Optional[str] = None  # 'collection' | 'news' | 'login' | None
_history_lock = threading.Lock()


# Ensure logs directory exists
_log_file.parent.mkdir(exist_ok=True)


def _collect_tweets(headless: bool = True):
    """Run the tweet collection script and log result"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {
        'timestamp': timestamp,
        'status': 'running',
        'message': 'Starting collection'
    }
    _add_log_entry(log_entry)

    try:
        success = asyncio.run(collection_cycle(headless=headless))
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


def _collect_news():
    """Run the news cycle (RSS + X -> DeepSeek scoring -> WeChat push) and log result"""
    from news_pipeline import run_news_cycle

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {
        'timestamp': timestamp,
        'status': 'running',
        'message': 'Starting news cycle'
    }
    _add_log_entry(log_entry)

    try:
        result = run_news_cycle()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if result.get('error'):
            log_entry['status'] = 'error'
            log_entry['message'] = f"News cycle failed: {result['error'][:150]}"
        else:
            log_entry['status'] = 'success'
            log_entry['message'] = (f"News cycle: fetched {result['fetched']}, "
                                    f"new {result['new_items']}, scored "
                                    f"{result['scored']}, pushed "
                                    f"{result['pushed_count']}")
    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry['status'] = 'error'
        log_entry['message'] = f'News cycle failed: {str(e)[:200]}'
        logger.exception("News cycle failed")

    log_entry['timestamp'] = timestamp
    _add_log_entry(log_entry)


def _acquire_job(name: str) -> bool:
    """Claim the global job slot. False if another job is in progress."""
    global _busy_job
    with _job_lock:
        if _busy_job is not None:
            return False
        _busy_job = name
        return True


def _release_job(name: str):
    """Release the global job slot if it belongs to this job."""
    global _busy_job
    with _job_lock:
        if _busy_job == name:
            _busy_job = None


def _run_collection_job(headless: bool = True):
    """Run one collection cycle, skipping if another job is in progress."""
    if not _acquire_job('collection'):
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'info',
            'message': 'Collection skipped: another job is running',
        })
        return
    try:
        _collect_tweets(headless=headless)
    finally:
        _release_job('collection')


def _run_news_job():
    """Run one news cycle, skipping if another job is in progress."""
    if not _acquire_job('news'):
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'info',
            'message': 'News cycle skipped: another job is running',
        })
        return
    try:
        _collect_news()
    finally:
        _release_job('news')


def _run_tweet_scoring_job():
    """AI-score unscored tweets, skipping if another job is in progress."""
    if not _acquire_job('tweet-scoring'):
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'info',
            'message': 'Tweet scoring skipped: another job is running',
        })
        return
    try:
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'running',
            'message': 'Starting tweet AI scoring',
        })
        total_scored, total_hidden = score_history()
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success',
            'message': (f'Tweet scoring: {total_scored} scored, '
                        f'{total_hidden} hidden'),
        })
    except Exception as e:
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error',
            'message': f'Tweet scoring failed: {str(e)[:150]}',
        })
        logger.exception("Tweet scoring job failed")
    finally:
        _release_job('tweet-scoring')


def _run_news_scoring_job():
    """Re-score recent news items, skipping if another job is in progress."""
    if not _acquire_job('news-scoring'):
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'info',
            'message': 'News scoring skipped: another job is running',
        })
        return
    try:
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'running',
            'message': 'Starting news AI scoring',
        })
        result = rescore_news()
        if result.get('error'):
            _add_log_entry({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'error',
                'message': f"News scoring failed: {result['error'][:150]}",
            })
        else:
            _add_log_entry({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'success',
                'message': (f"News scoring: {result['scored']} rescored, "
                            f"{result['hidden']} hidden"),
            })
    except Exception as e:
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error',
            'message': f'News scoring failed: {str(e)[:150]}',
        })
        logger.exception("News scoring job failed")
    finally:
        _release_job('news-scoring')


def _run_login_job():
    """Run the auto-detect login flow, skipping if another job is in progress."""
    if not _acquire_job('login'):
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'info',
            'message': 'Login skipped: another job is running',
        })
        return
    try:
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'running',
            'message': 'Starting login flow (browser will open)',
        })
        success = asyncio.run(login_flow_auto())
        _add_log_entry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success' if success else 'error',
            'message': 'Login completed successfully' if success
                       else 'Login failed or timed out',
        })
    finally:
        _release_job('login')


def trigger_collection_now() -> Dict[str, Any]:
    """Kick off a manual (visible-browser) collection cycle in the background."""
    with _job_lock:
        if _busy_job is not None:
            return {'started': False, 'busy': _busy_job}
    threading.Thread(target=_run_collection_job, kwargs={'headless': False},
                     name='manual-collection', daemon=True).start()
    return {'started': True}


def trigger_news_now() -> Dict[str, Any]:
    """Kick off a manual news cycle in the background."""
    with _job_lock:
        if _busy_job is not None:
            return {'started': False, 'busy': _busy_job}
    threading.Thread(target=_run_news_job, name='manual-news', daemon=True).start()
    return {'started': True}


def trigger_login() -> Dict[str, Any]:
    """Kick off the auto-detect login flow in the background."""
    with _job_lock:
        if _busy_job is not None:
            return {'started': False, 'busy': _busy_job}
    threading.Thread(target=_run_login_job, name='manual-login', daemon=True).start()
    return {'started': True}


def trigger_tweet_scoring() -> Dict[str, Any]:
    """Kick off AI scoring of unscored tweets in the background."""
    with _job_lock:
        if _busy_job is not None:
            return {'started': False, 'busy': _busy_job}
    threading.Thread(target=_run_tweet_scoring_job,
                     name='manual-tweet-scoring', daemon=True).start()
    return {'started': True}


def trigger_news_scoring() -> Dict[str, Any]:
    """Kick off re-scoring of recent news items in the background."""
    with _job_lock:
        if _busy_job is not None:
            return {'started': False, 'busy': _busy_job}
    threading.Thread(target=_run_news_scoring_job,
                     name='manual-news-scoring', daemon=True).start()
    return {'started': True}


def _add_log_entry(entry: Dict[str, Any]):
    """Add log entry to history and save to file (thread-safe)"""
    global _log_history
    with _history_lock:
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


def _check_existing_process() -> bool:
    """Return True if another live process holds the scheduler PID lock."""
    if not _pid_file.exists():
        return False
    try:
        pid = int(_pid_file.read_text().strip())
    except (ValueError, OSError):
        return False
    try:
        os.kill(pid, 0)  # Signal 0 = existence check only
        return True
    except ProcessLookupError:
        return False  # stale pid file, previous process is gone
    except PermissionError:
        return True  # exists but owned by someone else


def _acquire_pid_lock() -> bool:
    """Take the cross-process scheduler lock. False if another scheduler is live.

    Note: is_running() only guards within this process; the PID file is what
    stops a second app.py instance from starting its own scheduler thread.
    """
    if _check_existing_process():
        return False
    try:
        _pid_file.write_text(str(os.getpid()))
        return True
    except OSError as e:
        logger.error(f"Failed to write pid file {_pid_file}: {e}")
        return False


def _release_pid_lock():
    """Remove the PID lock if it belongs to this process."""
    try:
        if _pid_file.exists() and _pid_file.read_text().strip() == str(os.getpid()):
            _pid_file.unlink()
    except OSError:
        pass


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
        schedule.every(interval).minutes.do(_run_collection_job)
    elif unit == 'hours':
        schedule.every(interval).hours.do(_run_collection_job)
    elif unit == 'days':
        schedule.every(interval).days.do(_run_collection_job)
    else:
        schedule.every().hour.do(_run_collection_job)  # default

    # News cycle job - must be registered here (after schedule.clear())
    # or it would be wiped on every scheduler start/stop
    if config.NEWS_SCHEDULE_ENABLED:
        schedule.every(config.NEWS_CYCLE_INTERVAL_MINUTES).minutes.do(_run_news_job)


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

    # Cross-process guard: refuse if another process (e.g. a second web
    # instance) already owns the scheduler PID lock.
    if not _acquire_pid_lock():
        owner = _pid_file.read_text().strip() if _pid_file.exists() else 'unknown'
        logger.warning("Scheduler already running in another process (PID %s) - refusing to start", owner)
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

    _release_pid_lock()
    
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
        'busy_job': _busy_job,
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
        if start_scheduler(interval, unit):
            logger.info(f"Auto-started scheduler: every {interval} {unit}")
        else:
            logger.warning("Scheduler auto-start refused (already running in this process or another)")


# Load config and logs on module import
load_config()
_load_logs()
