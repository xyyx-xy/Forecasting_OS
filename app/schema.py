# =============================================================================
# 4. Prompt Schema
# =============================================================================

DECOMPOSITION_SCHEMA = {
    "base_rate": {
        "reference_class": "最接近的参考类。",
        "base_probability": "0到1，作为先验概率。",
        "sample_size_guess": "如果没有硬数据，写 rough/unknown；不要假装精确。",
        "confidence": "0到1",
        "rationale": "为什么这个参考类合理。",
    },
    "factors": [
        {
            "factor": "影响因素名称",
            "sub_question": "可被单独判断的子问题",
            "direction_if_true": "increase | decrease | mixed",
            "probability": "该因素为真的概率，0到1",
            "effect_log_odds": "如果该因素为真，对主事件log-odds影响，-1.5到1.5",
            "confidence": "0到1",
            "dependencies": ["依赖的其他factor名称"],
            "rationale": "简短理由",
        }
    ],
    "known_unknowns": ["关键未知项"],
    "search_queries": ["如果未来接入搜索，应搜索的query"],
}

EVIDENCE_SCHEMA = {
    "evidence_cards": [
        {
            "claim": "证据主张。不能编造具体来源。",
            "source_type": "user_provided | background | official | news | paper | market | database | other",
            "source": "来源名称；如果没有真实来源，写 background_prior 或 user_input，不要写假URL。",
            "direction": "increase | decrease | neutral",
            "relevance": "0到1",
            "reliability": "0到1",
            "diagnosticity": "0到1，表示这条证据对预测是否有区分度",
            "freshness": "0到1",
            "independence_group": "同源证据用同一个group，避免重复计权",
            "impact_log_odds": "证据对主事件log-odds的裸影响，-0.8到0.8",
            "rationale": "为什么这么赋权",
        }
    ]
}

PANEL_SCHEMA = {
    "agent_forecasts": [
        {
            "agent_name": "outside_view | inside_view | skeptic | optimist | base_rate_guardian | domain_generalist",
            "probability": "0到1",
            "confidence": "0到1",
            "rationale": "简短理由",
            "strongest_update_trigger": "什么新证据会明显改变判断",
        }
    ]
}
