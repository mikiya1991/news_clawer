# Ubuntu 安装包发布手册

本文记录 xclawer 项目在 Ubuntu 上的打包、安装、升级与运维流程。

## 1. 构建

### 环境要求

- Ubuntu 环境（物理机 / VM），**或**任意平台 + Docker Desktop
- 构建环境与目标系统的 Ubuntu 版本建议一致（包内 venv 的系统 Python 与构建系统绑定）

### 构建命令

```bash
# 在 Ubuntu 上直接构建
./build_deb.sh 1.0.0

# 在 Mac/Windows 上用 Docker 构建
./build_deb_docker.sh 1.0.0
# 目标系统是 24.04 时指定镜像版本：
XCLAWER_BUILD_IMAGE=ubuntu:24.04 ./build_deb_docker.sh 1.0.0
```

### 产物

```
dist/xclawer_1.0.0_amd64.deb     # 约 200MB（含打好依赖的 venv）
```

包内**不包含** Chromium（安装时由 postinst 下载到数据目录）和 `.env`（安装时生成模板）。

检查包内容：

```bash
dpkg -c dist/xclawer_1.0.0_amd64.deb | head -30
dpkg -I dist/xclawer_1.0.0_amd64.deb    # 包元信息
```

## 2. 安装

```bash
sudo dpkg -i dist/xclawer_1.0.0_amd64.deb
# 报依赖缺失时：
sudo apt-get install -f
```

安装过程（postinst）：

1. 创建系统用户 `_xclawer`（nologin）
2. 创建数据目录 `/var/lib/xclawer`，配置目录 `/etc/xclawer`
3. 下载 Chromium 到 `/var/lib/xclawer/ms-playwright`（约 150MB，需联网）
4. 生成 `/etc/xclawer/.env` 模板、种子调度配置（60 分钟采集，自动启动）
5. 启用并启动 systemd 服务

安装后配置：

```bash
sudo vi /etc/xclawer/.env        # 填入 DEEPSEEK_API_KEY（及 PUSH_PROVIDER/PUSH_TOKEN、RSS_FEEDS）
sudo systemctl restart xclawer
# 浏览器访问 http://<服务器IP>:5001
```

## 3. 升级

```bash
sudo dpkg -i dist/xclawer_1.1.0_amd64.deb   # 覆盖安装即可
```

- 程序与 venv 随包整体替换
- 数据（`/var/lib/xclawer`）、配置（`/etc/xclawer/.env`）、Chromium 均保留（postinst 仅在文件缺失时创建）
- postinst 结束时会自动 `systemctl restart xclawer`

## 4. 目录布局

| 路径 | 内容 | 升级时 |
|------|------|--------|
| `/usr/lib/xclawer/` | 程序 + venv（只读） | 覆盖 |
| `/var/lib/xclawer/` | tweets.db、browser_state、ms-playwright、logs、调度状态 | 保留 |
| `/etc/xclawer/.env` | API key、推送、RSS 配置 | 保留 |
| `/lib/systemd/system/xclawer.service` | systemd 服务定义 | 覆盖 |

路径重定位由环境变量 `XCLAWER_DATA_DIR` 驱动（systemd 单元中设置为 `/var/lib/xclawer`），代码侧无需改动。

## 5. 服务管理

```bash
systemctl status xclawer              # 状态
sudo systemctl restart xclawer        # 重启（改配置后）
journalctl -u xclawer -f              # 实时日志
journalctl -u xclawer -n 100          # 最近 100 行
```

- 服务以 `_xclawer` 用户运行，`Restart=always`（崩溃自动拉起），开机自启
- 服务内已设置 `XCLAWER_DEBUG=0`（不暴露 Werkzeug debugger）；数据目录内 `logs/scraper.log` 为业务日志

## 6. 卸载

```bash
sudo apt remove xclawer          # 卸载程序，保留数据
sudo apt purge xclawer           # 连同配置模板
sudo rm -rf /var/lib/xclawer     # 彻底删除数据（数据库、浏览器会话、日志）
```

## 7. 常见问题

### Chromium 下载失败 / 安装中断
重装一次即可（postinst 幂等）；或手动执行：

```bash
sudo PLAYWRIGHT_BROWSERS_PATH=/var/lib/xclawer/ms-playwright \
    /usr/lib/xclawer/venv/bin/playwright install --with-deps chromium
sudo chown -R _xclawer:_xclawer /var/lib/xclawer/ms-playwright
```

### 服务起不来
```bash
journalctl -u xclawer -n 50
```
常见原因：端口 5001 被占；`/etc/xclawer/.env` 权限不对（应为 640，属主 `_xclawer`）；Python 与构建机版本不匹配（用同版本镜像重新构建）。

### 登录 X / 手动抓取
需要桌面环境：按钮会弹出可见浏览器窗口。无图形界面的服务器上登录按钮会提示不可用。

### 查数据库
```bash
sudo sqlite3 /var/lib/xclawer/tweets.db "SELECT COUNT(*) FROM tweets;"
```

## 8. 发布检查清单

每次发版前逐项确认：

- [ ] 代码已 commit（构建脚本会原样拷贝工作区，包括未提交改动）
- [ ] 版本号递增（`build_deb.sh <版本>` 写入 control）
- [ ] 构建镜像与目标 Ubuntu 版本一致
- [ ] `dpkg -c` 检查包内无 `.env`、无数据库、无浏览器会话
- [ ] 全新机器安装验证 + 老版本机器升级验证
- [ ] 安装后跑通：登录 → 手动抓取 → AI 评分 → 新闻循环
