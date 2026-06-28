# =============================================================================
# 0. 所有可调参数都在这里
# =============================================================================

CONFIG = {
    # -------------------------
    # LLM 服务配置
    # -------------------------
    "api_key": "0",
    # macstudio
    "base_url": "http://127.0.0.1:1234/v1",
    "model": "Qwen3.5-27B",

    # -------------------------
    # 输出文件配置
    # -------------------------
    # v0.6 起默认不再把所有预测 append 到一个 forecast_mvp_store.json。
    # 每个问题直接输出一个 Markdown，JSON 也按单条记录保存到 outputs/json。
    "report_output_dir": "./outputs/md",
    "json_output_dir": "./outputs/json",
    "save_markdown_report": True,
    "save_json_record": True,
    "save_output_index": False,

    # 旧字段保留给兼容读取，不再默认写入。
    "storage_path": "./forecast_mvp_store.json",
    "question_decomposition_storage_path": "./outputs/json/question_decomposition_store.json",
    "save_question_decomposition_record": True,

    # -------------------------
    # LLM 通用参数
    # -------------------------
    "llm": {
        "max_tokens": 100000,
        "top_p": 0.80,
        "system": "You are a rigorous superforecasting research assistant. Output exactly what the user asks for.",
    },

    # -------------------------
    # 不同阶段的 temperature
    # -------------------------
    "temperature": {
        "question_expansion": 0.7,
        "contract": 0.7,
        "decomposition": 0.7,
        "evidence": 0.7,
        "panel": 0.7,
        "portfolio_summary": 0.7,
        "json_repair": 0.7,
    },

    # -------------------------
    # 云状问题识别配置
    # -------------------------
    "cloud_question": {
        "cloud_terms": [
            "更好", "更差", "改善", "恶化", "成功", "失败", "爆发", "崩溃",
            "变强", "变弱", "繁荣", "衰退", "领先", "落后", "有前途", "没前途",
            "过得好", "幸福", "压力", "景气", "复苏", "危机", "牛市", "熊市"
        ],
        "force_multi_contract_when_cloud": True,
        "min_intent_preservation_for_single_contract": 0.70,
        "high_risk_blocks_single_contract": True,
    },

    # -------------------------
    # Portfolio 聚合配置
    # -------------------------
    "portfolio": {
        "max_contract_candidates": 7,
        "min_contract_candidates": 3,

        # 如果模型没给 coverage，就按这些默认经济类维度权重近似
        "default_cloud_dimension_weights": {
            "output_or_gdp": 0.25,
            "income_and_employment": 0.20,
            "consumption_and_confidence": 0.15,
            "industry_and_business_vitality": 0.15,
            "housing_and_balance_sheet": 0.10,
            "fiscal_and_public_services": 0.05,
            "external_environment": 0.05,
            "subjective_wellbeing": 0.05,
        },

        # proxy risk 对组合权重的惩罚
        "proxy_risk_weight_factor": {
            "low": 1.00,
            "medium": 0.85,
            "high": 0.60,
            "unknown": 0.75,
        },

        # 组合置信区间
        "portfolio_interval": {
            "base_sigma": 0.35,
            "semantic_risk_penalty": {
                "low": 0.05,
                "medium": 0.25,
                "high": 0.55,
                "unknown": 0.35,
            },
            "subforecast_disagreement_weight": 0.45,
            "min_sigma": 0.35,
            "max_sigma": 2.20,
        },
    },

    # -------------------------
    # 预测引擎参数
    # -------------------------
    "engine": {
        "min_probability": 0.01,
        "max_probability": 0.99,

        "min_base_probability": 0.02,
        "max_base_probability": 0.98,

        "min_evidence_impact_log_odds": -0.80,
        "max_evidence_impact_log_odds": 0.80,

        "min_factor_effect_log_odds": -1.50,
        "max_factor_effect_log_odds": 1.50,

        "max_factors": 12,
        "max_evidence_cards": 12,
        "max_panel_agents": 8,

        "independence_penalty_power": 0.5,

        "ensemble_weights": {
            "base_const": 0.20,
            "base_low_forecastability_bonus": 0.25,
            "evidence_const": 0.10,
            "evidence_forecastability_bonus": 0.30,
            "causal_const": 0.10,
            "causal_forecastability_bonus": 0.25,
            "panel_const": 0.20,
        },

        "cold_start_min_history": 10,
        "cold_start_temperature_base": 1.25,
        "cold_start_temperature_forecastability_discount": 0.15,

        "brier_temperature": {
            "bad_threshold": 0.25,
            "weak_threshold": 0.22,
            "strong_threshold": 0.17,
            "bad_temperature": 1.45,
            "weak_temperature": 1.25,
            "normal_temperature": 1.12,
            "strong_temperature": 1.00,
        },

        "interval": {
            "base_sigma": 0.55,
            "forecastability_penalty": 1.15,
            "panel_disagreement_weight": 0.30,
            "evidence_quality_penalty": 0.65,
            "evidence_count_bonus_per_card": 0.03,
            "max_evidence_count_bonus": 0.25,
            "min_sigma": 0.35,
            "max_sigma": 2.00,
        },
    },

    # -------------------------
    # Bayesian Causal Graph / Monte Carlo 配置
    # -------------------------
    "causal_graph": {
        "enabled": True,
        "monte_carlo_samples": 12000,
        "sensitivity_samples": 3000,
        "random_seed": 42,
        "max_nodes": 12,
        "max_edges": 32,
        "max_sensitivity_nodes": 6,
        "beta_strength_min": 2.0,
        "beta_strength_max": 90.0,
        "node_evidence_max_abs_log_odds": 1.20,
        "target_evidence_max_abs_log_odds": 1.00,
        "min_node_probability": 0.02,
        "max_node_probability": 0.98,
        "min_target_probability": 0.01,
        "max_target_probability": 0.99,
        "default_node_confidence": 0.50,
        "default_edge_confidence": 0.55,
        "default_base_confidence": 0.50,
        "default_evidence_update_confidence": 0.45,

        # v0.5.3: Monte Carlo 不再只采样 factor true/false，
        # 而是做“预测不确定性传播”。
        # 这些参数只影响 causal_graph_probability，不改变 base/evidence/panel/portfolio 主流程。
        "uncertainty_sampling": {
            "enabled": True,

            # 1. base rate 不确定性：每轮从 Beta(base_p, base_confidence) 采样 base_p。
            "sample_base_rate": True,

            # 2. factor 状态不确定性：保留旧逻辑，节点概率先 Beta 采样，再 Bernoulli 采样 true/false。
            "sample_factor_state": True,

            # 3. factor effect 不确定性：每轮扰动 factor 对目标的 log-odds 影响强度。
            "sample_factor_effect": True,
            "factor_effect_sigma_min": 0.03,
            "factor_effect_sigma_max": 0.45,
            "factor_effect_relative_sigma": 0.20,
            "factor_effect_clip_abs": 1.75,

            # 4. evidence update 不确定性：每轮扰动 target evidence delta。
            "sample_evidence_update": True,
            "evidence_delta_sigma_min": 0.02,
            "evidence_delta_sigma_max": 0.35,
            "evidence_delta_relative_sigma": 0.25,
            "evidence_delta_clip_abs": 1.20,
            "sample_evidence_noise_when_zero": False,

            # 5. target logit 不确定性：保留一项模型/结构残差噪声。
            "sample_target_logit_noise": True,
            "target_logit_noise_sigma_min": 0.00,
            "target_logit_noise_sigma_max": 0.30,
            "target_logit_noise_confidence_key": "graph_confidence",

            # 采样诊断输出。
            "return_sampling_diagnostics": True,
        },

        # causal graph 自身置信度标签，用于报告或 JSON 诊断。
        "confidence_label": {
            "wide_interval_threshold": 0.55,
            "medium_interval_threshold": 0.30,
            "sparse_edge_ratio_threshold": 0.35,
            "low_score_threshold": 0.40,
            "medium_score_threshold": 0.70,
        },
    },

    # -------------------------
    # 输出控制
    # -------------------------
    "runtime": {
        "print_steps": True,
        "print_expansion_json": True,
        "print_intermediate_json": True,
        "print_subcontract_reports": False,
        "print_markdown": True,
        "print_raw_json": False,
    },
}
