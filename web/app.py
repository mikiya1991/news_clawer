"""
Flask web application for tweet dashboard with scheduler control
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path to import config and database
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

import config
from database import TweetDatabase
from news_db import NewsDatabase
from scheduler_module import (start_scheduler, stop_scheduler, get_status,
                              auto_start_if_enabled, trigger_login,
                              trigger_collection_now, trigger_news_now,
                              trigger_tweet_scoring, trigger_news_scoring)

app = Flask(__name__,
    template_folder='templates',
    static_folder='static'
)
CORS(app)

# Initialize database
db = TweetDatabase()
news_db = NewsDatabase()

# Auto-start scheduler if it was running before (on Flask startup)
auto_start_if_enabled()


@app.route('/')
def index():
    """Render main page - the news timeline"""
    return render_template('timeline.html')


@app.route('/tweets')
def tweets_page():
    """Render tweet dashboard page"""
    return render_template('index.html')


@app.route('/api/tweets')
def get_tweets():
    """
    Get tweets with sorting, filtering, and pagination
    
    Query params:
    - sort: time|user|likes|views|retweets (default: time)
    - order: asc|desc (default: desc)
    - username: filter by username
    - search: search in tweet text
    - page: page number (default: 1)
    - limit: items per page (default: 50)
    """
    try:
        # Parse query parameters
        sort = request.args.get('sort', 'time')
        order = request.args.get('order', 'desc')
        username = request.args.get('username', '')
        search = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        # Validate parameters
        if page < 1:
            page = 1
        if limit < 1 or limit > 200:
            limit = 50
        
        offset = (page - 1) * limit
        
        # Build query (kept=1 hides AI-filtered low-value tweets)
        query = "SELECT * FROM tweets WHERE kept = 1"
        params = []
        
        if username:
            query += " AND username LIKE ?"
            params.append(f"%{username}%")
        
        if search:
            query += " AND text LIKE ?"
            params.append(f"%{search}%")
        
        # Add sorting
        sort_column = {
            'time': 'collected_at',
            'user': 'username',
            'likes': 'like_count',
            'views': 'view_count',
            'retweets': 'retweet_count'
        }.get(sort, 'collected_at')
        
        order_dir = 'DESC' if order == 'desc' else 'ASC'
        query += f" ORDER BY {sort_column} {order_dir}"
        
        # Add pagination
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # Execute query
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute(query, params)
        
        tweets = []
        for row in cursor.fetchall():
            tweet = dict(row)
            # Format timestamps
            if tweet.get('collected_at'):
                tweet['collected_at'] = tweet['collected_at'] if isinstance(tweet['collected_at'], str) else tweet['collected_at'].strftime('%Y-%m-%d %H:%M:%S')
            if tweet.get('created_at'):
                tweet['created_at'] = tweet['created_at'] if isinstance(tweet['created_at'], str) else tweet['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            tweets.append(tweet)
        
        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM tweets WHERE kept = 1"
        count_params = []
        if username:
            count_query += " AND username LIKE ?"
            count_params.append(f"%{username}%")
        if search:
            count_query += " AND text LIKE ?"
            count_params.append(f"%{search}%")
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        return jsonify({
            'success': True,
            'tweets': tweets,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/users')
def get_users():
    """Get list of all unique usernames"""
    try:
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT username, COUNT(*) as tweet_count
            FROM tweets
            WHERE kept = 1
            GROUP BY username
            ORDER BY tweet_count DESC
        ''')
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'username': row['username'],
                'tweet_count': row['tweet_count']
            })
        
        return jsonify({
            'success': True,
            'users': users
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics"""
    try:
        db.connect()
        cursor = db.conn.cursor()
        
        # Total tweets
        cursor.execute('SELECT COUNT(*) FROM tweets WHERE kept = 1')
        total_tweets = cursor.fetchone()[0]

        # Unique users
        cursor.execute('SELECT COUNT(DISTINCT username) FROM tweets WHERE kept = 1')
        unique_users = cursor.fetchone()[0]

        # Total likes
        cursor.execute('SELECT COALESCE(SUM(like_count), 0) FROM tweets WHERE kept = 1')
        total_likes = cursor.fetchone()[0]

        # Total views
        cursor.execute('SELECT COALESCE(SUM(view_count), 0) FROM tweets WHERE kept = 1')
        total_views = cursor.fetchone()[0]

        # Latest collection time
        cursor.execute('SELECT MAX(collected_at) FROM tweets WHERE kept = 1')
        latest_collection = cursor.fetchone()[0]
        
        return jsonify({
            'success': True,
            'stats': {
                'total_tweets': total_tweets,
                'unique_users': unique_users,
                'total_likes': total_likes,
                'total_views': total_views,
                'latest_collection': latest_collection
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Scheduler Control Routes
@app.route('/scheduler')
def scheduler_page():
    """Render scheduler control page"""
    return render_template('scheduler.html')


@app.route('/api/scheduler/status')
def scheduler_status():
    """Get scheduler status"""
    return jsonify(get_status())


@app.route('/api/scheduler/start', methods=['POST'])
def scheduler_start():
    """Start the scheduler"""
    try:
        data = request.get_json() or {}
        interval = int(data.get('interval', 1))
        unit = data.get('unit', 'hours')
        
        # Validate unit
        if unit not in ['minutes', 'hours', 'days']:
            unit = 'hours'
        
        # Validate interval
        if interval < 1:
            interval = 1
        if interval > 1440 and unit == 'minutes':  # Max 24 hours in minutes
            interval = 60
        
        success = start_scheduler(interval, unit)
        if success:
            return jsonify({
                'success': True,
                'message': f'Scheduler started: every {interval} {unit}'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Scheduler is already running'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start scheduler: {str(e)}'
        }), 500


@app.route('/api/scheduler/stop', methods=['POST'])
def scheduler_stop():
    """Stop the scheduler"""
    try:
        success = stop_scheduler()
        if success:
            return jsonify({
                'success': True,
                'message': 'Scheduler stopped'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Scheduler is not running'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to stop scheduler: {str(e)}'
        }), 500


_BUSY_JOB_LABELS = {
    'collection': '推文采集',
    'news': '新闻采集',
    'login': '登录',
    'tweet-scoring': 'Tweet评分',
    'news-scoring': '新闻评分',
}


def _manual_job_response(result):
    """Build the JSON response for manual job triggers"""
    if result.get('started'):
        return jsonify({'success': True, 'message': result.get('message', '任务已启动')})
    busy = result.get('busy', 'unknown')
    label = _BUSY_JOB_LABELS.get(busy, busy)
    return jsonify({
        'success': False,
        'message': f'另一个任务正在执行中（{label}），请稍后再试'
    }), 409


@app.route('/api/scheduler/login', methods=['POST'])
def scheduler_login():
    """Open a visible browser for manual X login (auto-detects completion)"""
    try:
        return _manual_job_response(trigger_login())
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start login: {str(e)}'
        }), 500


@app.route('/api/scheduler/collect-now', methods=['POST'])
def scheduler_collect_now():
    """Run one tweet collection cycle immediately (visible browser)"""
    try:
        return _manual_job_response(trigger_collection_now())
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start collection: {str(e)}'
        }), 500


