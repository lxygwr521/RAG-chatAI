"""Manual retrieval test cases for RAG retriever regression checks.

Coverage targets across the 6 knowledge-base documents:

  01-饮食营养指南        6 cases (food diversity, protein, vitamin D, veggies,
                              whole grains, sodium/hypertension cross-doc)
  02-健身锻炼指南        3 cases (aerobic guideline, strength beginner, knee-pain)
  03-睡眠管理指南        2 cases (sleep duration, insomnia remedies)
  04-生活习惯与心理平衡  3 cases (alcohol limit, smoking cessation, stress management)
  05-古法锻炼与传统养生  3 cases (tai chi, baduanjin, traditional-vs-modern cross-doc)
  06-个人健康档案         3 cases (height/weight, blood pressure, BMI assessment)

Categories: factual, multi_doc, reasoning, safety, sleep, exercise,
            nutrition, mental_health, traditional, specific_nutrient
"""

from __future__ import annotations


DEFAULT_RETRIEVAL_CASES: list[dict] = [
    # =========================================================================
    # 06-个人健康档案与状态评估 (3 cases)
    # =========================================================================
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
        "id": "bmi_weight_assessment",
        "question": "我的 BMI 21.6 算正常吗？理想体重范围是多少？",
        "category": "factual",
        "expected_terms": ["BMI", "21.6", "体重", "正常", "身高"],
    },

    # =========================================================================
    # 01-饮食营养指南 (5 cases)
    # =========================================================================
    {
        "id": "protein_intake",
        "question": "成年人每天建议摄入多少蛋白质？",
        "category": "nutrition",
        "expected_terms": ["蛋白质", "0.8", "1.2", "克"],
    },
    {
        "id": "vitamin_d_sources",
        "question": "维生素 D 的主要食物来源有哪些？",
        "category": "nutrition",
        "expected_terms": ["维生素", "D", "鱼", "蛋", "奶"],
    },
    {
        "id": "daily_vegetable_intake",
        "question": "每天应该吃多少蔬菜水果才够？",
        "category": "nutrition",
        "expected_terms": ["蔬菜", "300", "水果", "200", "深色"],
    },
    {
        "id": "whole_grains_guide",
        "question": "全谷物有哪些种类？每天应该吃多少？",
        "category": "nutrition",
        "expected_terms": ["全谷物", "糙米", "燕麦", "杂豆", "薯类"],
    },
    {
        "id": "sodium_hypertension_diet",
        "question": "高血压患者饮食上应该注意什么？钠摄入控制在多少？",
        "category": "multi_doc",
        "expected_terms": ["钠", "盐", "高血压", "DASH", "蔬果"],
    },

    # =========================================================================
    # 02-健身锻炼指南 (3 cases)
    # =========================================================================
    {
        "id": "aerobic_exercise_weekly",
        "question": "每周应该做多少有氧运动才够？",
        "category": "exercise",
        "expected_terms": ["150", "有氧", "中等强度", "FITT", "分钟"],
    },
    {
        "id": "strength_training_beginner",
        "question": "新手入门力量训练应该注意什么？",
        "category": "exercise",
        "expected_terms": ["力量", "训练", "循序渐进", "安全", "组"],
    },
    {
        "id": "knee_pain_running",
        "question": "跑步时膝盖疼，还能继续跑吗？",
        "category": "safety",
        "expected_terms": ["膝盖", "跑步", "休息", "疼痛", "就医"],
    },

    # =========================================================================
    # 03-睡眠管理指南 (2 cases)
    # =========================================================================
    {
        "id": "sleep_duration_adult",
        "question": "成年人一天睡几个小时最好？",
        "category": "sleep",
        "expected_terms": ["睡眠", "7", "9", "NSF", "小时"],
    },
    {
        "id": "insomnia_sleep_remedies",
        "question": "晚上睡不着有什么改善方法？",
        "category": "sleep",
        "expected_terms": ["入睡", "睡前", "睡眠", "环境", "放松"],
    },

    # =========================================================================
    # 04-生活习惯与心理平衡指南 (3 cases)
    # =========================================================================
    {
        "id": "alcohol_safe_limit",
        "question": "喝酒的安全限量是多少？对身体有什么危害？",
        "category": "factual",
        "expected_terms": ["酒精", "15", "致癌", "肝脏", "饮酒"],
    },
    {
        "id": "smoking_cessation_timeline",
        "question": "戒烟后身体多久能恢复？有什么变化？",
        "category": "factual",
        "expected_terms": ["戒烟", "尼古丁", "肺功能", "冠心病"],
    },
    {
        "id": "stress_emotion_management",
        "question": "工作压力大、情绪不好的时候怎么调节？",
        "category": "mental_health",
        "expected_terms": ["压力", "情绪", "RAIN", "呼吸", "放松"],
    },

    # =========================================================================
    # 05-古法锻炼与传统养生指南 (3 cases)
    # =========================================================================
    {
        "id": "tai_chi_health_benefits",
        "question": "打太极拳对身体有什么好处？能降血压吗？",
        "category": "traditional",
        "expected_terms": ["太极", "平衡", "跌倒", "血压", "老年人"],
    },
    {
        "id": "baduanjin_introduction",
        "question": "八段锦是什么样的锻炼方式？适合什么人？",
        "category": "traditional",
        "expected_terms": ["八段锦", "动作", "呼吸", "养生", "传统"],
    },
    {
        "id": "traditional_vs_modern_exercise",
        "question": "传统养生锻炼（太极/气功）和现代健身有什么区别？哪个更好？",
        "category": "multi_doc",
        "expected_terms": ["传统", "现代", "太极", "气功", "健身"],
    },

    # =========================================================================
    # 跨文档综合推理 (2 cases)
    # =========================================================================
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

    # =========================================================================
    # 安全/边界 (1 case)
    # =========================================================================
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
