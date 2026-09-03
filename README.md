# X.com Tweet Scraper with Playwright

自动化脚本，使用 Playwright 控制浏览器从 X.com 收集推文数据。支持定期自动收集、SQLite 数据存储和定时任务。

## 功能

- 🌐 **浏览器自动化**: 使用 Playwright 控制浏览器
- 💾 **数据存储**: SQLite 本地数据库，支持 3500+ 推文
- ⏱️ **定时采集**: 支持 Python schedule 库定时任务（每小时/6小时/12小时/每天）
- 📊 **数据提取**: 自动提取推文文本、用户名、点赞数、转发数、浏览量
- 🔄 **会话持久化**: 首次登录后自动保存浏览器状态，后续运行无需重新登录
- 📝 **详细日志**: 完整的执行日志、错误跟踪和调试截图
- 🛡️ **错误恢复**: 自动处理重试、异常和网络问题
- 🤖 **AI 自动筛选**: DeepSeek 判断推文价值，垃圾推文不入库（fail-open 不丢数据）
- 🀄 **AI 中文摘要**: 英文推文自动生成一行中文摘要
- 📡 **新闻雷达**: RSS + X 推文 → DeepSeek 评分 → 微信推送（Server酱/PushPlus）

## 项目结构

```
new_clawer/
├── main.py                 # 主程序、协调器
├── browser.py              # Playwright 浏览器管理
├── scraper.py              # 推文数据抓取逻辑
├── database.py             # SQLite 数据库操作
├── config.py               # 配置文件
├── logger.py               # 统一日志配置（日志轮转）
├── requirements.txt        # Python 依赖
├── scheduler.py           # Python schedule 库定时调度器（推荐）
├── scheduler_module.py    # 程序化调度器（Web 面板控制，随 app.py 自动启动）
├── tweet_filter.py        # AI 推文价值筛选/评分（DeepSeek 批量）
├── tweet_summarizer.py    # 英文推文 AI 中文摘要
├── news_pipeline.py       # 新闻雷达流水线（RSS+X → 评分 → 推送）
├── news_fetcher.py        # RSS 订阅与 X 候选推文抓取
├── news_scorer.py         # DeepSeek 新闻评分
├── news_db.py             # 新闻数据存储（news_items 表）
├── news_pusher.py         # 微信推送（Server酱/PushPlus）
├── .env.example           # 环境变量模板（API key、推送、RSS）
├── cron_job.sh            # 传统 cron 设置脚本（已弃用）
├── .gitignore             # Git 忽略文件
├── README.md              # 本文件
├── tweets.db              # SQLite 数据库（自动生成）
├── browser_state/         # Playwright 浏览器状态（自动生成）
├── logs/                  # 执行日志（自动生成）
├── debug_screenshots/     # 调试截图（自动生成）
└── web/                   # Web Dashboard（Flask + SQLite）
    ├── app.py             # Flask 后端 API
    ├── templates/         # HTML 模板
    └── static/            # CSS/JS 静态文件
```

## 安装

### 1. 克隆或下载项目

```bash
cd /Users/mikiya/workspace/new_clawer
```

### 2. 创建 Python 虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
playwright install
```

## 使用方法

### 步骤 1: 首次登录

首先需要手动登录 X.com（这样可以避免存储密码）。之后浏览器状态会被保存供后续使用。

```bash
python3 main.py --login
```

这会打开浏览器窗口：
1. 浏览器会打开 X.com
2. 使用你的账号登录
3. 登录成功后，按 Enter 关闭浏览器
4. 浏览器状态已保存

### 步骤 2: 运行数据采集

#### 立即运行一次（非后台模式，可看到浏览器操作过程）

```bash
python3 main.py --collect
```

#### 后台运行（不显示浏览器窗口）

```bash
python3 main.py --collect --headless
```

#### 指定滚动次数

```bash
python3 main.py --collect --iterations 5
```

### 步骤 3: 查看统计信息

```bash
python3 main.py --stats
```

输出示例：
```
================================================================================
TWEET DATABASE STATISTICS
================================================================================
Total tweets: 1,234
Tweets in last 24 hours: 45

