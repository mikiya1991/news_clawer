# 快速开始指南

## 1 分钟快速启动

### 首次使用

#### Step 1: 安装依赖
```bash
cd /Users/mikiya/workspace/new_clawer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

#### Step 2: 登录 X.com
```bash
python3 main.py --login
```
- 浏览器会打开，用你的账号登录 X.com
- 登录成功后，按 Enter

#### Step 3: 运行首次采集
```bash
python3 main.py --collect
```
浏览器会自动打开，采集推文并存入数据库

### 查看采集结果
```bash
python3 main.py --stats
```

---

## 定期自动采集设置

### 方法 1: Python schedule 库（推荐）

```bash
pip install schedule
```

创建 `scheduler.py`：
```python
import schedule
import time
import subprocess

def collect_tweets():
    subprocess.run(['python3', 'main.py', '--collect', '--headless'])

# 每小时运行一次（可修改频率）
schedule.every().hour.do(collect_tweets)

print("Scheduler started. Press Ctrl+C to stop.")
while True:
    schedule.run_pending()
    time.sleep(60)
```

运行（后台模式）：
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

### 方法 2: 使用提供的脚本（传统 cron）

```bash
chmod +x cron_job.sh
./cron_job.sh
```
根据提示选择采集频率（每小时/6小时/12小时/每天）

---

## 常用命令

| 命令 | 说明 |
|------|------|
| `python3 main.py --login` | 登录 X.com（首次或重新登录） |
| `python3 main.py --collect` | 运行数据采集（可见浏览器） |
| `python3 main.py --collect --headless` | 后台采集（用于定时任务） |
| `python3 main.py --stats` | 查看数据统计 |
| `python3 main.py --collect --iterations 10` | 采集时滚动 10 次 |
| `tail -f logs/scraper.log` | 实时查看日志 |

---

## 数据库查询

查看最近采集的 10 条推文：

```bash
sqlite3 tweets.db "SELECT username, text, like_count FROM tweets ORDER BY collected_at DESC LIMIT 10;"
```

---

## Web 可视化界面

启动 Web Dashboard 查看和筛选采集的推文：

```bash
cd web/
source ../venv/bin/activate
pip install -r requirements.txt
python app.py
```

打开浏览器访问: **http://localhost:5001**

### 功能特点
- **排序**: 按时间/用户名/点赞数/浏览量/转发数排序
- **筛选**: 按用户名筛选、搜索推文内容
- **分页**: 每页 50 条，支持翻页浏览
- **统计**: 实时显示总推文数、用户数、总点赞数

### 生产部署

使用 Gunicorn:
```bash
cd web/
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 wsgi:app
```

---

## 文件说明

- `main.py` - 主程序，运行 `python3 main.py -h` 查看所有选项
- `tweets.db` - SQLite 数据库，存储所有推文
- `logs/scraper.log` - 执行日志
- `browser_state/` - 浏览器状态（登录信息）
- `debug_screenshots/` - 调试截图
- `scheduler.py` - Python schedule 库定时调度器
- `web/` - Web Dashboard 可视化界面
  - `app.py` - Flask 后端服务
  - `templates/index.html` - 前端页面
  - `static/js/app.js` - 前端交互逻辑

---

## 问题排查

**问题**: 提示 "Not logged in"
```bash
python3 main.py --login
```

**问题**: 定时任务未运行
- 检查进程是否在运行：`ps aux | grep scheduler.py`
- 查看调度器日志：`tail -f logs/scheduler.log`
- 重新启动调度器：`nohup python3 scheduler.py > logs/scheduler.log 2>&1 &`

**问题**: 推文采集为空
- 检查网络连接
- 查看 `debug_screenshots/` 中的截图
- 查看 `logs/scraper.log` 中的错误信息

---

## 下一步

- 阅读 [README.md](README.md) 了解更多功能和配置
- 编辑 `config.py` 调整采集参数
- 使用 `python3 main.py --help` 查看所有选项
