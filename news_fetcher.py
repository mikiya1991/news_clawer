"""
News fetcher module
Fetches candidate news items from RSS feeds and from tweets already in tweets.db
Both sources are normalized to the same item dict shape.
"""
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import feedparser
import requests

import config
from database import get_database

logger = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


def fetch_rss_items(feeds: List[str], max_per_feed: int = None) -> List[Dict[str, Any]]:
    """
    Fetch items from RSS feeds

    Args:
        feeds: List of feed URLs
        max_per_feed: Max items taken per feed (default from config)

    Returns:
        List of normalized item dicts
    """
    max_per_feed = max_per_feed or config.NEWS_RSS_MAX_PER_FEED
    items: List[Dict[str, Any]] = []

    for feed_url in feeds:
        try:
            response = requests.get(
                feed_url,
                timeout=config.NEWS_HTTP_TIMEOUT,
                headers={'User-Agent': USER_AGENT}
            )
            response.raise_for_status()
            parsed = feedparser.parse(response.content)

            feed_title = parsed.feed.get('title', feed_url)
            feed_items = parsed.entries[:max_per_feed]
            logger.info(f"RSS feed '{feed_title}': {len(feed_items)} entries")

            for entry in feed_items:
                title = entry.get('title', '').strip()
                content = entry.get('summary', entry.get('description', '')).strip()
                link = entry.get('link', '').strip()
                published = None
                if entry.get('published_parsed'):
                    published = datetime(*entry.published_parsed[:6]).isoformat()
                elif entry.get('updated_parsed'):
                    published = datetime(*entry.updated_parsed[:6]).isoformat()

                if not title and not content:
                    continue

                # Fallback dedup key when link is missing
                url = link or f"sha1:{_sha1(title + str(published))}"

                items.append({
                    'source': 'rss',
                    'source_name': feed_title,
                    'title': title or content[:60],
                    'content': content or title,
                    'url': url,
                    'author': entry.get('author', ''),
                    'published_at': published,
                })

        except Exception as e:
            logger.warning(f"Failed to fetch RSS feed {feed_url}: {e}")

    return items


def fetch_x_candidates(db=None, lookback_hours: int = None,
                       min_likes: int = None, max_items: int = None) -> List[Dict[str, Any]]:
    """
    Select candidate tweets from tweets.db for news scoring

    Args:
        db: TweetDatabase instance (uses singleton if None)
        lookback_hours: Lookback window by collected_at
        min_likes: Minimum like_count
        max_items: Max candidates returned

    Returns:
        List of normalized item dicts, ranked by like_count desc
    """
    lookback_hours = lookback_hours or config.NEWS_X_LOOKBACK_HOURS
    min_likes = min_likes if min_likes is not None else config.NEWS_X_MIN_LIKES
    max_items = max_items or config.NEWS_X_MAX_ITEMS

    db = db or get_database()
    recent_tweets = db.get_recent_tweets(hours=lookback_hours)

    candidates = [
        t for t in recent_tweets
        if int(t.get('like_count', 0)) >= min_likes
        and len(str(t.get('text', '')).strip()) >= 20
        and str(t.get('url', '')).strip()
    ]

    candidates.sort(key=lambda t: int(t.get('like_count', 0)), reverse=True)
    candidates = candidates[:max_items]

    items = []
    for t in candidates:
        text = str(t['text']).strip()
        items.append({
            'source': 'x',
            'source_name': '@' + str(t['username']),
            'title': text[:60],
            'content': text,
            'url': str(t['url']),
            'author': str(t['username']),
            'published_at': None,
            'like_count': int(t.get('like_count', 0)),
        })

    if candidates:
        logger.info(f"X candidates: {len(candidates)} tweets (>= {min_likes} likes, "
                    f"last {lookback_hours}h)")
    else:
        logger.info(f"X candidates: 0 (no tweets >= {min_likes} likes in last "
                    f"{lookback_hours}h)")

    return items