Recent tweets:
  - @username1: This is a great tweet...
  - @username2: Another interesting tweet...
================================================================================
```

### 步骤 4: 设置定时采集（推荐：Python schedule）

使用 Python schedule 库（纯 Python，无需系统工具，易调试）：

#### 1. 安装依赖

```bash
pip install schedule
```

#### 2. 创建调度器

创建 `scheduler.py`：

```python
import schedule
import time
import subprocess

def collect_tweets():
    subprocess.run(['python3', 'main.py', '--collect', '--headless'])

# 每小时运行一次（默认）
schedule.every().hour.do(collect_tweets)

# 也可以根据需求修改：
# schedule.every(6).hours.do(collect_tweets)         # 每 6 小时
# schedule.every(12).hours.do(collect_tweets)        # 每 12 小时
# schedule.every().day.at("09:00").do(collect_tweets) # 每天 9:00

print("Scheduler started. Press Ctrl+C to stop.")
while True:
    schedule.run_pending()
    time.sleep(60)
```

#### 3. 运行调度器

前台运行（方便查看日志和调试）：
```bash
python3 scheduler.py
```

后台运行（长期使用）：
```bash
nohup python3 scheduler.py > logs/scheduler.log 2>&1 &
```

查看运行状态：
```bash
ps aux | grep scheduler.py
```

停止：
```bash
pkill -f scheduler.py
```

#### 常用 schedule 语法

```python
schedule.every(10).minutes.do(collect_tweets)    # 每 10 分钟
schedule.every().hour.do(collect_tweets)         # 每小时
schedule.every(6).hours.do(collect_tweets)       # 每 6 小时
schedule.every().day.at("09:00").do(collect_tweets) # 每天 9:00
schedule.every().monday.do(collect_tweets)       # 每周一
```

### 步骤 5: 启动 Web 可视化界面

启动 Web Dashboard 在浏览器中查看和筛选采集的推文：

```bash
cd web/
source ../venv/bin/activate
pip install -r requirements.txt
python app.py
```

打开浏览器访问: **http://localhost:5001**

功能：
- 按时间/用户名/点赞数/浏览量/转发数排序
- 按用户名筛选、搜索推文内容
- 分页浏览，每页 50 条
- 实时统计面板

### 其他定时任务方式

如果 schedule 库不适合你的需求，以下是其他可选方案：

#### macOS launchd（macOS 原生）

比 cron 更可靠，支持自动重启：

创建 `~/Library/LaunchAgents/com.tweetscraper.collect.plist`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tweetscraper.collect</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/mikiya/workspace/new_clawer/venv/bin/python3</string>
        <string>/Users/mikiya/workspace/new_clawer/main.py</string>
        <string>--collect</string>
        <string>--headless</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>WorkingDirectory</key>
    <string>/Users/mikiya/workspace/new_clawer</string>
    <key>StandardOutPath</key>
    <string>/Users/mikiya/workspace/new_clawer/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mikiya/workspace/new_clawer/logs/launchd_error.log</string>
</dict>
</plist>
```

加载并启动：
```bash
launchctl load ~/Library/LaunchAgents/com.tweetscraper.collect.plist
launchctl start com.tweetscraper.collect
```

#### cron（传统方案）

```bash
# 每小时运行
crontab -e
```
添加：
```bash
0 * * * * cd /Users/mikiya/workspace/new_clawer && /usr/bin/python3 main.py --collect --headless
```

#### systemd Timer（Linux）

创建 `/etc/systemd/system/tweet-scraper.service`：
```ini
[Unit]
Description=Tweet Scraper
[Service]
Type=oneshot
WorkingDirectory=/path/to/new_clawer
ExecStart=/path/to/venv/bin/python3 main.py --collect --headless
```

