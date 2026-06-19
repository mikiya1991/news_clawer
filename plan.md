# Plan: X.com Tweet Scraper with Playwright

## TL;DR
Build a Python script using Playwright to automatically control a browser, login to X.com, collect tweets (content, username, read count, like count), and store them in SQLite. Run periodically via Python schedule library on local machine. Manual login once, then script handles browser automation for data collection.

## Steps

### Phase 1: Project Setup
1. Initialize Python project structure with `requirements.txt` (Playwright, SQLite3 drivers)
2. Create config file for X.com URLs, wait times, and collection intervals
3. Set up SQLite database schema with tables: `tweets`, `metadata` (last_collection_time, status)

### Phase 2: Playwright & Browser Automation Foundation
4. Create `browser.py` module to handle Playwright browser initialization and lifecycle
5. Implement login persistence: Save browser state after manual login so script can reuse session (avoids re-login)
6. Add screenshot/debugging capabilities for troubleshooting XPath/selector changes
7. Implement page wait strategies (wait for dynamic content loading, scrolling)

### Phase 3: Data Collection Logic
8. Create `scraper.py` module with functions to:
   - Navigate to X.com feed/search
   - Scroll and identify tweet elements
   - Extract: tweet text, username, like count, read count
   - Handle pagination/infinite scroll
9. Implement retry logic for failed extractions (network timeouts, element not found)
10. Add timestamp tracking to avoid duplicate collections

### Phase 4: Database Storage
11. Create `database.py` module with:
    - SQLite connection management
    - Insert/upsert tweets (avoid duplicates using tweet ID)
    - Query methods for analysis
12. Add data validation before insertion

### Phase 5: Scheduling & Execution
13. Create `main.py` orchestrator that:
    - Runs collection cycle
    - Handles errors gracefully
    - Logs execution status
14. Setup schedule library: Create `scheduler.py` using Python schedule library for periodic execution (hourly/6x daily)
15. Add logging to file for monitoring execution

### Phase 6: Testing & Refinement
16. Manual test: Run scraper once with real X.com session
17. Verify database stores tweets correctly
18. Test schedule library with shortened interval
19. Monitor for selector changes on X.com (Twitter changes UI frequently)

## Relevant Files

### Core Scraper
- `requirements.txt` — dependencies (playwright, selenium-like features)
- `config.py` — configuration constants (URLs, wait times, collection frequency)
- `browser.py` — Playwright browser setup, session persistence, screenshot debug
- `scraper.py` — Tweet extraction logic, scrolling, retry handling
- `database.py` — SQLite schema, CRUD operations
- `main.py` — Orchestrator, logging, entry point
- `.gitignore` — Exclude `*.db`, auth tokens, browser state directory
- `cron_job.sh` — Helper script to setup cron job (legacy)
- `scheduler.py` — Python schedule library-based task scheduler (recommended)

### Web Dashboard
- `web/app.py` — Flask backend with REST API
- `web/wsgi.py` — WSGI entry for production deployment
- `web/requirements.txt` — Flask dependencies
- `web/templates/index.html` — Dashboard UI
- `web/static/css/style.css` — Custom styles
- `web/static/js/app.js` — Frontend JavaScript

## Verification
1. **Manual login test**: Start script, verify browser opens and prompts login, save session state
2. **First collection run**: Execute scraper → check SQLite database has tweets with correct fields
3. **Data integrity**: Verify no duplicate tweets, timestamps are recorded, counts are numeric
4. **Schedule automation**: Test scheduler with shortened interval, verify logs show execution
5. **Error recovery**: Kill scraper mid-run, restart → check it resumes properly without duplicates
6. **UI change handling**: If X.com selectors break, screenshot captures indicate what changed

## Decisions
- **Session persistence**: Save browser state after login to avoid re-authentication (security tradeoff: session file on disk)
- **Database**: SQLite (simple, file-based, no server) — suitable for local collection; can migrate to PostgreSQL later if scaling
- **Execution**: Python schedule library (vs. cron daemon) — pure Python, easier debugging, cross-platform
- **Manual login**: Handled once by user, script reuses session — avoids storing credentials
- **Scope**: Focused on feed tweets only (not search, not replies) — can extend later

## Further Considerations
1. **X.com rate limits / blocking**: Long collection runs may trigger captchas or IP blocks. Recommendation: Implement backoff delays, randomize scroll speed, consider rotating user-agent headers.
2. **Tweet selector fragility**: X.com uses dynamically generated class names. Recommendation: Store screenshots on failures, use more stable selectors (e.g., `data-testid`), add fallback selectors.
3. **Session expiry**: Browser session may expire after days/weeks. Recommendation: Add re-login prompt if session invalid, or schedule periodic full restart.

---

## Phase 7: Web Dashboard (Added)

A Flask-based web dashboard for browsing and analyzing collected tweets.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Dashboard                          │
├─────────────────────────────────────────────────────────────┤
│  Frontend (HTML + TailwindCSS + Vanilla JS)                │
│  ├── Sorting: time / username / likes / views / retweets   │
│  ├── Filtering: by username, search in content             │
│  └── Pagination: 50 items per page                         │
├─────────────────────────────────────────────────────────────┤
│  Backend (Flask REST API)                                  │
│  ├── GET /api/tweets - list with sort/filter/page          │
│  ├── GET /api/users - unique users list                    │
│  └── GET /api/stats - dashboard statistics                 │
├─────────────────────────────────────────────────────────────┤
│  Data Layer (SQLite - reuses existing database.py)         │
└─────────────────────────────────────────────────────────────┘
```

### File Structure
```
web/
├── app.py              # Flask application + API routes
├── wsgi.py             # WSGI entry point for production
├── requirements.txt    # flask, flask-cors
├── templates/
│   └── index.html      # Dashboard UI (TailwindCSS)
└── static/
    ├── css/style.css   # Custom styles
    └── js/app.js       # Frontend logic (AJAX, sorting, pagination)
```

### Design Decisions
- **Port**: 5001 (macOS AirPlay uses port 5000)
- **No server-side templating loops**: All rendering done via JS fetch for dynamic updates
- **Debounced search**: 500ms delay to reduce API calls
- **Auto-refresh stats**: Every 30 seconds
- **Responsive**: Mobile-first design with TailwindCSS

### Usage

#### Local Development
```bash
cd web/
source ../venv/bin/activate
pip install -r requirements.txt
python app.py
# Open http://localhost:5001
```

#### Deploy to Production (with Gunicorn)
```bash
cd web/
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 wsgi:app
```

#### Deploy to Netlify (Serverless)
```bash
# Install netlify-cli
npm install -g netlify-cli
# Deploy
netlify deploy --prod --dir=.
```

### API Reference

| Endpoint | Query Params | Description |
|----------|--------------|-------------|
| `GET /api/tweets` | `sort`, `order`, `username`, `search`, `page`, `limit` | Get paginated tweets |
| `GET /api/users` | - | Get unique usernames with counts |
| `GET /api/stats` | - | Get dashboard statistics |

### Sort Options
- `time` (default) - by collected_at
- `user` - by username
- `likes` - by like_count
- `views` - by view_count
- `retweets` - by retweet_count