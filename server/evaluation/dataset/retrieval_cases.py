"""Manual retrieval test cases for RAG retriever regression checks."""

from __future__ import annotations


DEFAULT_RETRIEVAL_CASES = [
    {
        "id": "profile_height_weight",
        "question": "我的身高体重是多少？",
        "category": "factual",
        "expected_terms": ["身高", "体重", "180", "70"],
    },
    {
        "id": "blood_pressure_value",
        "question": "血压 145/90mmHg 正常吗？",
        "category": "factual",
        "expected_terms": ["血压", "145", "90", "mmHg", "高血压"],
    },
    {
        "id": "protein_intake",
        "question": "成年人每天建议摄入多少蛋白质？",
        "category": "factual",
        "expected_terms": ["蛋白质", "0.8", "1.2", "克"],
    },
    {
        "id": "vitamin_d_sources",
        "question": "维生素 D 的主要食物来源有哪些？",
        "category": "factual",
        "expected_terms": ["维生素", "D", "鱼", "蛋", "奶"],
    },
    {
        "id": "dash_mediterranean",
        "question": "比较地中海饮食和 DASH 饮食在控制高血压方面的异同。",
        "category": "multi_doc",
        "expected_terms": ["地中海", "DASH", "高血压", "钠", "蔬果"],
    },
    {
        "id": "fatigue_checks",
        "question": "最近疲劳注意力不集中，应该做哪些检查？",
        "category": "reasoning",
        "expected_terms": ["疲劳", "血常规", "甲状腺", "维生素", "血糖"],
    },
    {
        "id": "knee_pain_running",
        "question": "跑步时膝盖疼，还能继续跑吗？",
        "category": "safety",
        "expected_terms": ["膝盖", "跑步", "休息", "疼痛", "就医"],
    },
    {
        "id": "unsafe_weight_loss_tea",
        "question": "排毒减肥茶每天喝三包靠谱吗？",
        "category": "safety",
        "expected_terms": ["排毒", "减肥茶", "泻药", "电解质", "不建议"],
    },
]


def load_retrieval_cases() -> list[dict]:
    """Load retrieval-only test cases."""
    return [dict(case) for case in DEFAULT_RETRIEVAL_CASES]
