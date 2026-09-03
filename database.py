"""
Database module for SQLite operations
Handles tweet storage, retrieval, and duplicate detection
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import config

logger = logging.getLogger(__name__)


class TweetDatabase:
    """SQLite database wrapper for tweet storage"""
    
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
            logger.info(f"Connected to database: {self.db_path}")
    
    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")
    
    def init_database(self):
        """Create tables if they don't exist"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Tweets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tweets (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                text TEXT NOT NULL,
                like_count INTEGER DEFAULT 0,
                retweet_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                url TEXT UNIQUE,
                ai_summary TEXT DEFAULT '',
                ai_score INTEGER,
                kept INTEGER DEFAULT 1,
                UNIQUE(id)
            )
        ''')

        # Migration: add newer columns to older databases
        cursor.execute("PRAGMA table_info(tweets)")
        columns = {row['name'] for row in cursor.fetchall()}
        if 'ai_summary' not in columns:
            cursor.execute("ALTER TABLE tweets ADD COLUMN ai_summary TEXT DEFAULT ''")
        if 'ai_score' not in columns:
            cursor.execute("ALTER TABLE tweets ADD COLUMN ai_score INTEGER")
        if 'kept' not in columns:
            cursor.execute("ALTER TABLE tweets ADD COLUMN kept INTEGER DEFAULT 1")
        
        # Metadata table for tracking collection runs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_type TEXT NOT NULL,
                last_collection_time TIMESTAMP,
                tweet_count_collected INTEGER DEFAULT 0,
                error_message TEXT,
                status TEXT DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Log of tweets discarded by the AI filter (judged once, never re-judged)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tweet_filter_log (
                id TEXT PRIMARY KEY,
                reason TEXT DEFAULT '',
                filtered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        logger.info("Database tables initialized")
    
    def tweet_exists(self, tweet_id: str) -> bool:
        """
        Check if tweet already exists in database
        
        Args:
            tweet_id: Unique identifier of tweet
            
        Returns:
            True if tweet exists, False otherwise
        """
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM tweets WHERE id = ?', (tweet_id,))
        return cursor.fetchone() is not None
    
    def insert_tweet(self, tweet_data: Dict[str, Any]) -> bool:
        """
        Insert or update a tweet in the database
        
        Args:
            tweet_data: Dictionary with keys: id, username, text, like_count, 
                       retweet_count, view_count, url
                       
        Returns:
            True if successful, False if duplicate or error
        """
        self.connect()
        cursor = self.conn.cursor()
        
        try:
            # Validate required fields
            required_fields = ['id', 'username', 'text']
            if not all(field in tweet_data for field in required_fields):
                logger.warning(f"Missing required fields: {tweet_data}")
                return False
            
            # Check for duplicates
            if self.tweet_exists(tweet_data['id']):
                logger.debug(f"Tweet already exists: {tweet_data['id']}")
                return False
            
            # Insert tweet
            cursor.execute('''
                INSERT INTO tweets
                (id, username, text, like_count, retweet_count, view_count, url, ai_summary, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tweet_data['id'],
                tweet_data.get('username', ''),
                tweet_data.get('text', ''),
                int(tweet_data.get('like_count', 0)),
                int(tweet_data.get('retweet_count', 0)),
                int(tweet_data.get('view_count', 0)),
                tweet_data.get('url', ''),
                tweet_data.get('ai_summary', ''),
                datetime.now()
            ))
            
            self.conn.commit()
            logger.debug(f"Tweet inserted: {tweet_data['id']}")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.warning(f"Integrity error (possible duplicate): {e}")
            return False
        except Exception as e:
            logger.error(f"Error inserting tweet: {e}")
            return False
    
    def insert_tweets_batch(self, tweets: List[Dict[str, Any]]) -> int:
        """
        Insert multiple tweets efficiently
        
        Args:
            tweets: List of tweet dictionaries
            
        Returns:
            Number of tweets successfully inserted
        """
        inserted_count = 0
        for tweet in tweets:
            if self.insert_tweet(tweet):
                inserted_count += 1
        
        logger.info(f"Batch insert: {inserted_count}/{len(tweets)} tweets inserted")
        return inserted_count
    
    def get_tweets(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve tweets from database
        
        Args:
            limit: Maximum number of tweets to return
            offset: Number of tweets to skip
            
        Returns:
            List of tweet dictionaries
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT * FROM tweets 
            ORDER BY collected_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        tweets = []
        for row in cursor.fetchall():
            tweets.append(dict(row))
        
        return tweets
    
    def get_tweet_count(self) -> int:
        """Get total number of tweets in database"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM tweets')
        return cursor.fetchone()[0]
    
    def get_recent_tweets(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get tweets collected in the last N hours
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of recent tweet dictionaries
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT * FROM tweets
            WHERE kept = 1 AND collected_at > datetime('now', '-' || ? || ' hours')
            ORDER BY collected_at DESC
        ''', (hours,))
        
        tweets = []
        for row in cursor.fetchall():
            tweets.append(dict(row))
        
        return tweets
    
    def get_tweets_without_score(self, limit: int = 500,
                                 offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get tweets that have not been AI-scored yet

        Args:
            limit: Max number of tweets to return
            offset: Number of tweets to skip

        Returns:
            List of tweet dictionaries ordered by collected_at desc
        """
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM tweets
            WHERE ai_score IS NULL
            ORDER BY collected_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    def update_score(self, tweet_id: str, score: int, kept: int,
                     summary: str = None) -> bool:
        """
        Set AI score and kept flag for a tweet; optionally fill summary
        only when the tweet has no summary yet

        Args:
            tweet_id: Tweet id
            score: 0-100 AI score
            kept: 1 to keep visible, 0 to hide
            summary: Chinese summary (only applied if current is empty)

        Returns:
            True if a row was updated
        """
        self.connect()
        cursor = self.conn.cursor()
        if summary:
            cursor.execute('''
                UPDATE tweets SET ai_score = ?, kept = ?,
                    ai_summary = CASE WHEN (ai_summary IS NULL OR ai_summary = '')
                        THEN ? ELSE ai_summary END
                WHERE id = ?
            ''', (int(score), int(kept), str(summary)[:200], str(tweet_id)))
        else:
            cursor.execute('''
                UPDATE tweets SET ai_score = ?, kept = ? WHERE id = ?
            ''', (int(score), int(kept), str(tweet_id)))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_tweets_without_summary(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get recent tweets that lack an AI summary

        Args:
            limit: Max number of tweets to return

        Returns:
            List of tweet dictionaries ordered by collected_at desc
        """
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM tweets
            WHERE (ai_summary IS NULL OR ai_summary = '')
            ORDER BY collected_at DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def update_summary(self, tweet_id: str, summary: str) -> bool:
        """
        Set the AI summary for a tweet

        Args:
            tweet_id: Tweet id
            summary: Chinese summary text

        Returns:
            True if a row was updated
        """
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE tweets SET ai_summary = ? WHERE id = ?
        ''', (str(summary)[:200], str(tweet_id)))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_top_tweets(self, min_score: int = 0,
                       limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get kept tweets scoring at least min_score for the timeline

        Args:
            min_score: Minimum ai_score
            limit: Max tweets to return

        Returns:
            List of tweet dictionaries ordered by score desc
        """
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM tweets
            WHERE kept = 1 AND ai_score IS NOT NULL AND ai_score >= ?
            ORDER BY ai_score DESC, collected_at DESC
            LIMIT ?
        ''', (min_score, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_discarded_ids(self, tweet_ids: List[str]) -> set:
        """
        Return the subset of tweet ids already discarded by the AI filter

        Args:
            tweet_ids: Candidate tweet ids to check

        Returns:
            Set of ids present in tweet_filter_log
        """
        if not tweet_ids:
            return set()
        self.connect()
        cursor = self.conn.cursor()
        placeholders = ','.join('?' for _ in tweet_ids)
        cursor.execute(
            f'SELECT id FROM tweet_filter_log WHERE id IN ({placeholders})',
            tweet_ids
        )
        return {row['id'] for row in cursor.fetchall()}

    def log_discarded(self, discarded: List[tuple]) -> int:
        """
        Record tweets discarded by the AI filter

        Args:
            discarded: List of (tweet_id, reason) tuples

        Returns:
            Number of rows written
        """
        if not discarded:
            return 0
        self.connect()
        cursor = self.conn.cursor()
        for tweet_id, reason in discarded:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO tweet_filter_log (id, reason)
                    VALUES (?, ?)
                ''', (str(tweet_id), str(reason)[:200]))
            except Exception as e:
                logger.error(f"Error logging discarded tweet {tweet_id}: {e}")
        self.conn.commit()
        logger.info(f"Logged {len(discarded)} discarded tweets")
        return len(discarded)

    def log_collection_run(self, collection_type: str, tweet_count: int,
                          error_message: str = None, status: str = 'success'):
        """
        Log a collection run in metadata table
        
        Args:
            collection_type: Type of collection (e.g., 'feed', 'search')
            tweet_count: Number of tweets collected
            error_message: Any error that occurred
            status: Status of the run ('success', 'error', 'partial')
        """
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO collection_metadata 
            (collection_type, last_collection_time, tweet_count_collected, error_message, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            collection_type,
            datetime.now(),
            tweet_count,
            error_message,
            status
        ))
        
        self.conn.commit()
        logger.info(f"Logged collection run: {collection_type}, tweets: {tweet_count}, status: {status}")
    
    def get_last_collection_time(self, collection_type: str = None) -> Optional[datetime]:
        """
        Get timestamp of last successful collection
        
        Args:
            collection_type: Type of collection to filter by
            
        Returns:
            Last collection timestamp or None
        """
        self.connect()
        cursor = self.conn.cursor()
        
        if collection_type:
            cursor.execute('''
                SELECT last_collection_time FROM collection_metadata 
                WHERE collection_type = ? AND status = 'success'
                ORDER BY created_at DESC
                LIMIT 1
            ''', (collection_type,))
        else:
            cursor.execute('''
                SELECT last_collection_time FROM collection_metadata 
                WHERE status = 'success'
                ORDER BY created_at DESC
                LIMIT 1
            ''')
        
        result = cursor.fetchone()
        return result[0] if result else None


# Global database instance
_db = None


def get_database() -> TweetDatabase:
    """Get or create global database instance"""
    global _db
    if _db is None:
        _db = TweetDatabase()
    return _db


def close_database():
    """Close global database instance"""
    global _db
    if _db:
        _db.disconnect()
        _db = None
