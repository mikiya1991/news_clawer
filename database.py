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
                UNIQUE(id)
            )
        ''')
        
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
                (id, username, text, like_count, retweet_count, view_count, url, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tweet_data['id'],
                tweet_data.get('username', ''),
                tweet_data.get('text', ''),
                int(tweet_data.get('like_count', 0)),
                int(tweet_data.get('retweet_count', 0)),
                int(tweet_data.get('view_count', 0)),
                tweet_data.get('url', ''),
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
            WHERE collected_at > datetime('now', '-' || ? || ' hours')
            ORDER BY collected_at DESC
        ''', (hours,))
        
        tweets = []
        for row in cursor.fetchall():
            tweets.append(dict(row))
        
        return tweets
    
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
