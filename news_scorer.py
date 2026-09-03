"""
News scorer module
Scores news items (0-100) via the DeepSeek API. One batched request per cycle,
with a per-item fallback if batch parsing fails.
"""
import json
import logging
import time
from typing import List, Dict, Any, Optional

import requests

import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的新闻质量评分助手。对每一条新闻按以下维度打分（总分 0-100）：
- 信息量 (0-30)：是否包含具体事实、数据、细节，而非空泛观点
- 可信度 (0-25)：来源权威性与内容可验证性
- 时效性 (0-20)：是否新近、与当前热点相关
- 写作质量 (0-15)：结构清晰、表达准确
- 重要性 (0-10)：对读者的价值与影响范围

只输出一个 JSON 对象，不要输出任何其他文字，格式严格为：
{"items": [{"id": 序号, "score": 整数0-100, "summary": "一句话中文摘要", "reasons": ["理由1", "理由2"]}]}
id 必须与输入新闻的编号一致，不得遗漏任何一条。"""

SINGLE_ITEM_SYSTEM_PROMPT = """你是一个专业的新闻质量评分助手。对这条新闻按以下维度打分（总分 0-100）：
- 信息量 (0-30)：是否包含具体事实、数据、细节，而非空泛观点
- 可信度 (0-25)：来源权威性与内容可验证性
- 时效性 (0-20)：是否新近、与当前热点相关
- 写作质量 (0-15)：结构清晰、表达准确
- 重要性 (0-10)：对读者的价值与影响范围

