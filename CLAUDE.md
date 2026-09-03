# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

X.com Tweet Scraper — a Python-based browser automation tool that uses Playwright to collect tweets from X.com, stores them in SQLite, and provides a Flask web dashboard for browsing results.

## Common Commands

All Python scripts should be run from the project root with the virtual environment activated.

### Setup
```bash
./setup.sh                    # One-time setup: venv, deps, playwright browsers
source venv/bin/activate
```

### Scraper Operations
```bash
python3 main.py --login       # Interactive login (saves browser state to browser_state/)
python3 main.py --collect     # Run one collection cycle (visible browser)
python3 main.py --collect --headless --iterations 5
python3 main.py --stats       # Print database statistics
```

### Scheduler
```bash
python3 scheduler.py          # Foreground scheduler (hourly by default)
nohup python3 scheduler.py > logs/scheduler.log 2>&1 &   # Background
pkill -f scheduler.py         # Stop background scheduler
```

### Web Dashboard
```bash
cd web/
source ../venv/bin/activate
pip install -r requirements.txt
python app.py                 # http://localhost:5001
```

### News Radar (新闻雷达)
```bash
cp .env.example .env          # Fill in DEEPSEEK_API_KEY, PUSH_PROVIDER/PUSH_TOKEN, RSS_FEEDS
python3 main.py --collect-news    # One manual news cycle: RSS + X -> DeepSeek scoring -> WeChat push
```
Scored news is stored in the `news_items` table of `tweets.db` and browsable at `http://localhost:5001/news`. The scheduler runs the news cycle hourly by default (`NEWS_CYCLE_INTERVAL_MINUTES` in `config.py`).

### Database
```bash
sqlite3 tweets.db "SELECT username, text, like_count FROM tweets ORDER BY collected_at DESC LIMIT 10;"
tail -f logs/scraper.log      # Live log stream
```

## Architecture

### Core Data Flow
```
main.py --collect
  └─> collection_cycle()
        ├─> browser.py  (Playwright, persistent context from browser_state/)
        ├─> scraper.py  (scroll feed, extract tweets via data-testid selectors)
        └─> database.py (SQLite batch insert, dedup by tweet ID)
```

### Key Modules

- **browser.py**: `BrowserManager` wraps Playwright's async API. Uses `launch_persistent_context` with `user_data_dir=browser_state/` so cookies/session survive across runs. Auth is session-based — no passwords stored. Call `check_login_status()` to verify the `SideNav_NewTweet_Button` indicator.
- **scraper.py**: `TweetScraper` scrolls the X.com feed and extracts tweet elements using `data-testid` selectors defined in `config.py`. Engagement counts ("1.2K") are parsed to integers. A session-level `scraped_tweet_ids` set prevents duplicates within a single run.
- **database.py**: `TweetDatabase` is a SQLite wrapper. Access the global singleton via `get_database()`; close with `close_database()`. Tables: `tweets` (tweet data) and `collection_metadata` (run history). Batch inserts skip duplicates by tweet ID.
- **scheduler_module.py**: Background scheduler designed for programmatic control. Runs `collection_cycle()` in a daemon thread. State is persisted to `scheduler_config.json` and `logs/scheduler_history.json`. Auto-starts on import if `running: true` in config. Imported by `web/app.py` for the scheduler control page.
- **scheduler.py**: Simpler standalone scheduler script using the `schedule` library. Use this for basic cron-like operation without the web UI.
- **logger.py**: Unified logging configuration with daily rotating file handlers. Both `main.py` and `scheduler.py` call `configure_logging()` on startup to avoid duplicate handlers.
- **web/app.py**: Flask app on port 5001. Serves a dashboard that reads from the same `tweets.db` and can start/stop the scheduler via `scheduler_module.py` endpoints.
- **news_pipeline.py**: News Radar orchestrator. `run_news_cycle()` runs one full cycle: fetch RSS (news_fetcher.py) + X candidates from tweets.db → score via DeepSeek (news_scorer.py, one batched request) → store in `news_items` (news_db.py) → push top-scored digest to WeChat (news_pusher.py, Server酱/PushPlus). Synchronous — called from CLI (`--collect-news`) and scheduler thread.

### Configuration
All tunables (selectors, scroll settings, paths, timeouts) live in `config.py`. Key settings:
- `HEADLESS_MODE`: visibility for collection runs
- `MAX_SCROLL_ATTEMPTS` / `SCROLL_PAUSE_TIME`: feed depth and rate-limiting
- `TWEET_SELECTOR` and related selectors: X.com `data-testid` attributes
- `DEBUG_SCREENSHOTS`: saves `debug_screenshots/` on errors

## Important Patterns

- **Global singletons**: `get_database()` and `configure_logging()` return shared instances. Avoid creating multiple `TweetDatabase` objects.
- **Async throughout**: `browser.py`, `scraper.py`, and `main.py` use `asyncio`. The scheduler bridges sync and async via `asyncio.run(collection_cycle(...))`.
- **Session persistence is the auth model**: If "Not logged in" errors appear, run `python3 main.py --login` to refresh `browser_state/`. Never hardcode credentials.
- **Web and scraper share state**: `web/app.py` and the scraper both read/write `tweets.db` and `scheduler_config.json`.