创建 `/etc/systemd/system/tweet-scraper.timer`：
```ini
[Unit]
Description=Run Tweet Scraper every hour
[Timer]
OnCalendar=hourly
Persistent=true
[Install]
WantedBy=timers.target
```

启用并启动：
```bash
sudo systemctl daemon-reload
sudo systemctl enable tweet-scraper.timer
sudo systemctl start tweet-scraper.timer
```

#### 简单的 while + sleep（测试用）

```bash
#!/bin/bash
while true; do
    python3 main.py --collect --headless
    sleep 3600
done
```

#### 方案对比

| 方式 | 适用系统 | 优点 | 缺点 |
|------|---------|------|------|
| **schedule** | 通用 | **纯 Python、易调试、推荐** | 需保持脚本运行 |
| launchd | macOS | 原生支持、自动重启 | 仅 macOS |
| cron | 通用 | 简单、传统 | 错误处理弱、难以调试 |
| systemd | Linux | 系统级、可靠 | 仅 Linux |
| while+sleep | 通用 | 最简单 | 无持久化、重启需手动 |

## AI 自动筛选

推文从采集到推送共经过 **三层 AI 筛选**（DeepSeek），触发时机各不相同：

### 环境准备

```bash
cp .env.example .env    # 填入 DEEPSEEK_API_KEY（筛选必需）
```

`.env` 中还可配置：`PUSH_PROVIDER`/`PUSH_TOKEN`（微信推送）、`RSS_FEEDS`（新闻源）、`DEEPSEEK_MODEL` 等。

### 1. 采集时过滤（写入数据库之前）

每次采集循环（`--collect` 或调度器定时采集）抓到新推文后、**写入 `tweets.db` 之前**，`tweet_filter.py` 的 `filter_tweets()` 用 DeepSeek 批量判断每条推文是否值得收集：

- **保留**：新闻、行业资讯、数据、公告、独到观点、深度分析、有价值分享
- **丢弃**：纯闲聊、日常寒暄、无信息量互动、无补充的纯转发、广告抽奖

特点：

- 已被判定丢弃的推文会记录在库，**永不重复判断**（再次抓到直接跳过）
- 每轮最多判断 `AI_FILTER_MAX_TWEETS=50` 条，超出部分不过滤直接入库
- **Fail-open**：DeepSeek 失败或未配置 key 时全部入库，不丢数据
- 开关：环境变量 `AI_FILTER_ENABLED`（默认开启）

过滤之后，英文推文还会经 `tweet_summarizer.py` 生成一行中文摘要（`ai_summary` 字段），仅作标注、不参与筛选。

### 2. 历史推文打分隐藏（手动触发）

```bash
python3 main.py --score-history [N]   # 不加 N = 全部未评分的推文
```

对库中未评分的推文打分（0-100），低于 `TWEET_STORE_THRESHOLD=60` 的在 Web 面板中隐藏（`kept=0`，不删除）。

> 注意：此步骤目前**仅支持手动执行**，调度器不会自动运行。

### 3. 新闻雷达评分筛选（每小时自动）

调度器每小时自动运行新闻流水线（`news_pipeline.py`，也可手动 `python3 main.py --collect-news`）：

1. 候选 = RSS 订阅 + 库中近 24 小时、点赞 ≥ 100 的 X 推文
2. DeepSeek 评分后，低于 `NEWS_STORE_THRESHOLD=70` 的入库但标记过滤（`kept=0`）
3. 高于 `NEWS_SCORE_THRESHOLD=70` 的 top 5 推送到微信（Server酱/PushPlus）

这里的 X 候选是第 1 层过滤后已经入库的推文，因此是第二次筛选。评分结果可在 `http://localhost:5001/news` 查看。

### 筛选总览

