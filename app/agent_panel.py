from typing import Any, Dict, List, Tuple, Optional
from app.config import CONFIG
from app.schema import DECOMPOSITION_SCHEMA, EVIDENCE_SCHEMA, PANEL_SCHEMA
from app.utils import (
    clamp,
    json_dumps,
    llm_json,
)

# =============================================================================
# 6. Agent 调用：分解、证据、Panel
# =============================================================================

def decompose_question(
    question: str,
    contract: Dict[str, Any],
    expansion: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    expansion_context = ""
    if expansion:
        expansion_context = f"""
原始问题的语义展开：
{json_dumps({
    "question_type": expansion.get("question_type"),
    "overall_semantic_intent": expansion.get("overall_semantic_intent"),
    "semantic_collapse_risk": expansion.get("semantic_collapse_risk"),
    "dimension_map": expansion.get("dimension_map"),
})}

注意：
当前只预测 portfolio 中的一个子合约。不要把该子合约误认为完整原问题。
"""

    prompt = f"""
你是 Superforecasting Decomposition Agent。使用 Tetlock 风格的方法拆解预测题。

方法：
1. outside view / base rate
2. inside view / 机制分析
3. Fermi decomposition
4. 反方视角
5. 关键未知项

原始问题：
{question}

{expansion_context}

当前预测合约：
{json_dumps(contract)}

要求：
1. base_probability 是先验，不是最终概率。
2. factors 的 effect_log_odds 是数学引擎后续会使用的数值；不要全部给极端值。
3. 明确 dependencies，避免假设所有子问题独立。
4. 如果没有硬数据，要在 rationale 里说明不确定性。
5. 不要编造具体统计数据。
6. search_queries 只是为以后接入搜索准备，不代表你已经搜索过。
7. 如果这是一个云状问题的子合约，必须只围绕当前 contract 的指标拆解，不要冒充完整原问题。

输出 JSON schema：
{json_dumps(DECOMPOSITION_SCHEMA)}
"""
    obj = llm_json(
        prompt,
        config=config,
        temperature=config["temperature"]["decomposition"],
    )

    engine = config["engine"]

    base = obj.get("base_rate", {}) or {}
    base["base_probability"] = clamp(
        base.get("base_probability", 0.5),
        engine["min_base_probability"],
        engine["max_base_probability"],
    )
    base["confidence"] = clamp(base.get("confidence", 0.5), 0.0, 1.0)
    base.setdefault("reference_class", "")
    base.setdefault("sample_size_guess", "unknown")
    base.setdefault("rationale", "")
    obj["base_rate"] = base

    clean_factors = []
    for f in (obj.get("factors") or [])[:engine["max_factors"]]:
        f["probability"] = clamp(
            f.get("probability", 0.5),
            engine["min_base_probability"],
            engine["max_base_probability"],
        )
        f["effect_log_odds"] = clamp(
            f.get("effect_log_odds", 0.0),
            engine["min_factor_effect_log_odds"],
            engine["max_factor_effect_log_odds"],
        )
        f["confidence"] = clamp(f.get("confidence", 0.5), 0.0, 1.0)
        f.setdefault("factor", "")
        f.setdefault("sub_question", "")
        f.setdefault("direction_if_true", "mixed")
        f.setdefault("dependencies", [])
        f.setdefault("rationale", "")
        clean_factors.append(f)

    obj["factors"] = clean_factors
    obj.setdefault("known_unknowns", [])
    obj.setdefault("search_queries", [])

    return obj


def build_evidence_cards(
    question: str,
    contract: Dict[str, Any],
    decomposition: Dict[str, Any],
    user_evidence: str = "",
    expansion: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    if user_evidence.strip():
        evidence_mode = "用户提供了证据材料，请优先从用户材料中抽取证据卡。"
    else:
        evidence_mode = "用户没有提供外部证据。只能生成 background 类型的分析性证据卡，不得编造新闻、URL、论文或具体数据。"

    expansion_context = ""
    if expansion:
        expansion_context = f"""
原始问题是经过语义展开后的预测组合。当前 evidence 只服务于当前子合约：
{json_dumps({
    "overall_semantic_intent": expansion.get("overall_semantic_intent"),
    "current_dimension": contract.get("dimension_name"),
    "proxy_metric": contract.get("proxy_metric"),
    "proxy_risk": contract.get("proxy_risk"),
})}
"""

    prompt = f"""
你是 Evidence Structuring Agent。你的任务不是写文章，而是把信息整理成可计算的 evidence_cards。

{evidence_mode}

原始问题：
{question}

{expansion_context}

预测合约：
{json_dumps(contract)}

问题拆解：
{json_dumps(decomposition)}

用户提供的证据材料：
{user_evidence if user_evidence.strip() else "<empty>"}

要求：
1. 证据卡数量 4 到 12 条。
2. 不要编造具体来源、URL、统计数据、新闻标题。
3. 如果没有真实来源，source_type 必须使用 background，source 写 background_prior。
4. 如果证据来自用户材料，source_type 写 user_provided，source 写 user_input。
5. impact_log_odds 是裸影响，后续程序会乘以 relevance/reliability/diagnosticity/freshness 等权重。
6. 多条同源或高度相关证据必须使用同一个 independence_group。
7. diagnosticity 代表证据的区分度；泛泛而谈的信息不要给高分。
8. 如果当前 contract 是单一代理指标，不要把证据说成覆盖完整原问题。

输出 JSON schema：
{json_dumps(EVIDENCE_SCHEMA)}
"""
    obj = llm_json(
        prompt,
        config=config,
        temperature=config["temperature"]["evidence"],
    )

    engine = config["engine"]

    clean_cards = []
    for c in (obj.get("evidence_cards") or [])[:engine["max_evidence_cards"]]:
        c["relevance"] = clamp(c.get("relevance", 0.5), 0.0, 1.0)
        c["reliability"] = clamp(c.get("reliability", 0.5), 0.0, 1.0)
        c["diagnosticity"] = clamp(c.get("diagnosticity", 0.5), 0.0, 1.0)
        c["freshness"] = clamp(c.get("freshness", 0.5), 0.0, 1.0)
        c["impact_log_odds"] = clamp(
            c.get("impact_log_odds", 0.0),
            engine["min_evidence_impact_log_odds"],
            engine["max_evidence_impact_log_odds"],
        )
        c.setdefault("claim", "")
        c.setdefault("source_type", "background")
        c.setdefault("source", "background_prior")
        c.setdefault("direction", "neutral")
        c.setdefault("independence_group", "default")
        c.setdefault("rationale", "")
        clean_cards.append(c)

    obj["evidence_cards"] = clean_cards
    return obj


def run_forecaster_panel(
    question: str,
    contract: Dict[str, Any],
    decomposition: Dict[str, Any],
    evidence: Dict[str, Any],
    expansion: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    expansion_context = ""
    if expansion:
        expansion_context = f"""
这是原始云状问题的一个子合约，不是完整原问题。
原始语义：{expansion.get("overall_semantic_intent")}
当前维度：{contract.get("dimension_name")}
当前代理指标：{contract.get("proxy_metric")}
proxy_risk：{contract.get("proxy_risk")}
"""

    prompt = f"""
你是一个多智能体预测委员会。请让以下 6 个虚拟预测者独立给出概率：

1. outside_view：只重视参考类和历史基准。
2. inside_view：重视当前事件机制。
3. skeptic：专门寻找失败路径和反证。
4. optimist：专门寻找成功路径，但不能无脑乐观。
5. base_rate_guardian：防止过度偏离 base rate。
6. domain_generalist：综合判断。

重要：
这些概率不是最终答案。最终概率由 Python 数学引擎聚合。

原始问题：
{question}

{expansion_context}

预测合约：
{json_dumps(contract)}

拆解：
{json_dumps(decomposition)}

证据卡：
{json_dumps(evidence)}

要求：
1. 每个 agent 必须给 0 到 1 概率。
2. 不要互相抄同一个概率。
3. 给出 strongest_update_trigger。
4. 不要声称自己完成了实时搜索。
5. 如果这是云状问题的子合约，必须只预测当前子合约，不要把它说成完整原问题。

输出 JSON schema：
{json_dumps(PANEL_SCHEMA)}
"""
    obj = llm_json(
        prompt,
        config=config,
        temperature=config["temperature"]["panel"],
    )

    engine = config["engine"]

    clean_runs = []
    for r in (obj.get("agent_forecasts") or [])[:engine["max_panel_agents"]]:
        r["probability"] = clamp(
            r.get("probability", 0.5),
            engine["min_base_probability"],
            engine["max_base_probability"],
        )
        r["confidence"] = clamp(r.get("confidence", 0.5), 0.0, 1.0)
        r.setdefault("agent_name", "agent")
        r.setdefault("rationale", "")
        r.setdefault("strongest_update_trigger", "")
        clean_runs.append(r)

    obj["agent_forecasts"] = clean_runs
    return obj