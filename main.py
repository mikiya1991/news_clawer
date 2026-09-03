"""
Main orchestrator for X.com Tweet Scraper
Handles collection cycles, logging, and error management
"""
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import config
from logger import configure_logging
from database import get_database, close_database
from browser import create_browser_manager
from scraper import TweetScraper
from tweet_filter import filter_tweets, score_tweets
from tweet_summarizer import summarize_tweets, is_english_text


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
            # Filter to tweets not yet in database
            to_insert = [t for t in tweets if not db.tweet_exists(t['id'])]

            # Exclude tweets previously discarded by the AI filter
            if to_insert:
                discarded_ids = db.get_discarded_ids([t['id'] for t in to_insert])
                to_insert = [t for t in to_insert if t['id'] not in discarded_ids]

            # AI filter: judge whether each new tweet is worth collecting
            if config.AI_FILTER_ENABLED and to_insert:
                candidates = to_insert[:config.AI_FILTER_MAX_TWEETS]
                remainder = to_insert[config.AI_FILTER_MAX_TWEETS:]
                if remainder:
                    logger.warning(f"AI filter: {len(to_insert)} new tweets exceed "
                                   f"cap ({config.AI_FILTER_MAX_TWEETS}), "
                                   f"{len(remainder)} stored unfiltered")
                result = filter_tweets(candidates)
                if result is not None:
                    kept_ids, discarded = result
                    db.log_discarded(discarded)
                    to_insert = [t for t in candidates if t['id'] in kept_ids] + remainder
                    logger.info(f"AI filter: kept {len(to_insert)}, "
                                f"discarded {len(discarded)}")
                else:
                    logger.warning("AI filter failed, storing all candidates "
                                   "(fail-open)")

            # AI summaries for English tweets (one-line Chinese annotation)
            if config.AI_SUMMARY_ENABLED and to_insert:
                english_tweets = [t for t in to_insert
                                  if is_english_text(t.get('text', ''))]
                if english_tweets:
                    summary_targets = english_tweets[:config.AI_SUMMARY_MAX_TWEETS]
                    summaries = summarize_tweets(summary_targets)
                    if summaries:
                        for t in to_insert:
                            if t['id'] in summaries:
                                t['ai_summary'] = summaries[t['id']]
                        logger.info(f"AI summaries: annotated {len(summaries)} "
                                    f"English tweets")
                    else:
                        logger.warning("AI summarization failed, storing "
                                       "without summaries")

            # Insert into database
            logger.info(f"Inserting {len(to_insert)} tweets into database...")
            inserted_count = db.insert_tweets_batch(to_insert)

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


async def login_flow_auto(timeout_seconds: int = 300) -> bool:
    """
    Non-interactive login flow (web-triggered): opens a visible browser and
    polls login status until the user completes login on the page, then saves
    browser state. Unlike manual_login(), no terminal input is required.
    """
    logger.info("=" * 80)
    logger.info("Starting auto-detect login flow")
    logger.info("=" * 80)

    browser_manager = None

    try:
        logger.info("Launching browser for login...")
        browser_manager = await create_browser_manager(headless=False)

        # Navigate to X.com
        await browser_manager.navigate_to("https://x.com/home")

        logger.info(f"Browser is open. Waiting up to {timeout_seconds}s "
                    f"for login to complete...")

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if await browser_manager.check_login_status():
                logger.info("✓ Login successful! Browser state has been saved.")
                return True
            await asyncio.sleep(5)

        logger.error(f"✗ Login timed out after {timeout_seconds}s")
        await browser_manager.take_screenshot("login_timeout.png")
        return False

    except Exception as e:
        logger.error(f"Error during auto login flow: {e}", exc_info=True)
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


def backfill_summaries(limit: int = 500):
    """
    Generate AI summaries for existing English tweets that lack one

    Args:
        limit: Max number of English tweets to summarize

    Returns:
        Number of tweets annotated
    """
    db = get_database()
    try:
        # Over-fetch: only ~a fraction of tweets are English
        candidates = db.get_tweets_without_summary(limit=max(limit * 2, 200))
        english = [t for t in candidates if is_english_text(t.get('text', ''))][:limit]
        logger.info(f"Backfill: {len(english)} English tweets to summarize "
                    f"(from {len(candidates)} candidates)")

        total_updated = 0
        for i in range(0, len(english), config.AI_SUMMARY_MAX_TWEETS):
            batch = english[i:i + config.AI_SUMMARY_MAX_TWEETS]
            summaries = summarize_tweets(batch)
            if not summaries:
                logger.error("Backfill aborted: summarization failed")
                break
            for t in batch:
                if t['id'] in summaries and db.update_summary(t['id'], summaries[t['id']]):
                    total_updated += 1
            logger.info(f"Backfill progress: "
                        f"{min(i + config.AI_SUMMARY_MAX_TWEETS, len(english))}/"
                        f"{len(english)}")

        logger.info(f"Backfill done: {total_updated} summaries added")
        return total_updated
    finally:
        close_database()