| 筛选 | 时机 | 触发方式 | 效果 |
|------|------|---------|------|
| AI 过滤 `filter_tweets` | 每次采集时 | 调度器自动（默认每小时） | 垃圾推文不入库 |
| AI 打分 `score_history` | 随时 | 仅手动 CLI | 低分历史推文在面板隐藏 |
| 新闻评分 | 每小时 | 调度器自动 | 高分新闻入库 + 推微信 |

## 数据库

### 表结构

#### tweets 表
存储收集的推文数据：

| 列 | 类型 | 说明 |
|-------|------|------|
| id | TEXT | 推文唯一 ID（主键） |
| username | TEXT | 推文发布者用户名 |
| text | TEXT | 推文内容 |
| like_count | INTEGER | 点赞数 |
| retweet_count | INTEGER | 转发数 |
| view_count | INTEGER | 浏览数 |
| created_at | TIMESTAMP | 推文创建时间 |
| collected_at | TIMESTAMP | 数据收集时间 |
| url | TEXT | 推文链接 |

#### collection_metadata 表
记录每次采集的元数据：

| 列 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 记录 ID |
| collection_type | TEXT | 采集类型（feed/search） |
| last_collection_time | TIMESTAMP | 采集时间 |
| tweet_count_collected | INTEGER | 本次采集推文数 |
| error_message | TEXT | 错误信息（如有） |
| status | TEXT | 采集状态（success/error/partial） |

### 查询数据库

使用 SQLite 命令行工具查看数据：

```bash
sqlite3 tweets.db

# 查看所有推文
SELECT * FROM tweets ORDER BY collected_at DESC LIMIT 10;

# 查看统计
SELECT COUNT(*) as total FROM tweets;

# 查看最近 24 小时的推文
SELECT * FROM tweets WHERE collected_at > datetime('now', '-24 hours');

# 查看采集历史
SELECT * FROM collection_metadata ORDER BY created_at DESC;
```

## 日志

所有执行日志保存在 `logs/scraper.log`：

```bash
# 实时查看日志
tail -f logs/scraper.log

# 查看最近 50 行
tail -50 logs/scraper.log

# 搜索错误
grep ERROR logs/scraper.log
```

## 调试

### 调试截图

当发生错误或需要调试时，脚本会在 `debug_screenshots/` 目录生成截图：

- `screenshot_*.png` - 定期采集的截图
- `scrape_error.png` - 出错时的截图
- `login_required.png` - 登录失败的截图

### 浏览器状态

浏览器的登录状态保存在 `browser_state/` 目录，包含：
- Cookies
- Session data
- 浏览器缓存

### 调试模式

编辑 `config.py` 启用调试：

```python
DEBUG_SCREENSHOTS = True       # 启用调试截图
HEADLESS_MODE = False          # 非后台模式，看到浏览器
```

## 配置

编辑 `config.py` 调整参数：

```python
# 浏览器设置
HEADLESS_MODE = False          # False = 可见浏览器，True = 后台运行
BROWSER_TIMEOUT = 30000        # 浏览器超时（毫秒）

# 采集设置
COLLECTION_INTERVAL_MINUTES = 60    # 采集间隔
MAX_SCROLL_ATTEMPTS = 5              # 最大滚动次数
SCROLL_PAUSE_TIME = 2                # 滚动之间的暂停（秒）

# 数据库
DATABASE_PATH = "tweets.db"    # 数据库文件路径
DATABASE_CHECK_SAME_THREAD = False

# 日志
LOG_LEVEL = "INFO"             # 日志级别（DEBUG/INFO/WARNING/ERROR）
```

AI 筛选与新闻雷达相关（API key 等放 `.env`，阈值改 `config.py`）：

