"""Context compression service — incremental message summarization.

Ported from src/utils/context/context.ts.
Uses tiktoken for accurate token counting (replaces Math.ceil(len/2.5)).
"""

import json
from dataclasses import dataclass

import httpx
import tiktoken

from app.config import settings

MAX_CONTEXT_TOKENS = settings.max_context_tokens  # default 80K
RECENT_WINDOW_SIZE = settings.recent_window_size   # default 20

# Use cl100k_base encoding (GPT-4/DeepSeek compatible)
_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Accurate token count using tiktoken."""
    if not text:
        return 0
    return len(_encoder.encode(text))


@dataclass
class ContextParams:
    system_prompt: str
    history: list[dict]  # [{"role": "user/assistant", "content": "..."}]
    user_content: str
    existing_summary: str | None = None
    summarized_count: int = 0


@dataclass
class BuildContextResult:
    messages: list[dict]
    new_summary: dict | None = None  # {"text": "...", "covered_count": N}


def _format_messages_for_summary(msgs: list[dict]) -> str:
    """Convert messages to a human-readable format for summarization."""
    return "\n\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
        for m in msgs
    )


async def generate_summary(
    existing_summary: str | None,
    new_messages: list[dict],
) -> str:
    """Call DeepSeek flash model to generate/merge a conversation summary."""
    conversation_text = _format_messages_for_summary(new_messages)

    if existing_summary:
        prompt = (
            f"之前的对话摘要：\n{existing_summary}\n\n"
            f"新的对话内容：\n{conversation_text}\n\n"
            f"请将以上内容合并为一个完整的对话摘要（200字以内），"
            f"保留关键事实、用户偏好、重要决策和待办事项。只输出摘要文本。"
        )
    else:
        prompt = (
            f"请将以下对话内容压缩为简洁的摘要（200字以内），"
            f"保留所有关键事实、用户偏好、重要决策和待办事项。只输出摘要文本。\n\n"
            f"{conversation_text}"
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        response = await client.post(
            f"{settings.deepseek_base_url}/chat/completions",
            json={
                "model": "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": "你是一个对话摘要助手，只输出简洁的摘要。"},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "max_tokens": 400,
            },
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def build_context(params: ContextParams) -> BuildContextResult:
    """Build the LLM message list with automatic context compression.

    Algorithm (identical to frontend version):
    1. Take the 'history' and slice off the first 'summarized_count'
       messages (already captured by existing summary). The remainder
       is 'unsummarized_history'.
    2. Estimate total tokens.
    3. If under threshold → return full context.
    4. If over threshold → split into recent (keep verbatim) and
       early (summarize), call DeepSeek flash to merge with existing
       summary, return compressed messages.
    """
    system_prompt = params.system_prompt
    history = params.history
    user_content = params.user_content
    existing_summary = params.existing_summary
    summarized_count = params.summarized_count

    # Messages not yet covered by summary
    unsummarized = history[summarized_count:]

    # Token estimation
    history_tokens = sum(count_tokens(m["content"]) for m in unsummarized)
    system_tokens = count_tokens(system_prompt)
    summary_tokens = count_tokens(existing_summary) if existing_summary else 0
    user_tokens = count_tokens(user_content)
    total_tokens = system_tokens + summary_tokens + history_tokens + user_tokens

    # Under threshold: return full context
    if total_tokens <= MAX_CONTEXT_TOKENS:
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if existing_summary:
            messages.append({
                "role": "system",
                "content": f"[历史对话摘要]\n{existing_summary}",
            })
        messages.extend(unsummarized)
        messages.append({"role": "user", "content": user_content})
        return BuildContextResult(messages=messages)

    # Over threshold: split into recent (keep) and early (summarize)
    recent = unsummarized[-RECENT_WINDOW_SIZE:]
    new_early = unsummarized[:-RECENT_WINDOW_SIZE]

    # No new messages to summarize → just use sliding window
    if len(new_early) == 0:
        messages = [{"role": "system", "content": system_prompt}]
        if existing_summary:
            messages.append({
                "role": "system",
                "content": f"[历史对话摘要]\n{existing_summary}",
            })
        messages.extend(recent)
        messages.append({"role": "user", "content": user_content})
        return BuildContextResult(messages=messages)

    # Call summary API
    try:
        new_summary_text = await generate_summary(existing_summary, new_early)
        new_covered_count = summarized_count + len(new_early)

        return BuildContextResult(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": f"[历史对话摘要]\n{new_summary_text}"},
                *recent,
                {"role": "user", "content": user_content},
            ],
            new_summary={
                "text": new_summary_text,
                "covered_count": new_covered_count,
            },
        )
    except Exception:
        # Fallback: sliding window without compression
        import logging
        logging.getLogger(__name__).warning("摘要生成失败，降级为滑窗截断")

        messages = [{"role": "system", "content": system_prompt}]
        if existing_summary:
            messages.append({
                "role": "system",
                "content": f"[历史对话摘要]\n{existing_summary}",
            })
        messages.extend(recent)
        messages.append({"role": "user", "content": user_content})
        return BuildContextResult(messages=messages)