def score_history(limit: int = None):
    """
    AI-score historical tweets and hide low-value ones (kept=0)

    Args:
        limit: Max number of tweets to score (None or negative = all unscored)

    Returns:
        (scored_count, hidden_count)
    """
    if limit is not None and limit < 0:
        limit = None
    db = get_database()
    total_scored = 0
    total_hidden = 0
    total_unscorable = 0
    batch = config.TWEET_SCORE_BATCH_SIZE

    try:
        # No offset pagination: scored rows leave the "ai_score IS NULL"
        # result set, so each iteration simply takes the first unscored batch
        while True:
            candidates = db.get_tweets_without_score(limit=batch)
            if not candidates:
                break

            results = score_tweets(candidates)
            if results is None:
                logger.error("History scoring aborted: scoring failed")
                break

            for t, r in zip(candidates, results):
                if r is None:
                    # Unscorable (e.g. content policy) - mark -1, keep visible
                    db.update_score(t['id'], -1, 1)
                    total_unscorable += 1
                    continue
                score = r['score']
                kept = 1 if score >= config.TWEET_STORE_THRESHOLD else 0
                if not kept:
                    total_hidden += 1
                # Only fill summary when the tweet has none yet
                summary = r.get('summary', '') if not t.get('ai_summary') else None
                db.update_score(t['id'], score, kept, summary)
                total_scored += 1

            logger.info(f"History scoring: {total_scored} scored, "
                        f"{total_hidden} hidden, {total_unscorable} unscorable "
                        f"(threshold {config.TWEET_STORE_THRESHOLD})")

            if limit and total_scored >= limit:
                break

        logger.info(f"History scoring done: {total_scored} scored, "
                    f"{total_hidden} hidden, {total_unscorable} unscorable")
        return total_scored, total_hidden
    finally:
        close_database()


def rescore_news(limit: int = 50) -> Dict[str, Any]:
    """
    Re-score the most recent news items and refresh their scores.

    Args:
        limit: Max number of recent kept items to re-score

    Returns:
        {scored, hidden, error}
    """
    from news_db import get_news_database, close_news_database
    from news_scorer import score_items

    result = {'scored': 0, 'hidden': 0, 'error': None}
    news_db = None

    try:
        news_db = get_news_database()
        items = news_db.get_items(limit=limit, sort='time', order='desc')
        if not items:
            logger.info("Rescore news: no items to score")
            return result

        logger.info(f"Rescoring {len(items)} recent news items")
        scored = score_items(items)
        if scored is None:
            result['error'] = 'scoring failed (see logs)'
            logger.error("Rescore news aborted: scoring failed")
            return result

        for item, s in zip(items, scored):
            if s is None:
                continue
            kept = 1 if s['score'] >= config.NEWS_STORE_THRESHOLD else 0
            if news_db.update_score(item['id'], s['score'], s['summary'],
                                    s['reasons'], kept):
                result['scored'] += 1
                if not kept:
                    result['hidden'] += 1

        logger.info(f"Rescore news done: {result['scored']} updated, "
                    f"{result['hidden']} hidden "
                    f"(threshold {config.NEWS_STORE_THRESHOLD})")
        return result
    except Exception as e:
        logger.error(f"Rescore news failed: {e}", exc_info=True)
        result['error'] = str(e)
        return result
    finally:
        close_news_database()


def main():
    """Main entry point"""
    configure_logging(config.LOG_DIR, config.LOG_LEVEL, config.LOG_RETENTION_DAYS)

    import argparse

    parser = argparse.ArgumentParser(description='X.com Tweet Scraper')
    parser.add_argument('--login', action='store_true', help='Start manual login flow')
    parser.add_argument('--collect', action='store_true', help='Run collection cycle')
    parser.add_argument('--collect-news', action='store_true', help='Run news cycle (RSS + X -> DeepSeek scoring -> WeChat push)')
    parser.add_argument('--backfill-summaries', nargs='?', const=500, type=int, metavar='N',
                        help='Backfill AI summaries for recent English tweets (default 500)')
    parser.add_argument('--score-history', nargs='?', const=-1, type=int, metavar='N',
                        help='AI-score historical tweets and hide those below threshold (no N = all unscored)')
    parser.add_argument('--stats', action='store_true', help='Print database statistics')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--iterations', type=int, help='Number of scroll iterations')

    args = parser.parse_args()

    # Default action: run collection if no args
    if not any([args.login, args.stats, args.collect_news,
                args.backfill_summaries is not None,
                args.score_history is not None]):
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

        elif args.collect_news:
            from news_pipeline import run_news_cycle
            result = run_news_cycle()
            if result.get('error'):
                logger.error(f"News cycle error: {result['error']}")
                sys.exit(1)
            print(f"\nNews cycle summary: fetched={result['fetched']}, "
                  f"new={result['new_items']}, scored={result['scored']}, "
                  f"pushed={result['pushed_count']}")
            if result['pushed_titles']:
                print("Pushed titles:")
                for title in result['pushed_titles']:
                    print(f"  - {title}")
            sys.exit(0)

        elif args.backfill_summaries is not None:
            count = backfill_summaries(args.backfill_summaries)
            print(f"\nBackfilled AI summaries: {count} tweets")
            sys.exit(0)

        elif args.score_history is not None:
            scored, hidden = score_history(args.score_history)
            print(f"\nHistory scoring: {scored} scored, {hidden} hidden "
                  f"(below {config.TWEET_STORE_THRESHOLD})")
            sys.exit(0)

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