只输出一个 JSON 对象，不要输出任何其他文字，格式严格为：
{"score": 整数0-100, "summary": "一句话中文摘要", "reasons": ["理由1", "理由2"]}"""


def _mask_key(key: str) -> str:
    """Mask API key for safe logging"""
    if not key:
        return "(empty)"
    return f"{key[:4]}***" if len(key) > 4 else "***"


def extract_json(text: str) -> Optional[Any]:
    """Extract a JSON object from model output, tolerating fences and noise"""
    if not text:
        return None
    text = text.strip()

    # Strip ```json fences
    if text.startswith('```'):
        lines = text.split('\n')
        lines = lines[1:] if lines and lines[0].startswith('```') else lines
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        text = '\n'.join(lines).strip()

    # Direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Brace scan: first { to last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _coerce_score(value: Any) -> Optional[int]:
    """Coerce a score to int 0-100; None if invalid"""
    try:
        score = int(round(float(value)))
        return max(0, min(100, score))
    except (TypeError, ValueError):
        return None


def call_deepseek(messages: List[Dict[str, str]],
                  response_format: bool = False) -> Optional[Dict[str, Any]]:
    """
    Call DeepSeek chat completions with retry

    Args:
        messages: Chat messages
        response_format: Enable json_object response format

    Returns:
        Parsed JSON response, or None on failure
    """
    if not config.DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY is not set. Cannot score items.")
        return None

    payload = {
        'model': config.DEEPSEEK_MODEL,
        'temperature': 0.3,
        'messages': messages,
    }
    if response_format:
        payload['response_format'] = {'type': 'json_object'}

    headers = {
        'Authorization': f"Bearer {config.DEEPSEEK_API_KEY}",
        'Content-Type': 'application/json',
    }
    url = f"{config.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"

    for attempt in range(config.MAX_RETRIES):
        try:
            response = requests.post(url, json=payload, headers=headers,
                                     timeout=config.NEWS_HTTP_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                return extract_json(content)

            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                delay = float(retry_after) if retry_after else config.RETRY_DELAY
                logger.warning(f"DeepSeek rate limited (429), retrying in {delay}s")
                time.sleep(delay)
                continue

            if response.status_code >= 500:
                logger.warning(f"DeepSeek server error ({response.status_code}), "
                               f"attempt {attempt + 1}/{config.MAX_RETRIES}")
                time.sleep(config.RETRY_DELAY)
                continue

            # 4xx: auth or request error - don't retry
            logger.error(f"DeepSeek request failed ({response.status_code}): "
                         f"{response.text[:200]}")
            return None

        except requests.RequestException as e:
            logger.warning(f"DeepSeek request error (attempt {attempt + 1}/"
                           f"{config.MAX_RETRIES}): {e}")
            time.sleep(config.RETRY_DELAY)

    logger.error(f"DeepSeek call failed after {config.MAX_RETRIES} attempts "
                 f"(key {_mask_key(config.DEEPSEEK_API_KEY)})")
    return None


def _format_item_text(item: Dict[str, Any], index: int) -> str:
    """Format one item for the prompt"""
    content = str(item.get('content', '')).strip()
    # Truncate very long content to keep the batch compact
    if len(content) > 400:
        content = content[:400] + '...'
    line = f"{index}. [{item.get('title', '')}] {content}"
    if item.get('source') == 'x' and item.get('like_count'):
        line += f"（点赞数: {item['like_count']}）"
    return line


def _score_batch(items: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """
    Score all items in one batched request. Returns a list aligned with items,
    each entry {score, summary, reasons} or None for failed entries.
    Returns None if the whole batch fails.
    """
    numbered = '\n\n'.join(_format_item_text(item, i + 1) for i, item in enumerate(items))
    user_prompt = f"以下是要评分的新闻，编号即为 JSON 输出中的 id：\n\n{numbered}"

    result = call_deepseek(
        [{'role': 'system', 'content': SYSTEM_PROMPT},
         {'role': 'user', 'content': user_prompt}],
        response_format=True
    )

    if not result or not isinstance(result.get('items'), list):
        logger.error("DeepSeek batch response missing 'items' list")
        return None

    raw_items = result['items']
    by_id = {int(entry.get('id', -1)): entry for entry in raw_items
             if isinstance(entry, dict) and entry.get('id') is not None}

    scored: List[Optional[Dict[str, Any]]] = [None] * len(items)
    for i, item in enumerate(items):
        entry = by_id.get(i + 1)
        if not entry:
            logger.warning(f"Item {i + 1} missing from batch response")
            continue
        score = _coerce_score(entry.get('score'))
        if score is None:
            logger.warning(f"Item {i + 1} has invalid score, skipped")
            continue
        reasons = entry.get('reasons', [])
        if not isinstance(reasons, list):
            reasons = []
        reasons = [str(r) for r in reasons][:5]
        scored[i] = {
            'score': score,
            'summary': str(entry.get('summary', ''))[:200],
            'reasons': json.dumps(reasons, ensure_ascii=False),
        }

    if not any(s is not None for s in scored):
        return None
    return scored


def _score_single(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Score one item individually (fallback path)"""
    user_prompt = _format_item_text(item, 1)
    result = call_deepseek(
        [{'role': 'system', 'content': SINGLE_ITEM_SYSTEM_PROMPT},
         {'role': 'user', 'content': f"请为这条新闻评分：\n\n{user_prompt}"}],
        response_format=True
    )
    if not result:
        return None
    score = _coerce_score(result.get('score'))
    if score is None:
        return None
    reasons = result.get('reasons', [])
    if not isinstance(reasons, list):
        reasons = []
    return {
        'score': score,
        'summary': str(result.get('summary', ''))[:200],
        'reasons': json.dumps([str(r) for r in reasons][:5], ensure_ascii=False),
    }


def score_items(items: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """
    Score a list of news items.

    Args:
        items: Normalized item dicts from news_fetcher

    Returns:
        List aligned with items: {score, summary, reasons} or None per entry.
        Returns None if scoring failed completely.
    """
    if not items:
        return []

    if not config.DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY is not set. Cannot score items.")
        return None

    logger.info(f"Scoring {len(items)} items via DeepSeek (batch mode)")
    scored = _score_batch(items)

    if scored is None:
        logger.warning("Batch scoring failed, falling back to per-item scoring")
        scored = []
        for i, item in enumerate(items):
            single = _score_single(item)
            if single is not None:
                logger.info(f"Item {i + 1} scored individually: {single['score']}")
            scored.append(single)

        if not any(s is not None for s in scored):
            logger.error("Scoring failed completely (batch and per-item)")
            return None

    return scored
