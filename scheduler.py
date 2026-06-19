"""
Tweet Scraper Scheduler
Uses Python schedule library for periodic tweet collection.

Usage:
    python3 scheduler.py              # Run in foreground
    nohup python3 scheduler.py &      # Run in background
"""
import asyncio
import logging
import schedule
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import config
from logger import configure_logging
from main import collection_cycle

logger = logging.getLogger(__name__)


def collect_tweets():
    """Run the tweet collection script"""
    logger.info("Starting tweet collection...")
    try:
        success = asyncio.run(collection_cycle(headless=True))
        if success:
            logger.info("Collection completed successfully")
        else:
            logger.warning("Collection completed with errors")
    except Exception:
        logger.exception("Collection failed with an unhandled exception")


def main():
    configure_logging(config.LOG_DIR, config.LOG_LEVEL, config.LOG_RETENTION_DAYS)

    # Schedule configuration - modify as needed
    # Examples:
    # schedule.every(10).minutes.do(collect_tweets)    # Every 10 minutes
    # schedule.every().hour.do(collect_tweets)         # Every hour
    # schedule.every(6).hours.do(collect_tweets)       # Every 6 hours
    # schedule.every().day.at("09:00").do(collect_tweets) # Daily at 9:00 AM

    # Default: every hour
    schedule.every().hour.do(collect_tweets)

    logger.info("=" * 60)
    logger.info("Tweet Scraper Scheduler Started")
    logger.info("=" * 60)
    logger.info(
        f"Schedule: {schedule.default_scheduler.jobs[0]}"
        if schedule.default_scheduler.jobs
        else "No jobs scheduled"
    )
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
