"""Memory service --- episodic memory + user profile.

- Episodic memory: ChromaDB collection (cross-conversation semantic retrieval)
- User profile: SQLite single-row table (long-term user traits)
"""

from __future__ import annotations

import chromadb
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import async_session
from app.models.memory import EpisodicMemoryRecord, UserMemoryFact, UserProfile
from app.rag.embedder import get_embedder
from app.services.llm_provider import create_light_openrouter_llm

logger = logging.getLogger(__name__)

MEMORY_COLLECTION_NAME = "episodic_memories"
EPISODIC_DISTANCE_THRESHOLD = 0.85

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class EpisodicMemory:
    """A single episodic memory extracted from a conversation."""

    id: str
    conversation_id: str
    summary: str
    embedding_id: str = ""
    facts: list[dict] = field(default_factory=list)  # [{fact, category, importance}]
    importance: int = 5
    created_at: int = 0
    source_message_start_id: int | None = None
    source_message_end_id: int | None = None
    distance: float | None = None


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

_collection: chromadb.Collection | None = None


def _get_collection():
    """Lazy-init the episodic_memories ChromaDB collection."""
    global _collection
    if _collection is not None:
        return _collection

    from app.services.rag_service import get_chroma_client

    client = get_chroma_client()
    _collection = client.get_or_create_collection(
        name=MEMORY_COLLECTION_NAME,
        embedding_function=None,  # Pre-compute embeddings manually
    )
    logger.info("Episodic memory collection ready: %s", MEMORY_COLLECTION_NAME)
    return _collection


# ---------------------------------------------------------------------------
# Flash LLM for memory extraction
# ---------------------------------------------------------------------------

_memory_llm = None


def _get_memory_llm():
    global _memory_llm
    if _memory_llm is None:
        _memory_llm = create_light_openrouter_llm(max_tokens=500, temperature=0.3)
    return _memory_llm


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """分析以下对话，提取有跨会话检索价值的关键事件，以 JSON 格式返回（只输出 JSON，不要任何其他文字）：

你的职责是捕捉**事件**——用户经历了什么、做了什么决定、给了什么反馈、遇到了什么困扰——而不是记录用户的长期属性。
长期属性（疾病、过敏、用药、偏好、目标）由用户画像系统专门管理，你不需要重复保存。

{{
  "summary": "一段150字以内的事件摘要。描述本轮对话中发生了什么：用户问了什么核心问题、做了哪些决定或行动、对建议有何反馈、达成了什么阶段性结论。以事件为中心，不以用户属性为中心。",
  "facts": [
    {{"fact": "用户对上一轮的低盐饮食建议反馈执行困难，希望换成更实际的方案", "category": "user_feedback", "importance": 8}},
    {{"fact": "用户计划下周开始每天快走30分钟", "category": "action_or_plan", "importance": 7}}
  ]
}}

category 可选值：
- action_or_plan：用户采取的行动、做的决定、制定的计划
- user_feedback：用户对之前建议的反馈（有效/无效/难以执行/需要调整）
- advice_given：本轮给用户的关键建议或方案
- outcome_or_result：阶段性结果、指标变化、达成的结论
- concern_or_question：用户的核心困扰、关键疑问、反复提到的问题

importance 1-10，10 为最重要。

规则：
- 只提取有跨会话检索价值的事件信息，一次性的寒暄或常规对话不提取。
- 如果当前轮次没有值得跨会话检索的新事件，返回 {{"summary": "", "facts": []}}。
- 只提取对话中明确提到的信息，不要推测。

对话内容：
{conversation_text}

JSON："""


async def extract_episodic_memory(
    messages: list[dict],
    conversation_id: str,
    assistant_response: str = "",
    source_message_start_id: int | None = None,
    source_message_end_id: int | None = None,
) -> EpisodicMemory | None:
    """Extract key facts and summary from a completed conversation round.

    Called asynchronously after each chat request completes. Uses the flash
    model for fast, cheap extraction.
    """
    total = len(messages) + (1 if assistant_response else 0)
    if total < 6:
        return None

    # Build conversation transcript (last 30 messages, truncated)
    parts = []
    for m in messages[-30:]:
        role = "用户" if m["role"] == "user" else "助手"
        content = m.get("content", "")
        if content:
            parts.append(f"{role}: {content[:300]}")
    if assistant_response:
        parts.append(f"助手: {assistant_response[:300]}")

    conversation_text = "\n".join(parts)
    prompt = EXTRACTION_PROMPT.format(conversation_text=conversation_text)

    try:
        llm = _get_memory_llm()
        response = await llm.ainvoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON (handle markdown code fences)
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])  # drop opening fence
            if text.endswith("```"):
                text = text[:-3]

        result = json.loads(text)

        facts: list[dict] = result.get("facts", [])
        importance = max((f.get("importance", 5) for f in facts), default=5) if facts else 5
        summary: str = str(result.get("summary", "")).strip()

        if not summary:
            return None

        memory_id = str(uuid.uuid4())
        embedding_id = f"episodic_{memory_id}"
        now = int(time.time() * 1000)
