"""
Configuration settings for X.com Tweet Scraper
"""
import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent

# Load environment variables from .env (no-op if missing; .env is gitignored)
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# Runtime data root: all writable state (database, browser profile, logs,
# scheduler state) lives under this directory. Defaults to the project
# directory; set XCLAWER_DATA_DIR to relocate, e.g. /var/lib/xclawer when
# installed from the .deb package.
DATA_ROOT = Path(os.getenv('XCLAWER_DATA_DIR', str(PROJECT_ROOT)))
DATA_ROOT.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = DATA_ROOT / "tweets.db"
DATABASE_CHECK_SAME_THREAD = False

# Playwright
BROWSER_USER_DATA_DIR = DATA_ROOT / "browser_state"
HEADLESS_MODE = False  # Set to True for background operation
BROWSER_TIMEOUT = 30000  # milliseconds

# X.com Collection Settings
X_COM_URL = "https://x.com/home"
COLLECTION_INTERVAL_MINUTES = 60  # Run scraper every X minutes
SCROLL_PAUSE_TIME = 2  # seconds between scrolls
MAX_SCROLL_ATTEMPTS = 5  # Maximum number of scroll attempts per session
TWEET_EXTRACTION_TIMEOUT = 5000  # milliseconds

# Logging
LOG_DIR = DATA_ROOT / "logs"
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
SCREENSHOTS_DIR = DATA_ROOT / "debug_screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# News Radar Settings (RSS + X tweets -> DeepSeek scoring -> WeChat push)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# WeChat push: "" (disabled), "serverchan", or "pushplus"
PUSH_PROVIDER = os.getenv("PUSH_PROVIDER", "")
PUSH_TOKEN = os.getenv("PUSH_TOKEN", "")

# Comma-separated RSS feed URLs
RSS_FEEDS = [u.strip() for u in os.getenv("RSS_FEEDS", "").split(",") if u.strip()]

NEWS_RSS_MAX_PER_FEED = 10        # Max items taken per RSS feed per cycle
NEWS_MAX_ITEMS_PER_CYCLE = 30    # Global cap (RSS + X) before scoring
NEWS_X_LOOKBACK_HOURS = 24       # X candidates window (by collected_at)
NEWS_X_MIN_LIKES = 100           # Min like_count for X candidates
NEWS_X_MAX_ITEMS = 15            # Max X candidates per cycle
NEWS_SCORE_THRESHOLD = 70        # Only push items scoring >= this
NEWS_STORE_THRESHOLD = 70        # Items below this are filtered (kept=0)
NEWS_TIMELINE_THRESHOLD = 80     # Only extremely important items on the timeline
NEWS_TIMELINE_TWEETS_PER_DAY = 5 # Max high-scored X tweets shown per day on the timeline
NEWS_PUSH_TOP_N = 5              # Max items per digest push
NEWS_SCHEDULE_ENABLED = True     # Register news job in scheduler_module
NEWS_CYCLE_INTERVAL_MINUTES = 60 # News cycle frequency in scheduler
NEWS_HTTP_TIMEOUT = 15           # HTTP timeout (seconds) for RSS/API calls

# AI filter for collected tweets: discard unimportant ones before storing
AI_FILTER_ENABLED = os.getenv("AI_FILTER_ENABLED", "1") == "1"
AI_FILTER_MAX_TWEETS = 50        # Max tweets judged per collection cycle

# AI Chinese summaries for English tweets
AI_SUMMARY_ENABLED = os.getenv("AI_SUMMARY_ENABLED", "1") == "1"
AI_SUMMARY_MAX_TWEETS = 50       # Max tweets summarized per batch

# AI scoring of tweets: hide low-value ones from dashboard (kept=0)
TWEET_STORE_THRESHOLD = 60       # Tweets scoring below this are hidden
TWEET_SCORE_BATCH_SIZE = 50      # Tweets scored per API batch
