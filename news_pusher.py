"""
News pusher module
Pushes a markdown digest of top-scored news to WeChat via Server酱 or PushPlus.
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests

import config

logger = logging.getLogger(__name__)

SERVERCHAN_SEND_URL = 'https://sctapi.ftqq.com/{sendkey}.send'
PUSHPLUS_SEND_URL = 'https://www.pushplus.plus/send'


def _mask_token(token: str) -> str:
    """Mask push token for safe logging"""
    if not token:
        return "(empty)"
    return f"{token[:4]}***" if len(token) > 4 else "***"


def _build_digest_markdown(items: List[Dict[str, Any]], cycle_time: datetime,
                           scanned_count: int) -> str:
    """Build the digest markdown body"""
    lines = [f"## 📡 新闻雷达快报 {cycle_time.strftime('%m-%d %H:%M')}", ""]
    lines.append(f"本次扫描 {scanned_count} 条，为您精选 Top {len(items)}（≥{config.NEWS_SCORE_THRESHOLD} 分）")
    lines.append("")

    for rank, item in enumerate(items, 1):
        source_label = 'RSS' if item.get('source') == 'rss' else 'X'
        lines.append(f"**{rank}. [{item.get('score', 0)}] {item.get('title', '')}**")
        lines.append(f"> 来源: {source_label} · {item.get('source_name', '')} ｜ "
                     f"摘要: {item.get('summary', '')}")
        if item.get('reasons'):
            lines.append(f"> 理由: {'；'.join(item['reasons'])}")
        if item.get('url', '').startswith('http'):
            lines.append(f"🔗 [查看原文]({item['url']})")
        lines.append("---")
        lines.append("")

    return '\n'.join(lines)


def _send_serverchan(token: str, title: str, desp: str) -> bool:
    """Send via Server酱, returns True on success"""
    response = requests.post(
        SERVERCHAN_SEND_URL.format(sendkey=token),
        data={'title': title[:32], 'desp': desp},
        timeout=config.NEWS_HTTP_TIMEOUT
    )
    data = response.json()
    if data.get('code') == 0:
        return True
    logger.error(f"Server酱 push failed: {data.get('message', response.text[:200])}")
    return False


def _send_pushplus(token: str, title: str, content: str) -> bool:
    """Send via PushPlus, returns True on success"""
    response = requests.post(
        PUSHPLUS_SEND_URL,
        json={'token': token, 'title': title, 'content': content,
              'template': 'markdown'},
        timeout=config.NEWS_HTTP_TIMEOUT
    )
    data = response.json()
    if data.get('code') == 200:
        return True
    logger.error(f"PushPlus push failed: {data.get('msg', response.text[:200])}")
    return False


def push_digest(items: List[Dict[str, Any]], scanned_count: int,
                provider: str = None, token: str = None) -> bool:
    """
    Push a digest of scored news items to WeChat.

    Args:
        items: Items to include, each with score/summary/reasons parsed
        scanned_count: Total items scanned this cycle (for the digest header)
        provider: Override config.PUSH_PROVIDER
        token: Override config.PUSH_TOKEN

    Returns:
        True if pushed successfully, False if skipped or failed
    """
    provider = provider or config.PUSH_PROVIDER
    token = token or config.PUSH_TOKEN

    if not provider:
        logger.info("Push disabled (PUSH_PROVIDER empty), skipping")
        return False

    if not token:
        logger.warning(f"PUSH_PROVIDER={provider} but PUSH_TOKEN is empty, "
                       f"skipping push")
        return False

    if not items:
        logger.info("No items above threshold, skipping push")
        return False

    # reasons is stored as JSON string; parse for display
    display_items = []
    for item in items:
        display = dict(item)
        reasons = display.get('reasons', '')
        if isinstance(reasons, str):
            try:
                display['reasons'] = json.loads(reasons)
            except (json.JSONDecodeError, ValueError):
                display['reasons'] = []
        display_items.append(display)

    cycle_time = datetime.now()
    title = f"📡 新闻雷达快报 {cycle_time.strftime('%m-%d %H:%M')}"
    body = _build_digest_markdown(display_items, cycle_time, scanned_count)

    try:
        if provider == 'serverchan':
            success = _send_serverchan(token, title, body)
        elif provider == 'pushplus':
            success = _send_pushplus(token, title, body)
        else:
            logger.error(f"Unknown PUSH_PROVIDER: {provider}")
            return False

        if success:
            logger.info(f"Digest pushed via {provider}: {len(items)} items "
                        f"(token {_mask_token(token)})")
        return success

    except Exception as e:
        logger.error(f"Push failed via {provider} (token {_mask_token(token)}): {e}")
        return False
