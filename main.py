"""
Main orchestrator for X.com Tweet Scraper
Handles collection cycles, logging, and error management
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from logger import configure_logging
from database import get_database, close_database
from browser import create_browser_manager
from scraper import TweetScraper


logger = logging.getLogger(__name__)


async def collection_cycle(headless: bool = False, max_iterations: int = None) -> bool:
    """
    Run a single collection cycle
    
    Args:
        headless: Run browser in headless mode
        max_iterations: Maximum scroll iterations
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("=" * 80)
    logger.info(f"Starting collection cycle at {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    browser_manager = None
    db = None
    
    try:
        # Initialize database
        db = get_database()
        
        # Initialize browser
        logger.info("Initializing browser...")
        browser_manager = await create_browser_manager(headless=headless)
        
        # Check login status
        logger.info("Checking login status...")
        is_logged_in = await browser_manager.check_login_status()
        
        if not is_logged_in:
            logger.error("Not logged into X.com. Please run in non-headless mode and login manually.")
            logger.error("After login, the browser state will be saved and used for future runs.")
            
            # Take screenshot for debugging
            await browser_manager.take_screenshot("login_required.png")
            
            db.log_collection_run(
                collection_type='feed',
                tweet_count=0,
                error_message='Not logged in to X.com',
                status='error'
            )
            return False
        
        logger.info("✓ Successfully logged in to X.com")
        
        # Initialize scraper
        scraper = TweetScraper(browser_manager)
        
        # Scrape tweets
        logger.info("Starting tweet collection...")
        tweets = await scraper.scrape_feed(scroll_iterations=max_iterations)
        
        logger.info(f"Collected {len(tweets)} new tweets")
        
        if tweets:
            # Insert into database
            logger.info("Inserting tweets into database...")
            inserted_count = db.insert_tweets_batch(tweets)
            
            logger.info(f"Successfully inserted {inserted_count} tweets into database")
            
            # Log collection metadata
            db.log_collection_run(
                collection_type='feed',
                tweet_count=inserted_count,
                status='success'
            )
            
            # Print sample tweets
            logger.info("Sample of collected tweets:")
            for tweet in tweets[:3]:
                logger.info(f"  - @{tweet.get('username', 'unknown')}: {tweet.get('text', '')[:80]}...")
        else:
            logger.warning("No new tweets collected")
            db.log_collection_run(
                collection_type='feed',
                tweet_count=0,
                error_message='No tweets found',
                status='partial'
            )
        
        # Print statistics
        total_tweets = db.get_tweet_count()
        logger.info(f"Total tweets in database: {total_tweets}")
        
        logger.info("=" * 80)
        logger.info(f"Collection cycle completed successfully at {datetime.now().isoformat()}")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"Collection cycle failed with error: {e}", exc_info=True)
        
        if db:
            db.log_collection_run(
                collection_type='feed',
                tweet_count=0,
                error_message=str(e),
                status='error'
            )
        
        if browser_manager:
            try:
                await browser_manager.take_screenshot("error.png")
            except:
                pass
        
        return False
    
    finally:
        # Cleanup
        if browser_manager:
            try:
                await browser_manager.close()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
        
        if db:
            try:
                close_database()
                logger.info("Database closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")


async def manual_login():
    """
    Manual login flow - start browser for user to login
    Browser state is automatically saved
    """
    logger.info("=" * 80)
    logger.info("Starting manual login mode")
    logger.info("=" * 80)
    
    browser_manager = None
    
    try:
        # Initialize browser (non-headless so user can see and interact)
        logger.info("Launching browser for login...")
        browser_manager = await create_browser_manager(headless=False)
        
        # Navigate to X.com
        await browser_manager.navigate_to("https://x.com/home")
        
        logger.info("Browser is open. Please login to X.com.")
        logger.info("After successful login, press Enter in this terminal to continue...")
        logger.info("")
        
        # Wait for user input
        input("Press Enter after you've logged in: ")
        
        # Check if logged in
        if await browser_manager.check_login_status():
            logger.info("✓ Login successful! Browser state has been saved.")
            logger.info("You can now run the scraper in headless mode.")
            return True
        else:
            logger.error("✗ Login verification failed. Please try again.")
            return False
            
    except Exception as e:
        logger.error(f"Error during manual login: {e}", exc_info=True)
        return False
    
    finally:
        if browser_manager:
            try:
                await browser_manager.close()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")


def print_stats():
    """Print database statistics"""
    try:
        db = get_database()
        total = db.get_tweet_count()
        recent = db.get_recent_tweets(hours=24)
        
        print("\n" + "=" * 80)
        print("TWEET DATABASE STATISTICS")
        print("=" * 80)
        print(f"Total tweets: {total}")
        print(f"Tweets in last 24 hours: {len(recent)}")
        
        if recent:
            print("\nRecent tweets:")
            for tweet in recent[:5]:
                print(f"  - @{tweet['username']}: {tweet['text'][:70]}...")
        
        print("=" * 80 + "\n")
        
        close_database()
        
    except Exception as e:
        logger.error(f"Error printing stats: {e}")


def main():
    """Main entry point"""
    configure_logging(config.LOG_DIR, config.LOG_LEVEL, config.LOG_RETENTION_DAYS)

    import argparse
    
    parser = argparse.ArgumentParser(description='X.com Tweet Scraper')
    parser.add_argument('--login', action='store_true', help='Start manual login flow')
    parser.add_argument('--collect', action='store_true', help='Run collection cycle')
    parser.add_argument('--stats', action='store_true', help='Print database statistics')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--iterations', type=int, help='Number of scroll iterations')
    
    args = parser.parse_args()
    
    # Default action: run collection if no args
    if not any([args.login, args.stats]):
        args.collect = True
    
    try:
        if args.login:
            success = asyncio.run(manual_login())
            sys.exit(0 if success else 1)
        
        elif args.collect:
            success = asyncio.run(collection_cycle(
                headless=args.headless,
                max_iterations=args.iterations
            ))
            sys.exit(0 if success else 1)
        
        elif args.stats:
            print_stats()
            sys.exit(0)
    
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
