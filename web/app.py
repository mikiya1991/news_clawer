"""
Flask web application for tweet dashboard with scheduler control
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path to import config and database
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from database import TweetDatabase
from scheduler_module import start_scheduler, stop_scheduler, get_status, auto_start_if_enabled

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
CORS(app)

# Initialize database
db = TweetDatabase()

# Auto-start scheduler if it was running before (on Flask startup)
auto_start_if_enabled()


@app.route('/')
def index():
    """Render main dashboard page"""
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
        
        # Build query
        query = "SELECT * FROM tweets WHERE 1=1"
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
        count_query = "SELECT COUNT(*) FROM tweets WHERE 1=1"
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
        cursor.execute('SELECT COUNT(*) FROM tweets')
        total_tweets = cursor.fetchone()[0]
        
        # Unique users
        cursor.execute('SELECT COUNT(DISTINCT username) FROM tweets')
        unique_users = cursor.fetchone()[0]
        
        # Total likes
        cursor.execute('SELECT COALESCE(SUM(like_count), 0) FROM tweets')
        total_likes = cursor.fetchone()[0]
        
        # Total views
        cursor.execute('SELECT COALESCE(SUM(view_count), 0) FROM tweets')
        total_views = cursor.fetchone()[0]
        
        # Latest collection time
        cursor.execute('SELECT MAX(collected_at) FROM tweets')
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
