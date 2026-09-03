"""
Tweet summarizer module
Generates one-line Chinese AI summaries for English tweets (batched via DeepSeek).
Fail-open: any failure returns None and tweets are stored without summaries.
"""
import logging
import re
from typing import List, Dict, Any, Optional

import config
from news_scorer import call_deepseek

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是推特内容总结助手。把英文推文总结成一句话中文注释，要求：
- 提炼核心信息：谁、发生了什么、关键数据或观点
- 一句话，不超过 60 个字，中文
- 保留专有名词（公司、人名、产品名）的英文原文
- 如果是纯情绪/闲聊内容，如实概括

只输出一个 JSON 对象，不要输出任何其他文字，格式严格为：
{"items": [{"id": 序号, "summary": "一句话中文总结"}]}
id 必须与输入推文的编号一致，不得遗漏任何一条。"""


def is_english_text(text: str) -> bool:
    """
    Heuristic: treat text as English when ASCII letters dominate
    (allows short Chinese interjections inside English tweets)
    """
    if not text:
        return False
    ascii_letters = len(re.findall(r'[A-Za-z]', text))
    cjk_chars = len(re.findall(r'[一-鿿]', text))
    total = ascii_letters + cjk_chars
    if total == 0:
        return False
    return ascii_letters / total > 0.7


def summarize_tweets(tweets: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    Generate one-line Chinese summaries for English tweets.

    Args:
        tweets: Tweet dicts with at least 'id' and 'text'

    Returns:
        {tweet_id: summary} for successfully summarized tweets,
        or None if the whole batch failed (fail-open).
    """
    if not tweets:
        return {}

    if not config.DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY is not set, skipping AI summaries")
        return None

    lines = []
    for i, tweet in enumerate(tweets, 1):
        text = str(tweet.get('text', '')).strip()
        if len(text) > 300:
            text = text[:300] + '...'
        lines.append(f"{i}. {text}")
    user_prompt = "以下是要总结的推文，编号即为 JSON 输出中的 id：\n\n" + '\n\n'.join(lines)

    logger.info(f"Summarizing {len(tweets)} English tweets (batch mode)")
    result = call_deepseek(
        [{'role': 'system', 'content': SYSTEM_PROMPT},
         {'role': 'user', 'content': user_prompt}],
        response_format=True
    )

    if not result or not isinstance(result.get('items'), list):
        logger.error("Summarizer response missing 'items' list (fail-open)")
        return None

    by_id: Dict[int, str] = {}
    for entry in result['items']:
        if isinstance(entry, dict) and entry.get('id') is not None:
            try:
                summary = str(entry.get('summary', '')).strip()[:120]
                if summary:
                    by_id[int(entry['id'])] = summary
            except (TypeError, ValueError):
                continue

    summaries = {}
    for i, tweet in enumerate(tweets, 1):
        if i in by_id:
            summaries[str(tweet['id'])] = by_id[i]

    logger.info(f"Summarized {len(summaries)}/{len(tweets)} tweets")
    return summaries
