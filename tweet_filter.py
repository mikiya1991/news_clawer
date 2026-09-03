"""
Tweet filter module
Judges whether scraped X tweets are worth collecting via DeepSeek (batched).
Unimportant tweets are discarded before they reach the database.
Fail-open: any failure returns None and the caller stores everything.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple, Set

import config
from news_scorer import call_deepseek

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是推文价值判断助手。判断每条推文是否值得收集保存。

值得保留（keep=true）：
- 包含新闻、行业资讯、数据、公告等实质信息
- 有独到观点、深度分析、专业见解
- 分享有价值的内容（文章、研究、工具、教程）

不值得保留（keep=false）：
- 纯闲聊、日常寒暄、情绪发泄
- 无信息量的互动（打招呼、简单感谢、表情回复）
- 纯转发或引用且无任何补充观点
- 广告、抽奖、刷屏内容

只输出一个 JSON 对象，不要输出任何其他文字，格式严格为：
{"items": [{"id": 序号, "keep": true或false, "reason": "简短理由"}]}
id 必须与输入推文的编号一致，不得遗漏任何一条。"""


def filter_tweets(tweets: List[Dict[str, Any]]) -> Optional[Tuple[Set[str], List[Tuple[str, str]]]]:
    """
    Judge which tweets are worth keeping.

    Args:
        tweets: Tweet dicts with at least 'id', 'username', 'text'

    Returns:
        (kept_ids, [(discarded_id, reason)]) or None if filtering failed
        completely (caller should then store everything - fail-open).
        Entries missing from the model response default to kept.
    """
    if not tweets:
        return set(), []

    if not config.DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY is not set, skipping AI filter "
                       "(fail-open: store all)")
        return None

    # Build numbered prompt, truncating long tweets
    lines = []
    for i, tweet in enumerate(tweets, 1):
        text = str(tweet.get('text', '')).strip()
        if len(text) > 200:
            text = text[:200] + '...'
        lines.append(f"{i}. @{tweet.get('username', '')}: {text}")
    user_prompt = "以下是要判断的推文，编号即为 JSON 输出中的 id：\n\n" + '\n\n'.join(lines)

    logger.info(f"AI filtering {len(tweets)} tweets (batch mode)")
    result = call_deepseek(
        [{'role': 'system', 'content': SYSTEM_PROMPT},
         {'role': 'user', 'content': user_prompt}],
        response_format=True
    )

    if not result or not isinstance(result.get('items'), list):
        logger.error("AI filter response missing 'items' list (fail-open)")
        return None

    by_id: Dict[int, Dict[str, Any]] = {}
    for entry in result['items']:
        if isinstance(entry, dict) and entry.get('id') is not None:
            try:
                by_id[int(entry['id'])] = entry
            except (TypeError, ValueError):
                continue

    kept_ids: Set[str] = set()
    discarded: List[Tuple[str, str]] = []

    for i, tweet in enumerate(tweets, 1):
        tweet_id = str(tweet['id'])
        entry = by_id.get(i)
        keep = True  # missing/unparseable entry -> keep (fail-open per item)
        reason = ''
        if entry is not None:
            if entry.get('keep') is False:
                keep = False
                reason = str(entry.get('reason', ''))[:200]
        if keep:
            kept_ids.add(tweet_id)
        else:
            discarded.append((tweet_id, reason))

    logger.info(f"AI filter result: kept {len(kept_ids)}, discarded {len(discarded)}")
    return kept_ids, discarded


SCORE_SYSTEM_PROMPT = """你是推文价值评分助手。综合评估每条推文的价值，总分 0-100 整数：
- 信息含量 (0-35)：是否包含事实、数据、干货、独到观点，而非空泛内容
- 表达质量 (0-15)：原创性、清晰度
- 影响力 (0-30)：参考给出的互动数据（点赞/转发/浏览）判断关注度与传播价值
- 长期价值 (0-20)：是否值得收藏、回顾，有持久参考意义

只输出一个 JSON 对象，不要输出任何其他文字，格式严格为：
{"items": [{"id": 序号, "score": 整数0-100, "summary": "一句话中文总结"}]}
id 必须与输入推文的编号一致，不得遗漏任何一条。"""


def score_tweets(tweets: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """
    Score tweets 0-100 (content value + engagement-informed influence).

    Args:
        tweets: Tweet dicts with at least 'id', 'username', 'text'

    Returns:
        List aligned with tweets: {score, summary} or None per entry.
        Returns None if scoring failed completely (fail-open).
    """
    if not tweets:
        return []

    if not config.DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY is not set, skipping tweet scoring")
        return None

    lines = []
    for i, tweet in enumerate(tweets, 1):
        text = str(tweet.get('text', '')).strip()
        if len(text) > 250:
            text = text[:250] + '...'
        engagement = (f"（点赞:{tweet.get('like_count', 0)} "
                      f"转发:{tweet.get('retweet_count', 0)} "
                      f"浏览:{tweet.get('view_count', 0)}）")
        lines.append(f"{i}. @{tweet.get('username', '')} {engagement}: {text}")
    user_prompt = "以下是要评分的推文，编号即为 JSON 输出中的 id：\n\n" + '\n\n'.join(lines)

    logger.info(f"Scoring {len(tweets)} tweets (batch mode)")
    result = call_deepseek(
        [{'role': 'system', 'content': SCORE_SYSTEM_PROMPT},
         {'role': 'user', 'content': user_prompt}],
        response_format=True
    )

    if not result or not isinstance(result.get('items'), list):
        logger.warning("Batch tweet scoring failed, falling back to per-item scoring")
        scored = [_score_single_tweet(t) for t in tweets]
        if not any(s is not None for s in scored):
            logger.error("Tweet scoring failed completely (batch and per-item)")
            return None
        return scored

    by_id: Dict[int, Dict[str, Any]] = {}
    for entry in result['items']:
        if isinstance(entry, dict) and entry.get('id') is not None:
            try:
                by_id[int(entry['id'])] = entry
            except (TypeError, ValueError):
                continue

    scored: List[Optional[Dict[str, Any]]] = [None] * len(tweets)
    for i in range(len(tweets)):
        entry = by_id.get(i + 1)
        if not entry:
            continue
        try:
            score = max(0, min(100, int(round(float(entry.get('score'))))))
        except (TypeError, ValueError):
            continue
        scored[i] = {
            'score': score,
            'summary': str(entry.get('summary', '')).strip()[:120],
        }

    if not any(s is not None for s in scored):
        return None
    return scored


def _score_single_tweet(tweet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Score one tweet individually (fallback for batches rejected by content policy)"""
    text = str(tweet.get('text', '')).strip()
    if len(text) > 250:
        text = text[:250] + '...'
    engagement = (f"（点赞:{tweet.get('like_count', 0)} "
                  f"转发:{tweet.get('retweet_count', 0)} "
                  f"浏览:{tweet.get('view_count', 0)}）")
    user_prompt = (f"请为这条推文评分：\n\n"
                   f"1. @{tweet.get('username', '')} {engagement}: {text}")

    result = call_deepseek(
        [{'role': 'system', 'content': SCORE_SYSTEM_PROMPT},
         {'role': 'user', 'content': user_prompt}],
        response_format=True
    )
    if not result:
        return None
    entry = result.get('items', [{}])
    entry = entry[0] if isinstance(entry, list) and entry else {}
    try:
        score = max(0, min(100, int(round(float(entry.get('score'))))))
    except (TypeError, ValueError):
        return None
    return {
        'score': score,
        'summary': str(entry.get('summary', '')).strip()[:120],
    }