# 如果当前要写入的“情景记忆摘要”与数据库中最新的一条完全相同，则直接返回已有的记录，避免重复写入。
        async with async_session() as db:
            existing = await _find_latest_episodic_memory(db, conversation_id)
            if existing and existing.summary.strip() == summary:
                return _record_to_episodic_memory(existing)

        collection = _get_collection()
        embedder = get_embedder()
        embedding = embedder.embed_query(summary)

        collection.add(
            ids=[embedding_id],
            documents=[summary],
            embeddings=[embedding],
            metadatas=[{
                "memory_id": memory_id,
                "conversation_id": conversation_id,
                "importance": importance,
                "created_at": now,
            }],
        )

        try:
            async with async_session() as db:
                record = EpisodicMemoryRecord(
                    id=memory_id,
                    conversation_id=conversation_id,
                    summary=summary,
                    facts_json=json.dumps(facts, ensure_ascii=False),
                    importance=importance,
                    embedding_id=embedding_id,
                    source_message_start_id=source_message_start_id,
                    source_message_end_id=source_message_end_id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(record)
                await db.commit()
                memory = _record_to_episodic_memory(record)
        except Exception:
            try:
                collection.delete(ids=[embedding_id])
            except Exception:
                logger.warning("Failed to clean up Chroma episodic embedding %s", embedding_id)
            raise

        logger.info(
            "Extracted episodic memory %s: %d facts, importance=%d",
            memory_id, len(facts), importance,
        )
        return memory

    except Exception:
        logger.exception("Failed to extract episodic memory for conversation %s", conversation_id)
        return None


async def _find_latest_episodic_memory(
    db: AsyncSession,
    conversation_id: str,
) -> EpisodicMemoryRecord | None:
    result = await db.execute(
        select(EpisodicMemoryRecord)
        .where(EpisodicMemoryRecord.conversation_id == conversation_id)
        .order_by(EpisodicMemoryRecord.created_at.desc())
    )
    return result.scalars().first()


def _record_to_episodic_memory(
    record: EpisodicMemoryRecord,
    distance: float | None = None,
) -> EpisodicMemory:
    try:
        facts = json.loads(record.facts_json) if record.facts_json else []
    except (json.JSONDecodeError, TypeError):
        facts = []

    return EpisodicMemory(
        id=record.id,
        conversation_id=record.conversation_id,
        summary=record.summary,
        embedding_id=record.embedding_id,
        facts=facts,
        importance=record.importance,
        created_at=record.created_at,
        source_message_start_id=record.source_message_start_id,
        source_message_end_id=record.source_message_end_id,
        distance=distance,
    )


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


async def retrieve_relevant_memories(
    query: str,
    limit: int = 3,
    exclude_conversation_id: str | None = None,
    distance_threshold: float = EPISODIC_DISTANCE_THRESHOLD,
) -> list[EpisodicMemory]:
    """Semantic search for relevant past conversation memories.

    Embeds the query and searches the ``episodic_memories`` ChromaDB collection.
    Returns memories ordered by relevance.
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    try:
        embedder = get_embedder()
        query_embedding = embedder.embed_query(query)

        fetch_limit = min(max(limit * 4, limit), collection.count())
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_limit,
            include=["documents", "metadatas", "distances"],
        )

        memories: list[EpisodicMemory] = []
        if results["ids"] and results["ids"][0]:
            seen: set[str] = set()
            async with async_session() as db:
                for i, embedding_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i] if results["distances"] else None
                    if distance is not None and distance > distance_threshold:
                        continue

                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    memory_id = metadata.get("memory_id") if metadata else None
                    if not memory_id:
                        # Backward compatibility for old Chroma-only entries.
                        memory_id = embedding_id
                    if memory_id in seen:
                        continue
                    seen.add(memory_id)

                    record = await db.get(EpisodicMemoryRecord, memory_id)
                    if not record:
                        continue
                    if exclude_conversation_id and record.conversation_id == exclude_conversation_id:
                        continue
                    memories.append(_record_to_episodic_memory(record, distance=distance))
                    if len(memories) >= limit:
                        break

        return memories

    except Exception:
        logger.exception("Failed to retrieve episodic memories")
        return []


async def delete_episodic_memories_for_conversation(conversation_id: str) -> int:
    """Delete all episodic memories for a conversation from SQLite and ChromaDB."""
    try:
        async with async_session() as db:
            result = await db.execute(
                select(EpisodicMemoryRecord)
                .where(EpisodicMemoryRecord.conversation_id == conversation_id)
            )
            records = list(result.scalars().all())
            if not records:
                return 0

            embedding_ids = [r.embedding_id for r in records if r.embedding_id]
            if embedding_ids:
                try:
                    _get_collection().delete(ids=embedding_ids)
                except Exception:
                    logger.exception(
                        "Failed to delete Chroma episodic embeddings for conversation %s",
                        conversation_id,
                    )

            for record in records:
                await db.delete(record)
            await db.commit()
            return len(records)

    except Exception:
        logger.exception("Failed to delete episodic memories for conversation %s", conversation_id)
        return 0


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_memory_context(memories: list[EpisodicMemory]) -> str:
    """Format retrieved memories into a context string for message injection."""
    if not memories:
        return ""

    lines = ["[系统提示] 以下是用户历史对话中可能与当前问题相关的信息，请参考："]
    for i, mem in enumerate(memories, 1):
        lines.append(f"\n{i}. {mem.summary}")
        important_facts = [f for f in mem.facts if f.get("importance", 5) >= 6]
        for fact in important_facts[:3]:
            lines.append(f"   - {fact['fact']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# User Profile (long-term trait memory)
# ---------------------------------------------------------------------------

USER_PROFILE_ID = 1  # Single-user app

PROFILE_EXTRACTION_PROMPT = """分析以下对话，提取用户明确表达的长期健康画像事实，以 JSON 格式返回（只输出 JSON）：

你是长期用户画像的唯一权威来源。你提取的事实会持久保存并跨会话复用，因此必须谨慎——只记录用户明确表达、长期稳定的信息。
短期计划、一次性反馈、临时的困惑或想法不应进入画像。会话摘要和情景记忆会分别管理会话连续性和历史事件，你不需要覆盖它们。

{
  "facts": [
    {
      "category": "condition",
      "key": "高血压",
      "value": {"name": "高血压", "details": "用户明确提到有高血压"},
      "status": "active",
      "confidence": 0.9,
      "evidence": "我有高血压"
    }
  ]
}

category 可选值：
- basic：年龄、性别、身高、体重，key 使用 age/gender/height/weight
- condition：疾病、症状、体检指标
- allergy：过敏
- medication：用药，value 可包含 name/dosage/frequency/status
- diet_preference：饮食偏好
- exercise_preference：运动习惯
- goal：健康目标

status 可选值：
- active：当前有效事实
- inactive：用户明确表示已停用、已不适用或已过期
- corrected：用户明确纠正了之前的信息
- pending：信息重要但表达不够确定

规则：
- 只提取**用户**明确提到的长期稳定信息，不要推测。
- 不要把助手说的话写为用户事实。
- 不要把一次性的临时计划、当前困惑或短期反馈提取为长期事实。
- 对用药、诊断、过敏、体检指标等高风险事实，务必填写 evidence 字段引用用户原话。
- 如果用户纠正或否定了旧信息，返回对应 key 且 status 为 corrected 或 inactive，并在 evidence 中记录纠正的原话。
- 如果没有新的长期画像事实，返回 {"facts": []}。

对话内容：
{conversation_text}

JSON："""


async def get_user_profile(db: AsyncSession) -> UserProfile:
    """Get or create the single user profile (ID=1)."""
    result = await db.get(UserProfile, USER_PROFILE_ID)
    if result is None:
        result = UserProfile(id=USER_PROFILE_ID, traits_json="{}")
        db.add(result)
        await db.flush()
    return result


async def list_user_memory_facts(
    db: AsyncSession,
    status: str | None = None,
) -> list[UserMemoryFact]:
    """List traceable user facts, optionally filtered by status."""
    stmt = select(UserMemoryFact).order_by(UserMemoryFact.updated_at.desc())
    if status:
        stmt = stmt.where(UserMemoryFact.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_user_memory_fact(
    db: AsyncSession,
    fact_id: str,
    *,
    status: str | None = None,
    value: dict | None = None,
    confidence: float | None = None,
) -> UserMemoryFact | None:
    """Update a user fact and rebuild the profile snapshot."""
    fact = await db.get(UserMemoryFact, fact_id)
    if not fact:
        return None

    if status is not None:
        fact.status = status
    if value is not None:
        fact.value_json = json.dumps(value, ensure_ascii=False)
    if confidence is not None:
        fact.confidence = confidence
    fact.updated_at = int(time.time() * 1000)

    await rebuild_user_profile_snapshot(db)
    await db.flush()
    return fact


async def delete_user_memory_fact(db: AsyncSession, fact_id: str) -> bool:
    """Delete a user fact and rebuild the profile snapshot."""
    fact = await db.get(UserMemoryFact, fact_id)
    if not fact:
        return False
    await db.delete(fact)
    await db.flush()
    await rebuild_user_profile_snapshot(db)
    return True


async def extract_and_update_profile(
    messages: list[dict],
    assistant_response: str = "",
    conversation_id: str | None = None,
    source_message_id: int | None = None,
) -> UserProfile | None:
    """Extract user facts from conversation and rebuild the profile snapshot.

    Called asynchronously after each chat request completes. Creates its own
    DB session to avoid depending on the request-scoped session.
    """
    total = len(messages) + (1 if assistant_response else 0)
    if total < 2:
        return None

    # Build conversation transcript (last 30 messages)
    parts = []
    for m in messages[-30:]:
        role = "用户" if m["role"] == "user" else "助手"
        content = m.get("content", "")
        if content:
            parts.append(f"{role}: {content[:300]}")
    if assistant_response:
        parts.append(f"助手: {assistant_response[:300]}")

    conversation_text = "\n".join(parts)
    prompt = PROFILE_EXTRACTION_PROMPT.format(conversation_text=conversation_text)

    try:
        llm = _get_memory_llm()
        response = await llm.ainvoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]

        payload = json.loads(text)
        raw_facts = payload.get("facts", []) if isinstance(payload, dict) else []
        facts = [_normalize_extracted_fact(f) for f in raw_facts]
        facts = [f for f in facts if f is not None]

        if not facts:
            return None

        async with async_session() as db:
            now = int(time.time() * 1000)
            for fact_data in facts:
                await _upsert_user_fact(
                    db,
                    fact_data=fact_data,
                    conversation_id=conversation_id,
                    source_message_id=source_message_id,
                    extracted_at=now,
                )
            profile = await rebuild_user_profile_snapshot(db)
            await db.commit()

        logger.info("Updated user profile from %d extracted facts", len(facts))
        return profile

    except Exception:
        logger.exception("Failed to extract user traits")
        return None


async def rebuild_user_profile_snapshot(db: AsyncSession) -> UserProfile:
    """Rebuild traits_json from active traceable facts."""
    profile = await get_user_profile(db)
    facts = await list_user_memory_facts(db, status="active")
    snapshot = _snapshot_from_facts(facts)
    profile.traits_json = json.dumps(snapshot, ensure_ascii=False)
    profile.updated_at = int(time.time() * 1000)
    db.add(profile)
    return profile


async def _upsert_user_fact(
    db: AsyncSession,
    *,
    fact_data: dict,
    conversation_id: str | None,
    source_message_id: int | None,
    extracted_at: int,
) -> UserMemoryFact:
    category = fact_data["category"]
    key = fact_data["key"]
    status = fact_data.get("status", "active")

    existing_result = await db.execute(
        select(UserMemoryFact)
        .where(UserMemoryFact.category == category)
        .where(UserMemoryFact.key == key)
        .where(UserMemoryFact.status == "active")
        .order_by(UserMemoryFact.updated_at.desc())
    )
    existing = existing_result.scalars().first()

    if status in {"inactive", "corrected"} and existing:
        existing.status = status
        existing.source_conversation_id = conversation_id
        existing.source_message_id = source_message_id
        existing.evidence_text = fact_data.get("evidence")
        existing.confidence = fact_data.get("confidence", existing.confidence)
        existing.updated_at = extracted_at
        db.add(existing)
        return existing

    if existing and status == "active":
        existing.value_json = json.dumps(fact_data["value"], ensure_ascii=False)
        existing.source_conversation_id = conversation_id
        existing.source_message_id = source_message_id
        existing.evidence_text = fact_data.get("evidence")
        existing.confidence = fact_data.get("confidence", existing.confidence)
        existing.updated_at = extracted_at
        db.add(existing)
        return existing

    fact = UserMemoryFact(
        id=str(uuid.uuid4()),
        category=category,
        key=key,
        value_json=json.dumps(fact_data["value"], ensure_ascii=False),
        status=status,
        confidence=fact_data.get("confidence", 0.8),
        source_conversation_id=conversation_id,
        source_message_id=source_message_id,
        evidence_text=fact_data.get("evidence"),
        extracted_at=extracted_at,
        updated_at=extracted_at,
    )
    db.add(fact)
    return fact


def _normalize_extracted_fact(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None

    category = str(raw.get("category", "")).strip()
    if category not in {
        "basic",
        "condition",
        "allergy",
        "medication",
        "diet_preference",
        "exercise_preference",
        "goal",
    }:
        return None

    value = raw.get("value")
    if value in (None, "", [], {}):
        return None
    if not isinstance(value, dict):
        value = {"value": value}

    key = str(raw.get("key") or value.get("name") or value.get("value") or "").strip()
    if not key:
        return None

    status = str(raw.get("status", "active")).strip()
    if status not in {"active", "inactive", "corrected", "pending"}:
        status = "active"

    try:
        confidence = float(raw.get("confidence", 0.8))
    except (TypeError, ValueError):
        confidence = 0.8
    confidence = min(1.0, max(0.0, confidence))

    return {
        "category": category,
        "key": key,
        "value": value,
        "status": status,
        "confidence": confidence,
        "evidence": raw.get("evidence"),
    }


def _snapshot_from_facts(facts: list[UserMemoryFact]) -> dict:
    snapshot: dict = {
        "basic": {},
        "conditions": [],
        "allergies": [],
        "medications": [],
        "preferences": {},
        "goals": [],
    }

    for fact in sorted(facts, key=lambda f: f.updated_at):
        try:
            value = json.loads(fact.value_json)
        except (json.JSONDecodeError, TypeError):
            continue

        if fact.category == "basic":
            raw_value = value.get("value", value.get(fact.key))
            if raw_value not in (None, ""):
                snapshot["basic"][fact.key] = raw_value
        elif fact.category == "condition":
            item = value if isinstance(value, dict) else {"name": str(value)}
            item.setdefault("name", fact.key)
            snapshot["conditions"].append(item)
        elif fact.category == "allergy":
            snapshot["allergies"].append(value.get("name") or value.get("value") or fact.key)
        elif fact.category == "medication":
            item = value if isinstance(value, dict) else {"name": str(value)}
            item.setdefault("name", fact.key)
            snapshot["medications"].append(item)
        elif fact.category == "diet_preference":
            snapshot["preferences"]["diet"] = value.get("value") or value.get("diet") or fact.key
        elif fact.category == "exercise_preference":
            snapshot["preferences"]["exercise"] = value.get("value") or value.get("exercise") or fact.key
        elif fact.category == "goal":
            snapshot["goals"].append(value.get("value") or value.get("goal") or fact.key)

    return snapshot


def format_profile_context(profile: UserProfile) -> str:
    """Format user profile into a context string for message injection."""
    traits = json.loads(profile.traits_json) if profile.traits_json else {}
    if not traits or all(
        (v is None or v == [] or v == {}) for v in traits.values()
    ):
        return ""

    lines = ["[用户健康档案] 以下是已知的用户健康信息："]

    basic = traits.get("basic", {})
    if any(v is not None for v in basic.values()):
        parts = []
        if basic.get("age"):
            parts.append(f"{basic['age']}岁")
        if basic.get("gender"):
            parts.append(basic["gender"])
        if basic.get("height"):
            parts.append(f"身高{basic['height']}cm")
        if basic.get("weight"):
            parts.append(f"体重{basic['weight']}kg")
        if parts:
            lines.append(f"基本信息: {', '.join(parts)}")

    conditions = traits.get("conditions", [])
    if conditions:
        items = [f"{c['name']}" + (f" (自{c['since']})" if c.get("since") else "") for c in conditions]
        lines.append(f"健康状况: {', '.join(items)}")

    medications = traits.get("medications", [])
    if medications:
        items = [f"{m['name']}" + (f" {m['dosage']}" if m.get("dosage") else "") for m in medications]
        lines.append(f"用药: {', '.join(items)}")

    allergies = traits.get("allergies", [])
    if allergies:
        lines.append(f"过敏: {', '.join(allergies)}")

    prefs = traits.get("preferences", {})
    pref_parts = []
    if prefs.get("diet"):
        pref_parts.append(f"饮食: {prefs['diet']}")
    if prefs.get("exercise"):
        pref_parts.append(f"运动: {prefs['exercise']}")
    if pref_parts:
        lines.append(f"偏好: {'; '.join(pref_parts)}")

    goals = traits.get("goals", [])
    if goals:
        lines.append(f"目标: {', '.join(goals)}")

    return "\n".join(lines)
