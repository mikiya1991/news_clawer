"""
News pipeline orchestrator
Runs one full news cycle: fetch -> dedup -> score -> store -> push.
Synchronous (uses requests), callable from the scheduler thread and CLI.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import config
from database import get_database, close_database
from news_db import get_news_database, close_news_database
from news_fetcher import fetch_rss_items, fetch_x_candidates
from news_scorer import score_items
from news_pusher import push_digest

logger = logging.getLogger(__name__)


def run_news_cycle(score_threshold: int = None, top_n: int = None,
                   push: bool = True) -> Dict[str, Any]:
    """
    Run a single news collection + scoring + push cycle

    Args:
        score_threshold: Override config.NEWS_SCORE_THRESHOLD
        top_n: Override config.NEWS_PUSH_TOP_N
        push: If False, store scores but skip the WeChat push

    Returns:
        Summary dict: {fetched, new_items, scored, skipped, pushed_count,
                       pushed_titles, error}
    """
    logger.info("=" * 80)
    logger.info(f"Starting news cycle at {datetime.now().isoformat()}")
    logger.info("=" * 80)

    result: Dict[str, Any] = {
        'fetched': 0,
        'new_items': 0,
        'scored': 0,
        'skipped': 0,
        'pushed_count': 0,
        'pushed_titles': [],
        'error': None,
    }

    news_db = None

    try:
        news_db = get_news_database()

        # 1. Fetch candidates from both sources
        rss_items = fetch_rss_items(config.RSS_FEEDS)
        x_items = fetch_x_candidates()

        all_items = (rss_items + x_items)[:config.NEWS_MAX_ITEMS_PER_CYCLE]
        result['fetched'] = len(all_items)
        logger.info(f"Fetched {len(rss_items)} RSS + {len(x_items)} X items, "
                    f"{result['fetched']} after cap")

        if not all_items:
            logger.info("No candidates fetched, cycle complete")
            return result

        # 2. Dedup against existing urls
        existing = news_db.existing_urls([item['url'] for item in all_items])
        new_items = [item for item in all_items if item['url'] not in existing]
        result['skipped'] = len(all_items) - len(new_items)
        logger.info(f"New items after dedup: {len(new_items)} "
                    f"({result['skipped']} already known)")

        if not new_items:
            logger.info("All fetched items already in database, cycle complete")
            return result

        # 3. Score via DeepSeek
        scored = score_items(new_items)
        if scored is None:
            result['error'] = 'scoring failed (see logs)'
            logger.error("Scoring failed, nothing stored this cycle")
            return result

        # 4. Merge and store successfully scored items (below threshold -> kept=0)
        rows = []
        filtered_count = 0
        for item, s in zip(new_items, scored):
            if s is None:
                result['skipped'] += 1
                continue
            kept = 1 if s['score'] >= config.NEWS_STORE_THRESHOLD else 0
            if not kept:
                filtered_count += 1
            rows.append({
                'source': item['source'],
                'source_name': item.get('source_name', ''),
                'title': item.get('title', ''),
                'content': item.get('content', ''),
                'url': item['url'],
                'author': item.get('author', ''),
                'published_at': item.get('published_at'),
                'score': s['score'],
                'summary': s['summary'],
                'reasons': s['reasons'],
                'kept': kept,
            })

        result['scored'] = len(rows)
        result['new_items'] = news_db.insert_items(rows)
        logger.info(f"Stored {result['new_items']} scored items "
                    f"({filtered_count} below {config.NEWS_STORE_THRESHOLD} "
                    f"filtered)")

        # 5. Push digest of top-scored items
        if push and rows:
            threshold = score_threshold if score_threshold is not None \
                else config.NEWS_SCORE_THRESHOLD
            n = top_n if top_n is not None else config.NEWS_PUSH_TOP_N

            top = sorted(rows, key=lambda r: r['score'], reverse=True)
            top = [r for r in top if r['score'] >= threshold][:n]

            if top:
                if push_digest(top, scanned_count=len(new_items)):
                    news_db.mark_pushed([r['url'] for r in top])
                    result['pushed_count'] = len(top)
                    result['pushed_titles'] = [r['title'][:40] for r in top]
            else:
                logger.info(f"No items above threshold ({threshold}), "
                            f"skipping push")

        logger.info("=" * 80)
        logger.info(f"News cycle completed: fetched={result['fetched']}, "
                    f"new={result['new_items']}, scored={result['scored']}, "
                    f"pushed={result['pushed_count']}")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"News cycle failed with error: {e}", exc_info=True)
        result['error'] = str(e)
        return result

    finally:
        close_news_database()
        close_database()
