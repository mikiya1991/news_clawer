"""
Configuration settings for X.com Tweet Scraper
"""
import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent

# Database
DATABASE_PATH = PROJECT_ROOT / "tweets.db"
DATABASE_CHECK_SAME_THREAD = False

# Playwright
BROWSER_USER_DATA_DIR = PROJECT_ROOT / "browser_state"
HEADLESS_MODE = False  # Set to True for background operation
BROWSER_TIMEOUT = 30000  # milliseconds

# X.com Collection Settings
X_COM_URL = "https://x.com/home"
COLLECTION_INTERVAL_MINUTES = 60  # Run scraper every X minutes
SCROLL_PAUSE_TIME = 2  # seconds between scrolls
MAX_SCROLL_ATTEMPTS = 5  # Maximum number of scroll attempts per session
TWEET_EXTRACTION_TIMEOUT = 5000  # milliseconds

# Logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "scraper.log"
LOG_LEVEL = "INFO"
LOG_RETENTION_DAYS = 7

# Retry Settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Selectors (X.com uses data-testid attributes - more stable than class names)
TWEET_SELECTOR = '[data-testid="tweet"]'
TWEET_TEXT_SELECTOR = '[data-testid="tweetText"] span'
USERNAME_SELECTOR = '[data-testid="User-Name"]'
LIKE_COUNT_SELECTOR = '[data-testid="like"] span'
VIEW_COUNT_SELECTOR = '[data-testid="views"] span'
RETWEET_COUNT_SELECTOR = '[data-testid="retweet"] span'

# Debugging
DEBUG_SCREENSHOTS = True
SCREENSHOTS_DIR = PROJECT_ROOT / "debug_screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