```python
# AI 采集时过滤（开关为 .env 中的 AI_FILTER_ENABLED）
AI_FILTER_MAX_TWEETS = 50      # 每轮最多判断的推文数
TWEET_STORE_THRESHOLD = 60     # 历史打分低于此值在面板隐藏

# AI 英文摘要
AI_SUMMARY_ENABLED = True      # 环境变量 AI_SUMMARY_ENABLED 控制
AI_SUMMARY_MAX_TWEETS = 50     # 每批最多摘要的推文数

# 新闻雷达
NEWS_X_LOOKBACK_HOURS = 24     # X 候选时间窗口（小时）
NEWS_X_MIN_LIKES = 100         # X 候选最小点赞数
NEWS_STORE_THRESHOLD = 70      # 低于此分的新闻标记为过滤
NEWS_SCORE_THRESHOLD = 70      # 高于此分才推送微信
NEWS_PUSH_TOP_N = 5            # 每次推送最多条数
NEWS_CYCLE_INTERVAL_MINUTES = 60  # 新闻循环频率
```

## 故障排除

### 问题 1: "Not logged into X.com"

**原因**: 浏览器状态不存在或过期

**解决**:
```bash
python3 main.py --login
```

### 问题 2: 推文提取失败

**原因**: X.com UI 更新导致选择器失效

**解决**:
1. 查看调试截图了解当前界面
2. 更新 `config.py` 中的 CSS 选择器
3. 或使用 `[data-testid]` 属性（更稳定）

### 问题 3: 定时任务未执行

**原因**: schedule 脚本未启动或被意外终止

**解决**:
1. 检查进程是否在运行：`ps aux | grep scheduler.py`
2. 重新启动调度器：`nohup python3 scheduler.py > logs/scheduler.log 2>&1 &`
3. 查看调度器日志：`tail -f logs/scheduler.log`
4. 检查 Python 路径：`which python3`

### 问题 4: 性能缓慢

**原因**: 滚动次数过多或网络慢

**解决**:
1. 减少 `MAX_SCROLL_ATTEMPTS`
2. 增加 `SCROLL_PAUSE_TIME`
3. 检查网络连接

### 问题 5: 内存占用过高

**原因**: 浏览器进程未正常关闭

**解决**:
```bash
# 杀死所有 Chromium 进程
pkill -f chromium
```

## 进阶用法

### 导出数据到 CSV

创建脚本 `export.py`:

```python
import sqlite3
import csv
from database import get_database

db = get_database()
tweets = db.get_tweets(limit=10000)

with open('tweets_export.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=tweets[0].keys())
    writer.writeheader()
    writer.writerows(tweets)

print("Exported to tweets_export.csv")
```

运行：
```bash
python3 export.py
```

### 定期备份数据

创建备份脚本 `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"
cp tweets.db "$BACKUP_DIR/tweets_$(date +%Y%m%d_%H%M%S).db"
echo "Backup created"
```

添加到 schedule 调度器：
```python
import schedule

def backup():
    subprocess.run(['bash', 'backup.sh'])

# 每周日 2:00 备份
schedule.every().sunday.at("02:00").do(backup)
```

## 注意事项

⚠️ **X.com 可能对频繁采集进行限制**:
- 避免过于频繁的采集（建议最少 1 小时一次）
- 使用 `SCROLL_PAUSE_TIME` 增加延迟
- X.com 可能要求验证码或暂时阻止访问

⚠️ **浏览器状态管理**:
- 不要删除 `browser_state/` 目录，否则需要重新登录
- 浏览器状态可能在数周后过期，需要重新登录
- 保持 X.com 密码安全，不要在脚本中硬编码凭据

⚠️ **数据库管理**:
- 定期备份 `tweets.db` 文件
- 大数据库（>10,000 条推文）可能需要迁移到 PostgreSQL
- 不要同时运行多个采集进程

## 许可证

MIT License

## 技术栈

- **Python 3.8+**
- **Playwright** - 浏览器自动化
- **SQLite3** - 本地数据存储
- **schedule** - Python 定时任务调度
- **Flask** - Web Dashboard 后端
- **TailwindCSS** - Web Dashboard 前端样式

## 支持

遇到问题？查看：
1. `logs/scraper.log` - 详细错误日志
2. `debug_screenshots/` - 调试截图
3. 查看本 README 的故障排除部分