@app.route('/api/scheduler/news-now', methods=['POST'])
def scheduler_news_now():
    """Run one news cycle immediately (fetch + score + push)"""
    try:
        return _manual_job_response(trigger_news_now())
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start news cycle: {str(e)}'
        }), 500


@app.route('/api/scheduler/score-tweets', methods=['POST'])
def scheduler_score_tweets():
    """AI-score unscored tweets (low-scored ones get hidden)"""
    try:
        return _manual_job_response(trigger_tweet_scoring())
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start tweet scoring: {str(e)}'
        }), 500


@app.route('/api/scheduler/score-news', methods=['POST'])
def scheduler_score_news():
    """Re-score the most recent news items"""
    try:
        return _manual_job_response(trigger_news_scoring())
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start news scoring: {str(e)}'
        }), 500


@app.route('/api/scheduler/overview')
def scheduler_overview():
    """
    Aggregated data for the scheduler page: current status, recent tweet
    collection results, unscored tweets, news cycle history, and recent
    scored news items.
    """
    try:
        status = get_status()

        # Recent tweet collection runs
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT collection_type, last_collection_time, tweet_count_collected,
                   status, error_message, created_at
            FROM collection_metadata
            WHERE collection_type = 'feed'
            ORDER BY created_at DESC
            LIMIT 10
        ''')
        collections = [dict(row) for row in cursor.fetchall()]

        # Tweets not yet AI-scored (score_history never run on them)
        cursor.execute(
            'SELECT COUNT(*) FROM tweets WHERE ai_score IS NULL AND kept = 1'
        )
        unscored_total = cursor.fetchone()[0]

        cursor.execute('''
            SELECT id, username, text, like_count, collected_at
            FROM tweets
            WHERE ai_score IS NULL AND kept = 1
            ORDER BY collected_at DESC
            LIMIT 30
        ''')
        unscored_tweets = [dict(row) for row in cursor.fetchall()]

        # News cycle history from scheduler_history.json.
        # Duplicate entries (same timestamp + message) are collapsed.
        news_runs = []
        hist_file = Path(__file__).parent.parent / 'logs' / 'scheduler_history.json'
        if hist_file.exists():
            with open(hist_file, 'r', encoding='utf-8') as f:
                entries = json.load(f)
            seen = set()
            for entry in entries:
                message = str(entry.get('message', ''))
                if not message.startswith('News cycle'):
                    continue
                key = (entry.get('timestamp'), message)
                if key in seen:
                    continue
                seen.add(key)
                news_runs.append({
                    'timestamp': entry.get('timestamp'),
                    'status': entry.get('status'),
                    'message': message,
                })
                if len(news_runs) >= 5:
                    break

        # Recent scored news items (kept only)
        news_items = news_db.get_items(limit=15, sort='time', order='desc')

        return jsonify({
            'success': True,
            'status': status,
            'collections': collections,
            'unscored_total': unscored_total,
            'unscored_tweets': unscored_tweets,
            'news_runs': news_runs,
            'news_items': news_items,
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scheduler/logs')
def scheduler_logs():
    """Get recent log entries from scraper.log"""
    try:
        lines = int(request.args.get('lines', 100))
        if lines < 1 or lines > 1000:
            lines = 100

        log_file = Path(__file__).parent.parent / 'logs' / 'scraper.log'
        if not log_file.exists():
            return jsonify({'success': True, 'logs': []})

        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return jsonify({
            'success': True,
            'logs': [line.rstrip('\n') for line in recent_lines]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# News Radar Routes
@app.route('/news')
def news_page():
    """Render news radar dashboard page"""
    return render_template('news.html')


@app.route('/timeline')
def timeline_page():
    """Render news timeline page"""
    return render_template('timeline.html')


@app.route('/api/timeline')
def get_timeline():
    """
    Get extremely important news grouped by date for the timeline

    Query params:
    - min_score: minimum score filter (default from config)
    - limit: max items (default 300, max 500)
    """
    try:
        min_score = int(request.args.get('min_score', config.NEWS_TIMELINE_THRESHOLD))
        min_score = max(0, min(100, min_score))
        limit = int(request.args.get('limit', 300))
        if limit < 1 or limit > 500:
            limit = 300

        # 1. News items from news radar
        items = news_db.get_timeline_items(min_score=min_score, limit=limit)
        for item in items:
            reasons = item.get('reasons', '')
            if isinstance(reasons, str):
                try:
                    item['reasons'] = json.loads(reasons)
                except (json.JSONDecodeError, ValueError):
                    item['reasons'] = []
            item['kind'] = 'news'

        # 2. High-scored X tweets, capped per day to keep the timeline readable
        tweets = db.get_top_tweets(min_score=min_score)
        per_day = {}
        for t in tweets:
            day = str(t.get('collected_at') or '')[:10]
            if per_day.get(day, 0) >= config.NEWS_TIMELINE_TWEETS_PER_DAY:
                continue
            per_day[day] = per_day.get(day, 0) + 1
            items.append({
                'id': t['id'],
                'kind': 'tweet',
                'source': 'x',
                'source_name': '@' + str(t.get('username', '')),
                'title': str(t.get('text', ''))[:80],
                'summary': t.get('ai_summary', ''),
                'url': t.get('url', ''),
                'score': t.get('ai_score'),
                'published_at': t.get('collected_at'),
                'created_at': t.get('collected_at'),
                'reasons': [],
            })

        # Group by date (publish date for news, collected_at for tweets)
        by_date = {}
        for item in items:
            ts = item.get('published_at') or item.get('created_at') or ''
            date = str(ts)[:10]
            if date:
                by_date.setdefault(date, []).append(item)

        # Sort each day's items by time desc
        for day_items in by_date.values():
            day_items.sort(
                key=lambda i: str(i.get('published_at') or i.get('created_at') or ''),
                reverse=True
            )

        groups = [{'date': d, 'items': by_date[d]}
                  for d in sorted(by_date, reverse=True)]

        return jsonify({'success': True, 'groups': groups})

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/news')
def get_news():
    """
    Get scored news items with sorting, filtering, and pagination

    Query params:
    - sort: score|time (default: score)
    - order: asc|desc (default: desc)
    - source: rss|x filter
    - min_score: minimum score filter
    - pushed: 0|1 filter
    - page: page number (default: 1)
    - limit: items per page (default: 50)
    """
    try:
        # Parse query parameters
        sort = request.args.get('sort', 'score')
        order = request.args.get('order', 'desc')
        source = request.args.get('source', '')
        min_score = request.args.get('min_score', '')
        pushed = request.args.get('pushed', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))

        # Validate parameters
        if sort not in ['score', 'time']:
            sort = 'score'
        if order not in ['asc', 'desc']:
            order = 'desc'
        if source not in ['rss', 'x']:
            source = None
        if page < 1:
            page = 1
        if limit < 1 or limit > 200:
            limit = 50

        min_score_int = None
        if min_score:
            try:
                min_score_int = max(0, min(100, int(min_score)))
            except ValueError:
                min_score_int = None

        pushed_int = None
        if pushed in ['0', '1']:
            pushed_int = int(pushed)

        offset = (page - 1) * limit

        items = news_db.get_items(
            limit=limit, offset=offset, sort=sort, order=order,
            source=source, min_score=min_score_int, pushed=pushed_int
        )

        # Parse reasons JSON string into a list for the frontend
        for item in items:
            reasons = item.get('reasons', '')
            if isinstance(reasons, str):
                try:
                    item['reasons'] = json.loads(reasons)
                except (json.JSONDecodeError, ValueError):
                    item['reasons'] = []

        total_count = news_db.get_count(
            source=source, min_score=min_score_int, pushed=pushed_int
        )

        return jsonify({
            'success': True,
            'items': items,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/news/stats')
def get_news_stats():
    """Get news radar aggregate statistics"""
    try:
        return jsonify({
            'success': True,
            'stats': news_db.get_stats()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # use_reloader=False: the Werkzeug debug reloader forks a child process,
    # which re-runs module-level code (auto_start_if_enabled) and doubles the
    # scheduler. The scheduler PID lock in scheduler_module guards this too.
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
