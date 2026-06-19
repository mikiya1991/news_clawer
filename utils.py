"""
Utility functions for X.com Tweet Scraper
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List
import csv
from pathlib import Path
import config


def export_to_csv(tweets: List[Dict[str, Any]], output_file: str = None) -> str:
    """
    Export tweets to CSV file
    
    Args:
        tweets: List of tweet dictionaries
        output_file: Output file path (default: tweets_export.csv)
        
    Returns:
        Path to exported CSV file
    """
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"tweets_export_{timestamp}.csv"
    
    if not tweets:
        raise ValueError("No tweets to export")
    
    # Get field names from first tweet
    fieldnames = tweets[0].keys()
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tweets)
    
    return output_file


def export_to_json(tweets: List[Dict[str, Any]], output_file: str = None) -> str:
    """
    Export tweets to JSON file
    
    Args:
        tweets: List of tweet dictionaries
        output_file: Output file path (default: tweets_export.json)
        
    Returns:
        Path to exported JSON file
    """
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"tweets_export_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tweets, f, ensure_ascii=False, indent=2, default=str)
    
    return output_file


def backup_database(backup_dir: str = None) -> str:
    """
    Create backup of tweets database
    
    Args:
        backup_dir: Directory to store backup (default: ./backups)
        
    Returns:
        Path to backup file
    """
    if not backup_dir:
        backup_dir = "backups"
    
    Path(backup_dir).mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = Path(backup_dir) / f"tweets_{timestamp}.db"
    
    import shutil
    shutil.copy(str(config.DATABASE_PATH), str(backup_file))
    
    return str(backup_file)


def get_storage_size() -> Dict[str, Any]:
    """
    Get storage information
    
    Returns:
        Dictionary with file sizes
    """
    sizes = {}
    
    # Database size
    if config.DATABASE_PATH.exists():
        db_size = config.DATABASE_PATH.stat().st_size
        sizes['database'] = {
            'path': str(config.DATABASE_PATH),
            'size_bytes': db_size,
            'size_mb': round(db_size / (1024*1024), 2)
        }
    
    # Browser state size
    if config.BROWSER_USER_DATA_DIR.exists():
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(config.BROWSER_USER_DATA_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        
        sizes['browser_state'] = {
            'path': str(config.BROWSER_USER_DATA_DIR),
            'size_bytes': total_size,
            'size_mb': round(total_size / (1024*1024), 2)
        }
    
    # Logs size
    if config.LOG_DIR.exists():
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(config.LOG_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        
        sizes['logs'] = {
            'path': str(config.LOG_DIR),
            'size_bytes': total_size,
            'size_mb': round(total_size / (1024*1024), 2)
        }
    
    return sizes


def cleanup_old_screenshots(keep_days: int = 7):
    """
    Delete old debug screenshots
    
    Args:
        keep_days: Keep screenshots from last N days
    """
    from datetime import timedelta
    
    if not config.SCREENSHOTS_DIR.exists():
        return
    
    cutoff_time = datetime.now() - timedelta(days=keep_days)
    
    for file in config.SCREENSHOTS_DIR.glob("*.png"):
        file_time = datetime.fromtimestamp(file.stat().st_mtime)
        if file_time < cutoff_time:
            file.unlink()


def print_config():
    """Print current configuration"""
    print("\n" + "="*80)
    print("CURRENT CONFIGURATION")
    print("="*80)
    
    settings = {
        'Database': str(config.DATABASE_PATH),
        'Browser Data Dir': str(config.BROWSER_USER_DATA_DIR),
        'Log File': str(config.LOG_FILE),
        'Collection Interval': f"{config.COLLECTION_INTERVAL_MINUTES} minutes",
        'X.com URL': config.X_COM_URL,
        'Headless Mode': config.HEADLESS_MODE,
        'Max Scroll Attempts': config.MAX_SCROLL_ATTEMPTS,
        'Scroll Pause Time': f"{config.SCROLL_PAUSE_TIME} seconds",
        'Debug Screenshots': config.DEBUG_SCREENSHOTS,
        'Max Retries': config.MAX_RETRIES,
    }
    
    for key, value in settings.items():
        print(f"{key:.<40} {value}")
    
    print("="*80 + "\n")


def verify_installation() -> bool:
    """
    Verify that all required modules and dependencies are installed
    
    Returns:
        True if installation is valid, False otherwise
    """
    import importlib
    
    required_modules = ['playwright', 'sqlite3']
    
    print("\nVerifying installation...")
    print("-" * 40)
    
    all_ok = True
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✓ {module}")
        except ImportError:
            print(f"✗ {module} (missing)")
            all_ok = False
    
    # Check if browser is installed
    try:
        from playwright.async_api import async_playwright
        print(f"✓ playwright async API")
    except ImportError:
        print(f"✗ playwright async API (missing)")
        all_ok = False
    
    print("-" * 40)
    
    if all_ok:
        print("✓ All dependencies installed\n")
    else:
        print("✗ Some dependencies are missing\n")
        print("Run: pip install -r requirements.txt && playwright install\n")
    
    return all_ok
