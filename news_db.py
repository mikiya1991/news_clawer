"""
News database module for SQLite operations
Stores scored news items (RSS + X) in the same tweets.db file
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import config

logger = logging.getLogger(__name__)


class NewsDatabase:
    """SQLite database wrapper for news item storage"""

    def __init__(self, db_path: str = None):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or str(config.DATABASE_PATH)
        self.conn = None
        self.init_database()

    def connect(self):
        """Establish database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=config.DATABASE_CHECK_SAME_THREAD
            )
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to news database: {self.db_path}")

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("News database connection closed")

    def init_database(self):
        """Create tables if they don't exist"""
        self.connect()
        cursor = self.conn.cursor()

        # News items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL CHECK (source IN ('rss', 'x')),
                source_name TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                author TEXT DEFAULT '',
                published_at TIMESTAMP,
                score INTEGER DEFAULT 0,
                summary TEXT DEFAULT '',
                reasons TEXT DEFAULT '',
                pushed INTEGER DEFAULT 0,
                kept INTEGER DEFAULT 1,
                scored_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migration: add kept column to older databases
        cursor.execute("PRAGMA table_info(news_items)")
        columns = {row['name'] for row in cursor.fetchall()}
        if 'kept' not in columns:
            cursor.execute("ALTER TABLE news_items ADD COLUMN kept INTEGER DEFAULT 1")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_news_items_score
            ON news_items (score DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_news_items_source
            ON news_items (source, created_at)
        ''')

        self.conn.commit()
        logger.info("News database tables initialized")

    def existing_urls(self, urls: List[str]) -> set:
        """
        Return the subset of urls already present in news_items

        Args:
            urls: Candidate urls to check

        Returns:
            Set of urls that already exist
        """
        if not urls:
            return set()
        self.connect()
        cursor = self.conn.cursor()
        placeholders = ','.join('?' for _ in urls)
        cursor.execute(
            f'SELECT url FROM news_items WHERE url IN ({placeholders})',
            urls
        )
        return {row['url'] for row in cursor.fetchall()}

    def insert_items(self, items: List[Dict[str, Any]]) -> int:
        """
        Insert news items, skipping duplicates by url

        Args:
            items: List of item dicts with keys: source, source_name, title,
                   content, url, author, published_at, score, summary, reasons

        Returns:
            Number of items successfully inserted
        """
        if not items:
            return 0
        self.connect()
        cursor = self.conn.cursor()

        inserted_count = 0
        for item in items:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO news_items
                    (source, source_name, title, content, url, author,
                     published_at, score, summary, reasons, kept, scored_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['source'],
                    item.get('source_name', ''),
                    item.get('title', ''),
                    item.get('content', ''),
                    item['url'],
                    item.get('author', ''),
                    item.get('published_at'),
                    int(item.get('score', 0)),
                    item.get('summary', ''),
                    item.get('reasons', ''),
                    int(item.get('kept', 1)),
                    datetime.now() if item.get('score') else None
                ))
                if cursor.rowcount > 0:
                    inserted_count += 1
            except sqlite3.IntegrityError as e:
                logger.warning(f"Integrity error (possible duplicate): {e}")
            except Exception as e:
                logger.error(f"Error inserting news item: {e}")

        self.conn.commit()
        logger.info(f"News batch insert: {inserted_count}/{len(items)} items inserted")
        return inserted_count

    def mark_pushed(self, urls: List[str]) -> int:
        """
        Mark items as pushed (included in a past digest)

        Args:
            urls: Item urls to mark

        Returns:
            Number of rows updated
        """
        if not urls:
            return 0
        self.connect()
        cursor = self.conn.cursor()
        placeholders = ','.join('?' for _ in urls)
        cursor.execute(
            f'UPDATE news_items SET pushed = 1 WHERE url IN ({placeholders})',
            urls
        )
        self.conn.commit()
        return cursor.rowcount

    def get_items(self, limit: int = 100, offset: int = 0,
                  sort: str = 'score', order: str = 'desc',
                  source: str = None, min_score: int = None,
                  pushed: int = None,
                  include_discarded: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieve news items with filtering and pagination

        Args:
            limit: Max items to return
            offset: Items to skip
            sort: 'score' or 'time'
            order: 'asc' or 'desc'
            source: 'rss' or 'x' filter
            min_score: Minimum score filter
            pushed: 0 or 1 filter
            include_discarded: Include items filtered out by kept=0

        Returns:
            List of news item dictionaries
        """
        self.connect()
        cursor = self.conn.cursor()

        sort_column = {
            'score': 'score',
            'time': 'created_at'
        }.get(sort, 'score')
        order_dir = 'DESC' if order == 'desc' else 'ASC'

        query = f"SELECT * FROM news_items WHERE 1=1"
        params = []

        if not include_discarded:
            query += " AND kept = 1"
        if source:
            query += " AND source = ?"
            params.append(source)
        if min_score is not None:
            query += " AND score >= ?"
            params.append(min_score)
        if pushed is not None:
            query += " AND pushed = ?"
            params.append(pushed)

        query += f" ORDER BY {sort_column} {order_dir}, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        items = [dict(row) for row in cursor.fetchall()]
        return items

    def get_count(self, source: str = None, min_score: int = None,
                  pushed: int = None,
                  include_discarded: bool = False) -> int:
        """Get count of news items matching filters"""
        self.connect()
        cursor = self.conn.cursor()

        query = "SELECT COUNT(*) FROM news_items WHERE 1=1"
        params = []
        if not include_discarded:
            query += " AND kept = 1"
        if source:
            query += " AND source = ?"
            params.append(source)
        if min_score is not None:
            query += " AND score >= ?"
            params.append(min_score)
        if pushed is not None:
            query += " AND pushed = ?"
            params.append(pushed)

        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def update_score(self, item_id: int, score: int, summary: str,
                     reasons: str, kept: int) -> bool:
        """
        Refresh an item's score, summary, reasons, kept flag and scored_at

        Args:
            item_id: Row id of the news item
            score: New score 0-100
            summary: New one-line summary
            reasons: New reasons JSON string
            kept: 1 to keep visible, 0 to filter out

        Returns:
            True if the row was updated
        """
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE news_items
            SET score = ?, summary = ?, reasons = ?, kept = ?, scored_at = ?
            WHERE id = ?
        ''', (int(score), summary, reasons, int(kept),
              datetime.now().isoformat(), int(item_id)))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_timeline_items(self, min_score: int = 0,
                           limit: int = 300) -> List[Dict[str, Any]]:
        """
        Get kept items for the timeline, ordered by publish date desc

        Args:
            min_score: Minimum score filter
            limit: Max items to return

        Returns:
            List of news item dictionaries
        """
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM news_items
            WHERE kept = 1 AND score >= ?
            ORDER BY COALESCE(published_at, created_at) DESC
            LIMIT ?
        ''', (min_score, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics for the dashboard (kept items only)"""
        self.connect()
        cursor = self.conn.cursor()

        stats = {'total': 0, 'scored': 0, 'avg_score': 0.0,
                 'rss_count': 0, 'x_count': 0, 'pushed_count': 0,
                 'last_scored_at': None}

        cursor.execute('SELECT COUNT(*) FROM news_items WHERE kept = 1')
        stats['total'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM news_items WHERE kept = 1 AND score > 0')
        stats['scored'] = cursor.fetchone()[0]

        cursor.execute('SELECT AVG(score) FROM news_items WHERE kept = 1 AND score > 0')
        avg = cursor.fetchone()[0]
        stats['avg_score'] = round(avg, 1) if avg is not None else 0.0

        cursor.execute("SELECT COUNT(*) FROM news_items WHERE kept = 1 AND source = 'rss'")
        stats['rss_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM news_items WHERE kept = 1 AND source = 'x'")
        stats['x_count'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM news_items WHERE kept = 1 AND pushed = 1')
        stats['pushed_count'] = cursor.fetchone()[0]

        cursor.execute('SELECT MAX(scored_at) FROM news_items WHERE kept = 1')
        stats['last_scored_at'] = cursor.fetchone()[0]

        return stats


# Global database instance
_news_db = None


def get_news_database() -> NewsDatabase:
    """Get or create global news database instance"""
    global _news_db
    if _news_db is None:
        _news_db = NewsDatabase()
    return _news_db


def close_news_database():
    """Close global news database instance"""
    global _news_db
    if _news_db:
        _news_db.disconnect()
        _news_db = None
