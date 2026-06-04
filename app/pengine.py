from __future__ import annotations

import json
import math
import random
import re
from statistics import mean, pstdev
from typing import Any, Dict, List, Tuple, Optional


from app.config import CONFIG
from app.utils import (
    short_id,
    clamp,
    safe_float,
    logit,
    sigmoid,
    llm_json,
)

# =============================================================================
# 7. 概率引擎
# =============================================================================

def weight_evidence_cards(
    cards: List[Dict[str, Any]],
    config: Dict[str, Any] = CONFIG,
) -> Tuple[List[Dict[str, Any]], float, float]:
    engine = config["engine"]
    group_counts: Dict[str, int] = {}
    weighted_cards: List[Dict[str, Any]] = []
    total_delta = 0.0
    qualities = []

    penalty_power = engine["independence_penalty_power"]

    for c in cards:
        group = str(c.get("independence_group", "default"))
        group_counts[group] = group_counts.get(group, 0) + 1
        occurrence = group_counts[group]

        independence_penalty = 1.0 / (occurrence ** penalty_power)

        relevance = clamp(c.get("relevance", 0.5), 0.0, 1.0)
        reliability = clamp(c.get("reliability", 0.5), 0.0, 1.0)
        diagnosticity = clamp(c.get("diagnosticity", 0.5), 0.0, 1.0)
        freshness = clamp(c.get("freshness", 0.5), 0.0, 1.0)

        impact = clamp(
            c.get("impact_log_odds", 0.0),
            engine["min_evidence_impact_log_odds"],
            engine["max_evidence_impact_log_odds"],
        )

        quality_weight = relevance * reliability * diagnosticity * freshness * independence_penalty
        weighted_impact = impact * quality_weight

        c2 = dict(c)
        c2["independence_penalty"] = independence_penalty
        c2["quality_weight"] = quality_weight
        c2["weighted_impact_log_odds"] = weighted_impact

        weighted_cards.append(c2)
        total_delta += weighted_impact
        qualities.append(quality_weight)

    avg_quality = mean(qualities) if qualities else 0.0
    return weighted_cards, total_delta, avg_quality



def slugify_node_id(label: str, idx: int) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_]+", "_", str(label or "").lower()).strip("_")

    # 中文标签通常会被清空或只剩年份，不能直接当 node_id
    if not raw or raw.isdigit() or re.fullmatch(r"20\d{2}", raw):
        raw = f"factor_{idx:02d}"

    # 如果 raw 以数字开头，也加 prefix
    if re.match(r"^\d", raw):
        raw = f"factor_{idx:02d}_{raw}"

    return raw[:48]


def percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.5
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * clamp(q, 0.0, 1.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def beta_params_from_prob_confidence(
    p: float,
    confidence: float,
    config: Dict[str, Any] = CONFIG,
) -> Tuple[float, float]:
    cg = config.get("causal_graph", {})
    p = clamp(p, 0.001, 0.999)
    c = clamp(confidence, 0.0, 1.0)
    strength = cg.get("beta_strength_min", 2.0) + c * (
        cg.get("beta_strength_max", 90.0) - cg.get("beta_strength_min", 2.0)
    )
    return max(0.001, p * strength), max(0.001, (1.0 - p) * strength)


def normalize_factor_effect(factor: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> float:
    engine = config["engine"]
    effect = clamp(
        factor.get("effect_log_odds", 0.0),
        engine["min_factor_effect_log_odds"],
        engine["max_factor_effect_log_odds"],
    )
    direction = str(factor.get("direction_if_true", "")).lower().strip()
    if abs(effect) < 1e-9:
        if direction == "increase":
            effect = 0.35
        elif direction == "decrease":
            effect = -0.35
    elif direction == "increase" and effect < 0:
        effect = abs(effect)
    elif direction == "decrease" and effect > 0:
        effect = -abs(effect)
    return effect


def text_overlap_score(a: str, b: str) -> float:
    """轻量证据-节点匹配。适配中文：按字符集合近似，避免引入分词依赖。"""
    a = re.sub(r"\s+", "", str(a or "").lower())
    b = re.sub(r"\s+", "", str(b or "").lower())
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    sa = set(a)
    sb = set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))



# =============================================================================
# 7.1 Mechanism Chain Factor Graph：LLM 结构化机制链 + 防重复计数
# =============================================================================

MECHANISM_CHAIN_STRUCTURER_PROMPT = r"""
你是一个用于预测系统的“机制链结构分析器”。

你的任务不是预测概率，也不是给出结论。
你的任务是把一个预测合约中的 factors 组织成若干条 mechanism chains，
并判断每个 factor 在机制链中的角色，用于后续防重复计数和 Monte Carlo 推断。

核心原则：
1. 不要把同一条故事链上的多个 factor 当成相互独立证据。
2. 同方向、同机制链的 factor 只能作为部分佐证，不能简单累加。
3. 反方向 factor 要保留，因为它们代表抵消力量。
4. 区分上游驱动、中介变量、直接驱动和代理指标。
5. 如果不确定，标记 unknown，不要编造强因果。
6. 你只输出结构，不输出最终概率。

机制角色定义：
- upstream_driver: 上游驱动，通常通过中间机制影响目标。例如政策、利率、成本、宏观、监管。
- mediator: 中介变量，位于传导链中间。例如供给收缩、成交量、VC出手频率、LP资金释放。
- direct_driver: 直接影响目标事件的近端变量。例如目标价格、融资事件数、实际成交量、出栏量。
- proxy_indicator: 代理指标，只是观测信号，不一定是因果变量。例如情绪指数、搜索热度、媒体报道。
- shock_driver: 低概率高冲击因素。例如疫情、战争、突发政策、自然灾害。
- counterforce: 对主方向有抵消作用的力量。例如扩产抵消供给收缩、监管压制融资改善。
- unknown: 无法判断。

机制链要求：
- 生成 1 到 6 条 mechanism chains；如果 factors 很少，可以只生成 1 条。
- chain_id 必须是英文 snake_case。
- chain_label 使用中文。
- chain_confidence 表示你对“结构划分是否合理”的置信度，不是事件概率。
- 如果某个 factor 同时属于多个机制链，选择 primary chain，并在 role_reason 中说明次要影响。
- weak_edges_for_display 只输出少量最重要的机制边，最多 8 条。
- weak_edges_for_display 只用于解释展示，不代表严格因果发现。

防重复计数规则：
- 如果两个或多个 factor 是同一机制链上的上下游，并且方向一致，则 double_counting_risk 应为 medium 或 high。
- 如果一个 factor 是另一个 factor 的代理指标，也应标记 double_counting_risk。
- 如果 factor 方向相反，不是重复计数，而是 counterforce，应明确标记。

输入：
原始问题：
{original_question}

预测合约：
{contract_json}

分解 factors：
{factors_json}

已知语义上下文：
{expansion_summary_json}

请严格输出 JSON，不要输出 markdown，不要解释。
JSON schema:
{{
  "mechanism_chains": [
    {{
      "chain_id": "string",
      "chain_label": "string",
      "chain_description": "string",
      "direction_to_target_if_active": "increase|decrease|mixed|unknown",
      "chain_confidence": 0.0
    }}
  ],
  "factor_annotations": [
    {{
      "factor_id": "string",
      "factor_label": "string",
      "causal_chain_id": "string",
      "mechanism_role": "upstream_driver|mediator|direct_driver|proxy_indicator|shock_driver|counterforce|unknown",
      "role_reason": "string",
      "double_counting_risk": "low|medium|high",
      "double_counting_with": ["string"],
      "recommended_role_discount": 0.0,
      "is_primary_signal_in_chain": true
    }}
  ],
  "weak_edges_for_display": [
    {{
      "from_factor_id": "string",
      "to_factor_id": "string",
      "edge_type": "mechanism_support|mechanism_counterforce|proxy_to_driver|upstream_to_mediator",
      "direction": "positive|negative|mixed|unknown",
      "confidence": 0.0,
      "rationale": "string"
    }}
  ],
  "chain_level_notes": [
    {{
      "chain_id": "string",
      "double_counting_note": "string"
    }}
  ],
  "warnings": ["string"]
}}
"""


def _mechanism_config(config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    return (config.get("causal_graph", {}) or {}).get("mechanism_chain", {}) or {}


def _stable_snake_id(text: str, fallback: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_]+", "_", str(text or "").lower()).strip("_")
    if not raw or raw.isdigit() or re.fullmatch(r"20\d{2}", raw):
        raw = fallback
    if re.match(r"^\d", raw):
        raw = f"{fallback}_{raw}"
    return raw[:64]


def _factor_label_from_node(node: Dict[str, Any]) -> str:
    return str(node.get("label") or node.get("factor") or node.get("sub_question") or node.get("node_id") or "factor")


def default_role_discount(role: str, config: Dict[str, Any] = CONFIG) -> float:
    mc = _mechanism_config(config)
    role_discount = mc.get("role_discount", {}) or {}
    return clamp(role_discount.get(str(role or "unknown"), role_discount.get("unknown", 0.75)), 0.20, 1.00)


def fallback_mechanism_chain_structure(
    nodes: List[Dict[str, Any]],
    reason: str = "LLM mechanism chain structurer unavailable; using fallback main_chain.",
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    mc = _mechanism_config(config)
    fallback_id = mc.get("fallback_chain_id", "main_chain")
    annotations = []
    for i, n in enumerate(nodes or [], start=1):
        nid = n.get("node_id") or f"factor_{i:02d}"
        annotations.append({
            "factor_id": nid,
            "factor_label": _factor_label_from_node(n),
            "causal_chain_id": fallback_id,
            "mechanism_role": "unknown",
            "role_reason": reason,
            "double_counting_risk": "medium" if len(nodes or []) >= 4 else "low",
            "double_counting_with": [],
            "recommended_role_discount": default_role_discount("unknown", config=config),
            "is_primary_signal_in_chain": i == 1,
        })
    return {
        "mechanism_chains": [{
            "chain_id": fallback_id,
            "chain_label": "主机制链",
            "chain_description": reason,
            "direction_to_target_if_active": "mixed",
            "chain_confidence": mc.get("default_chain_confidence", 0.55),
        }],
        "factor_annotations": annotations,
        "weak_edges_for_display": [],
        "chain_level_notes": [{
            "chain_id": fallback_id,
            "double_counting_note": "fallback 模式：所有 factor 暂归入主机制链，链内使用 strongest signal + partial corroboration 防重复计数。",
        }],
        "warnings": [reason],
    }


def validate_mechanism_chain_structure(
    obj: Dict[str, Any],
    nodes: List[Dict[str, Any]],
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    mc = _mechanism_config(config)
    allowed_roles = {
        "upstream_driver", "mediator", "direct_driver", "proxy_indicator",
        "shock_driver", "counterforce", "unknown",
    }
    allowed_risks = {"low", "medium", "high"}
    allowed_edge_types = {"mechanism_support", "mechanism_counterforce", "proxy_to_driver", "upstream_to_mediator"}
    allowed_edge_dirs = {"positive", "negative", "mixed", "unknown"}

    factor_ids = [n.get("node_id") for n in nodes or [] if n.get("node_id")]
    factor_id_set = set(factor_ids)

    chains = obj.get("mechanism_chains") if isinstance(obj, dict) else []
    if not isinstance(chains, list):
        chains = []

    clean_chains = []
    seen_chain_ids = set()
    max_chains = int(mc.get("max_chains", 6))
    for idx, c in enumerate(chains[:max_chains], start=1):
        if not isinstance(c, dict):
            continue
        cid = _stable_snake_id(c.get("chain_id"), f"chain_{idx:02d}")
        if cid in seen_chain_ids:
            cid = f"{cid}_{idx}"
        seen_chain_ids.add(cid)
        clean_chains.append({
            "chain_id": cid,
            "chain_label": str(c.get("chain_label") or cid),
            "chain_description": str(c.get("chain_description") or ""),
            "direction_to_target_if_active": str(c.get("direction_to_target_if_active") or "unknown")
            if str(c.get("direction_to_target_if_active") or "unknown") in {"increase", "decrease", "mixed", "unknown"}
            else "unknown",
            "chain_confidence": clamp(c.get("chain_confidence", mc.get("default_chain_confidence", 0.55)), 0.0, 1.0),
        })

    if not clean_chains:
        return fallback_mechanism_chain_structure(nodes, reason="LLM mechanism chain output has no valid chains.", config=config)

    chain_ids = {c["chain_id"] for c in clean_chains}
    fallback_chain = clean_chains[0]["chain_id"]
    raw_annotations = obj.get("factor_annotations") if isinstance(obj, dict) else []
    if not isinstance(raw_annotations, list):
        raw_annotations = []
    raw_by_id = {str(a.get("factor_id")): a for a in raw_annotations if isinstance(a, dict) and a.get("factor_id")}

    clean_annotations = []
    for i, n in enumerate(nodes or [], start=1):
        fid = n.get("node_id") or f"factor_{i:02d}"
        a = dict(raw_by_id.get(fid) or {})
        role = str(a.get("mechanism_role") or "unknown")
        if role not in allowed_roles:
            role = "unknown"
        risk = str(a.get("double_counting_risk") or "medium")
        if risk not in allowed_risks:
            risk = "medium"
        cid = _stable_snake_id(a.get("causal_chain_id"), fallback_chain)
        if cid not in chain_ids:
            cid = fallback_chain
        dc_with = a.get("double_counting_with") or []
        if not isinstance(dc_with, list):
            dc_with = []
        dc_with = [str(x) for x in dc_with if str(x) in factor_id_set and str(x) != fid]
        clean_annotations.append({
            "factor_id": fid,
            "factor_label": str(a.get("factor_label") or _factor_label_from_node(n)),
            "causal_chain_id": cid,
            "mechanism_role": role,
            "role_reason": str(a.get("role_reason") or ""),
            "double_counting_risk": risk,
            "double_counting_with": dc_with,
            "recommended_role_discount": clamp(a.get("recommended_role_discount", default_role_discount(role, config=config)), 0.20, 1.00),
            "is_primary_signal_in_chain": bool(a.get("is_primary_signal_in_chain", False)),
        })

    raw_edges = obj.get("weak_edges_for_display") if isinstance(obj, dict) else []
    if not isinstance(raw_edges, list):
        raw_edges = []
    clean_edges = []
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        a = str(e.get("from_factor_id") or "")
        b = str(e.get("to_factor_id") or "")
        if a not in factor_id_set or b not in factor_id_set or a == b:
            continue
        edge_type = str(e.get("edge_type") or "mechanism_support")
        if edge_type not in allowed_edge_types:
            edge_type = "mechanism_support"
        direction = str(e.get("direction") or "unknown")
        if direction not in allowed_edge_dirs:
            direction = "unknown"
        clean_edges.append({
            "from_factor_id": a,
            "to_factor_id": b,
            "edge_type": edge_type,
            "direction": direction,
            "confidence": clamp(e.get("confidence", mc.get("weak_edge_default_confidence", 0.30)), 0.0, 0.70),
            "rationale": str(e.get("rationale") or ""),
        })

    max_edges = int(mc.get("max_weak_edges", 8))
    notes = obj.get("chain_level_notes") if isinstance(obj, dict) else []
    if not isinstance(notes, list):
        notes = []
    warnings = obj.get("warnings") if isinstance(obj, dict) else []
    if not isinstance(warnings, list):
        warnings = []

    return {
        "mechanism_chains": clean_chains,
        "factor_annotations": clean_annotations,
        "weak_edges_for_display": clean_edges[:max_edges],
        "chain_level_notes": notes,
        "warnings": [str(x) for x in warnings],
    }


def structure_mechanism_chains_by_llm(
    original_question: str,
    contract: Dict[str, Any],
    nodes: List[Dict[str, Any]],
    decomposition: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    mc = _mechanism_config(config)
    if not mc.get("llm_enabled", True) or not nodes:
        return fallback_mechanism_chain_structure(nodes, reason="Mechanism chain LLM disabled or no nodes.", config=config)

    factor_payload = []
    for n in nodes:
        factor_payload.append({
            "factor_id": n.get("node_id"),
            "factor_label": n.get("label"),
            "direction_if_true": n.get("direction_if_true"),
            "probability": n.get("prior_probability"),
            "effect_log_odds": n.get("target_effect_log_odds"),
            "confidence": n.get("target_effect_confidence"),
            "dependencies_raw": n.get("dependencies_raw", []),
            "rationale": n.get("rationale", ""),
        })

    expansion_summary = {
        "base_rate": (decomposition or {}).get("base_rate"),
        "known_unknowns": (decomposition or {}).get("known_unknowns"),
        "search_queries": (decomposition or {}).get("search_queries"),
    }
    prompt = MECHANISM_CHAIN_STRUCTURER_PROMPT.format(
        original_question=original_question or contract.get("normalized_question", ""),
        contract_json=json.dumps(contract or {}, ensure_ascii=False, indent=2),
        factors_json=json.dumps(factor_payload, ensure_ascii=False, indent=2),
        expansion_summary_json=json.dumps(expansion_summary, ensure_ascii=False, indent=2),
    )

    try:
        obj = llm_json(
            prompt,
            config=config,
            temperature=float(mc.get("llm_temperature", 0.20)),
            max_tokens=int(mc.get("llm_max_tokens", 4096)),
        )
        return validate_mechanism_chain_structure(obj, nodes=nodes, config=config)
    except Exception as e:
        return fallback_mechanism_chain_structure(
            nodes,
            reason=f"Mechanism chain LLM failed; fallback used: {type(e).__name__}: {e}",
            config=config,
        )


def apply_mechanism_annotations_to_nodes(nodes: List[Dict[str, Any]], structure: Dict[str, Any]) -> None:
    ann_by_id = {a.get("factor_id"): a for a in structure.get("factor_annotations", []) or []}
    for node in nodes:
        ann = ann_by_id.get(node.get("node_id"), {}) or {}
        node["causal_chain_id"] = ann.get("causal_chain_id", "main_chain")
        node["mechanism_role"] = ann.get("mechanism_role", "unknown")
        node["mechanism_role_reason"] = ann.get("role_reason", "")
        node["double_counting_risk"] = ann.get("double_counting_risk", "medium")
        node["double_counting_with"] = ann.get("double_counting_with", [])
        node["recommended_role_discount"] = clamp(ann.get("recommended_role_discount", 0.75), 0.20, 1.00)
        node["is_primary_signal_in_chain"] = bool(ann.get("is_primary_signal_in_chain", False))


def convert_llm_weak_edges_to_graph_edges(structure: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> List[Dict[str, Any]]:
    mc = _mechanism_config(config)
    sign_map = {"positive": 1.0, "negative": -1.0, "mixed": 0.0, "unknown": 0.0}
    max_abs = safe_float(mc.get("weak_edge_max_abs_log_odds", 0.25), 0.25)
    out = []
    for e in structure.get("weak_edges_for_display", []) or []:
        sign = sign_map.get(e.get("direction", "unknown"), 0.0)
        out.append({
            "from": e.get("from_factor_id"),
            "to": e.get("to_factor_id"),
            "effect_log_odds": max_abs * sign,
            "confidence": clamp(e.get("confidence", mc.get("weak_edge_default_confidence", 0.30)), 0.0, 0.70),
            "edge_type": e.get("edge_type", "mechanism_support"),
            "rationale": e.get("rationale", ""),
            "source": "llm_mechanism_structurer",
        })
    return out


def aggregate_chain_effects_from_llm_structure(
    nodes: List[Dict[str, Any]],
    raw_target_weights: Dict[str, float],
    structure: Dict[str, Any],
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    mc = _mechanism_config(config)
    same_w = safe_float(mc.get("same_direction_corroboration_weight", 0.30), 0.30)
    opp_w = safe_float(mc.get("opposite_direction_counter_weight", 0.70), 0.70)
    min_eff = safe_float(mc.get("chain_effect_min_log_odds", -1.50), -1.50)
    max_eff = safe_float(mc.get("chain_effect_max_log_odds", 1.50), 1.50)

    chains_meta = {c.get("chain_id"): c for c in structure.get("mechanism_chains", []) or []}
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes or []:
        cid = n.get("causal_chain_id") or mc.get("fallback_chain_id", "main_chain")
        grouped.setdefault(cid, []).append(n)

    chain_factors: Dict[str, Any] = {}
    for cid, ns in grouped.items():
        effects = []
        for n in ns:
            nid = n["node_id"]
            raw = safe_float(raw_target_weights.get(nid), 0.0)
            role = n.get("mechanism_role", "unknown")
            role_discount = clamp(n.get("recommended_role_discount", default_role_discount(role, config=config)), 0.20, 1.00)
            adjusted = raw * role_discount
            effects.append({
                "node_id": nid,
                "label": n.get("label", nid),
                "raw_effect": raw,
                "adjusted_effect": adjusted,
                "abs_effect": abs(adjusted),
                "mechanism_role": role,
                "double_counting_risk": n.get("double_counting_risk", "medium"),
                "role_discount": role_discount,
                "is_primary_signal_in_chain": bool(n.get("is_primary_signal_in_chain", False)),
                "confidence": clamp(n.get("target_effect_confidence", 0.5), 0.0, 1.0),
                "role_reason": n.get("mechanism_role_reason", ""),
            })
        if not effects:
            continue
        primary_candidates = [e for e in effects if e.get("is_primary_signal_in_chain")]
        if primary_candidates:
            primary = sorted(primary_candidates, key=lambda x: x["abs_effect"], reverse=True)[0]
        else:
            primary = sorted(effects, key=lambda x: x["abs_effect"], reverse=True)[0]

        primary_effect = primary["adjusted_effect"]
        chain_effect = primary_effect
        supporting = []
        for e in effects:
            if e["node_id"] == primary["node_id"]:
                continue
            same_direction = primary_effect * e["adjusted_effect"] > 0
            contribution = (same_w if same_direction else opp_w) * e["adjusted_effect"]
            chain_effect += contribution
            supporting.append({
                **e,
                "same_direction_as_primary": same_direction,
                "contribution_to_chain_effect": contribution,
            })

        meta = chains_meta.get(cid, {}) or {}
        structure_conf = clamp(meta.get("chain_confidence", mc.get("default_chain_confidence", 0.55)), 0.0, 1.0)
        signal_conf = mean([e["confidence"] for e in effects]) if effects else 0.5
        chain_factors[cid] = {
            "chain_id": cid,
            "label": meta.get("chain_label", cid),
            "description": meta.get("chain_description", ""),
            "direction_to_target_if_active": meta.get("direction_to_target_if_active", "unknown"),
            "nodes": [e["node_id"] for e in effects],
            "primary_node": primary["node_id"],
            "primary_signal": primary,
            "supporting_signals": supporting,
            "chain_effect_log_odds": clamp(chain_effect, min_eff, max_eff),
            "chain_confidence": clamp(signal_conf * structure_conf, 0.0, 1.0),
            "node_count": len(effects),
            "double_counting_control": "llm_structured_chain_strongest_signal_plus_partial_corroboration",
        }
    return chain_factors


def compute_chain_state(chain: Dict[str, Any], states: Dict[str, bool]) -> float:
    primary = chain.get("primary_node")
    if primary in states:
        return 1.0 if states[primary] else -1.0
    vals = []
    for nid in chain.get("nodes", []) or []:
        if nid in states:
            vals.append(1.0 if states[nid] else -1.0)
    if not vals:
        return 0.0
    return mean(vals)


def compute_chain_sensitivity(
    graph: Dict[str, Any],
    baseline_p: float,
    config: Dict[str, Any] = CONFIG,
) -> List[Dict[str, Any]]:
    cg = config.get("causal_graph", {})
    mc = _mechanism_config(config)
    chain_factors = (graph.get("target_cpd", {}) or {}).get("chain_factors", {}) or {}
    if not chain_factors:
        return []
    out = []
    base_seed = int(cg.get("random_seed", 42)) + 200000
    n_samples = int(cg.get("sensitivity_samples", 3000))
    for idx, (cid, chain) in enumerate(chain_factors.items()):
        node_ids = [nid for nid in chain.get("nodes", []) or []]
        if not node_ids:
            continue
        res_true = run_causal_graph_monte_carlo(
            graph,
            n_samples=n_samples,
            interventions={nid: True for nid in node_ids},
            seed=base_seed + idx * 2,
            config=config,
        )
        res_false = run_causal_graph_monte_carlo(
            graph,
            n_samples=n_samples,
            interventions={nid: False for nid in node_ids},
            seed=base_seed + idx * 2 + 1,
            config=config,
        )
        do_true = res_true["target_probability"]
        do_false = res_false["target_probability"]
        out.append({
            "chain_id": cid,
            "label": chain.get("label", cid),
            "baseline": baseline_p,
            "do_true": do_true,
            "do_false": do_false,
            "swing": abs(do_true - do_false),
            "primary_node": chain.get("primary_node"),
            "node_count": len(node_ids),
            "chain_effect_log_odds": chain.get("chain_effect_log_odds"),
            "chain_confidence": chain.get("chain_confidence"),
        })
    return sorted(out, key=lambda x: x["swing"], reverse=True)[: int(mc.get("max_chain_sensitivity", 6))]


def build_causal_graph(
    base_p: float,
    factors: List[Dict[str, Any]],
    evidence_cards: List[Dict[str, Any]],
    contract: Optional[Dict[str, Any]] = None,
    decomposition: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    """
    将 decomposition.factors + evidence_cards 转成轻量 Bayesian Causal Graph。

    第一版设计：
    - 每个 factor 变成一个二元/潜变量节点；
    - factor.dependencies 变成节点间有向边；
    - 每个 factor 对目标 Y 的 effect_log_odds 变成 target logistic CPD 权重；
    - evidence_cards 先做 evidence-to-node soft update，无法绑定时作用到 Y。
    """
    engine = config["engine"]
    cg = config.get("causal_graph", {})
    max_nodes = int(cg.get("max_nodes", engine.get("max_factors", 12)))
    max_edges = int(cg.get("max_edges", 32))

    nodes: List[Dict[str, Any]] = []
    name_to_id: Dict[str, str] = {}

    for idx, f in enumerate((factors or [])[:max_nodes], start=1):
        label = str(f.get("factor") or f.get("sub_question") or f"factor_{idx}")
        node_id = slugify_node_id(label, idx)
        original_node_id = node_id
        suffix = 2
        while node_id in {n["node_id"] for n in nodes}:
            node_id = f"{original_node_id}_{suffix}"
            suffix += 1

        prior = clamp(
            f.get("probability", 0.5),
            cg.get("min_node_probability", engine["min_base_probability"]),
            cg.get("max_node_probability", engine["max_base_probability"]),
        )
        confidence = clamp(f.get("confidence", cg.get("default_node_confidence", 0.5)), 0.0, 1.0)
        effect = normalize_factor_effect(f, config=config)

        node = {
            "node_id": node_id,
            "label": label,
            "node_type": "binary_latent",
            "prior_probability": prior,
            "prior_confidence": confidence,
            "evidence_log_odds_update": 0.0,
            "adjusted_prior_probability": prior,
            "target_effect_log_odds": effect,
            "target_effect_confidence": confidence,
            "direction_if_true": f.get("direction_if_true", "mixed"),
            "dependencies_raw": f.get("dependencies", []) or [],
            "rationale": f.get("rationale", ""),
        }
        nodes.append(node)
        for key in [label, str(f.get("sub_question", "")), node_id]:
            if key:
                name_to_id[key.lower().strip()] = node_id

    original_question = str(
        (contract or {}).get("original_question")
        or (contract or {}).get("normalized_question")
        or (contract or {}).get("source_overall_semantic_intent")
        or ""
    )
    mechanism_structure = structure_mechanism_chains_by_llm(
        original_question=original_question,
        contract=contract or {},
        nodes=nodes,
        decomposition=decomposition,
        config=config,
    )
    apply_mechanism_annotations_to_nodes(nodes, mechanism_structure)

    edges: List[Dict[str, Any]] = []
    for node in nodes:
        for dep in node.get("dependencies_raw", []) or []:
            dep_text = str(dep).lower().strip()
            parent_id = name_to_id.get(dep_text)
            if not parent_id:
                best_id, best_score = None, 0.0
                for other in nodes:
                    score = text_overlap_score(dep_text, other.get("label", ""))
                    if score > best_score:
                        best_score = score
                        best_id = other["node_id"]
                if best_score >= 0.25:
                    parent_id = best_id
            if parent_id and parent_id != node["node_id"] and len(edges) < max_edges:
                edges.append({
                    "from": parent_id,
                    "to": node["node_id"],
                    "effect_log_odds": 0.35,
                    "confidence": cg.get("default_edge_confidence", 0.55),
                    "edge_type": "dependency",
                    "rationale": f"由 factor.dependencies 推断：{dep}",
                })

    weak_edges = convert_llm_weak_edges_to_graph_edges(mechanism_structure, config=config)
    for e in weak_edges:
        if len(edges) >= max_edges:
            break
        if e.get("from") and e.get("to") and e.get("from") != e.get("to"):
            edges.append(e)

    target_evidence_update = 0.0
    evidence_links: List[Dict[str, Any]] = []
    for card in evidence_cards or []:
        claim = str(card.get("claim", ""))
        weighted = safe_float(
            card.get("weighted_impact_log_odds", card.get("impact_log_odds", 0.0)),
            0.0,
        )
        best_node = None
        best_score = 0.0
        for node in nodes:
            score = max(
                text_overlap_score(claim, node.get("label", "")),
                text_overlap_score(claim, node.get("rationale", "")),
            )
            if score > best_score:
                best_score = score
                best_node = node

        if best_node and best_score >= 0.18:
            best_node["evidence_log_odds_update"] += weighted
            evidence_links.append({
                "claim": claim[:160],
                "target_node": best_node["node_id"],
                "match_score": best_score,
                "weighted_impact_log_odds": weighted,
            })
        else:
            target_evidence_update += weighted
            evidence_links.append({
                "claim": claim[:160],
                "target_node": "Y",
                "match_score": best_score,
                "weighted_impact_log_odds": weighted,
            })

    for node in nodes:
        update = clamp(
            node.get("evidence_log_odds_update", 0.0),
            -cg.get("node_evidence_max_abs_log_odds", 1.2),
            cg.get("node_evidence_max_abs_log_odds", 1.2),
        )
        node["evidence_log_odds_update"] = update
        node["adjusted_prior_probability"] = clamp(
            sigmoid(logit(node["prior_probability"]) + update),
            cg.get("min_node_probability", 0.02),
            cg.get("max_node_probability", 0.98),
        )

    target_evidence_update = clamp(
        target_evidence_update,
        -cg.get("target_evidence_max_abs_log_odds", 1.0),
        cg.get("target_evidence_max_abs_log_odds", 1.0),
    )

    raw_target_weights = {
        n["node_id"]: n["target_effect_log_odds"] * clamp(n.get("target_effect_confidence", 0.5), 0.0, 1.0)
        for n in nodes
    }
    chain_factors = aggregate_chain_effects_from_llm_structure(
        nodes=nodes,
        raw_target_weights=raw_target_weights,
        structure=mechanism_structure,
        config=config,
    )
    target_parents = list(chain_factors.keys()) if chain_factors else [n["node_id"] for n in nodes]

    return {
        "graph_id": short_id(),
        "target_node": "Y",
        "target_label": (contract or {}).get("normalized_question", "target_event"),
        "nodes": nodes,
        "edges": edges,
        "target_cpd": {
            "type": "mechanism_chain_logistic",
            "base_probability": base_p,
            "target_evidence_log_odds_update": target_evidence_update,
            "parents": target_parents,
            "weights": raw_target_weights,  # 保留 node-level 权重，兼容 node sensitivity 和旧报告。
            "chain_factors": chain_factors,
            "intercept_logit": logit(base_p) + target_evidence_update,
            "double_counting_control": "mechanism_chain_strongest_signal_plus_partial_corroboration",
        },
        "mechanism_structure": mechanism_structure,
        "evidence_links": evidence_links,
        "diagnostics": {
            "graph_confidence": mean([n.get("prior_confidence", 0.5) for n in nodes]) if nodes else 0.5,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "weak_edge_count": len(weak_edges),
            "chain_count": len(chain_factors),
            "target_evidence_update": target_evidence_update,
            "double_counting_control": "enabled",
            "known_bad_assumptions": [
                "v0.5.2 使用 mechanism-chain factor graph 近似完整 Bayesian Network。",
                "机制链由 LLM 结构化，表示预测假设结构，不是已验证事实图谱。",
                "同一机制链内使用 strongest signal + partial corroboration 防重复计数。",
                "weak_edges 仅用于解释展示和链内依赖提示；非严格因果发现。",
                "evidence-to-node binding 使用轻量文本匹配，后续应升级为 embedding/LLM binding。",
            ],
        },
    }


def topological_order_nodes(graph: Dict[str, Any]) -> List[str]:
    nodes = [n["node_id"] for n in graph.get("nodes", [])]
    incoming = {nid: set() for nid in nodes}
    outgoing = {nid: set() for nid in nodes}
    for e in graph.get("edges", []) or []:
        a, b = e.get("from"), e.get("to")
        if a in incoming and b in incoming and a != b:
            incoming[b].add(a)
            outgoing[a].add(b)

    ready = [nid for nid in nodes if not incoming[nid]]
    ordered = []
    while ready:
        nid = ready.pop(0)
        ordered.append(nid)
        for child in list(outgoing.get(nid, [])):
            incoming[child].discard(nid)
            if not incoming[child]:
                ready.append(child)
    for nid in nodes:
        if nid not in ordered:
            ordered.append(nid)
    return ordered


def run_causal_graph_monte_carlo(
    graph: Dict[str, Any],
    n_samples: int,
    interventions: Optional[Dict[str, bool]] = None,
    seed: Optional[int] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    cg = config.get("causal_graph", {})
    rng = random.Random(seed)
    interventions = interventions or {}

    nodes = {n["node_id"]: n for n in graph.get("nodes", [])}
    incoming_edges: Dict[str, List[Dict[str, Any]]] = {nid: [] for nid in nodes}
    for e in graph.get("edges", []) or []:
        if e.get("to") in incoming_edges:
            incoming_edges[e["to"]].append(e)

    order = topological_order_nodes(graph)
    target_cpd = graph.get("target_cpd", {}) or {}
    target_weights = target_cpd.get("weights", {}) or {}
    chain_factors = target_cpd.get("chain_factors", {}) or {}
    cpd_type = target_cpd.get("type", "logistic")
    intercept = safe_float(target_cpd.get("intercept_logit"), logit(target_cpd.get("base_probability", 0.5)))

    y_probs: List[float] = []
    node_true_counts = {nid: 0 for nid in nodes}

    for _ in range(max(1, int(n_samples))):
        states: Dict[str, bool] = {}

        for nid in order:
            node = nodes[nid]
            if nid in interventions:
                states[nid] = bool(interventions[nid])
            else:
                p_node_logit = logit(node.get("adjusted_prior_probability", node.get("prior_probability", 0.5)))
                for e in incoming_edges.get(nid, []):
                    parent = e.get("from")
                    if parent not in states:
                        continue
                    x_parent = 1.0 if states[parent] else -1.0
                    p_node_logit += (
                        safe_float(e.get("effect_log_odds"), 0.0)
                        * safe_float(e.get("confidence"), cg.get("default_edge_confidence", 0.55))
                        * x_parent
                    )
                p_node = clamp(
                    sigmoid(p_node_logit),
                    cg.get("min_node_probability", 0.02),
                    cg.get("max_node_probability", 0.98),
                )
                a, b = beta_params_from_prob_confidence(
                    p_node,
                    node.get("prior_confidence", cg.get("default_node_confidence", 0.5)),
                    config=config,
                )
                p_sample = rng.betavariate(a, b)
                states[nid] = rng.random() < p_sample

            if states[nid]:
                node_true_counts[nid] += 1

        y_logit = intercept
        if cpd_type == "mechanism_chain_logistic" and chain_factors:
            for chain_id, chain in chain_factors.items():
                chain_state = compute_chain_state(chain, states)
                chain_effect = safe_float(chain.get("chain_effect_log_odds"), 0.0)
                chain_conf = clamp(chain.get("chain_confidence", 0.5), 0.0, 1.0)
                y_logit += chain_effect * chain_conf * chain_state
        else:
            for parent, w in target_weights.items():
                if parent not in states:
                    continue
                x = 1.0 if states[parent] else -1.0
                y_logit += safe_float(w, 0.0) * x

        y_p = clamp(
            sigmoid(y_logit),
            cg.get("min_target_probability", 0.01),
            cg.get("max_target_probability", 0.99),
        )
        y_probs.append(y_p)

    return {
        "target_probability": mean(y_probs) if y_probs else 0.5,
        "p05": percentile(y_probs, 0.05),
        "p50": percentile(y_probs, 0.50),
        "p95": percentile(y_probs, 0.95),
        "n_samples": max(1, int(n_samples)),
        "node_marginals": {
            nid: node_true_counts[nid] / max(1, int(n_samples))
            for nid in node_true_counts
        },
    }


def compute_node_sensitivity(
    graph: Dict[str, Any],
    baseline_p: float,
    config: Dict[str, Any] = CONFIG,
) -> List[Dict[str, Any]]:
    cg = config.get("causal_graph", {})
    weights = graph.get("target_cpd", {}).get("weights", {}) or {}
    candidates = sorted(
        graph.get("nodes", []) or [],
        key=lambda n: abs(safe_float(weights.get(n.get("node_id")), 0.0)),
        reverse=True,
    )[: int(cg.get("max_sensitivity_nodes", 6))]

    out = []
    base_seed = int(cg.get("random_seed", 42)) + 100000
    for idx, node in enumerate(candidates):
        nid = node["node_id"]
        n_samples = int(cg.get("sensitivity_samples", 3000))
        res_true = run_causal_graph_monte_carlo(
            graph,
            n_samples=n_samples,
            interventions={nid: True},
            seed=base_seed + idx * 2,
            config=config,
        )
        res_false = run_causal_graph_monte_carlo(
            graph,
            n_samples=n_samples,
            interventions={nid: False},
            seed=base_seed + idx * 2 + 1,
            config=config,
        )
        do_true = res_true["target_probability"]
        do_false = res_false["target_probability"]
        out.append({
            "node_id": nid,
            "label": node.get("label", nid),
            "baseline": baseline_p,
            "do_true": do_true,
            "do_false": do_false,
            "swing": abs(do_true - do_false),
            "target_weight": safe_float(weights.get(nid), 0.0),
        })
    return sorted(out, key=lambda x: x["swing"], reverse=True)


def infer_causal_graph_monte_carlo(
    graph: Dict[str, Any],
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    cg = config.get("causal_graph", {})
    n_samples = int(cg.get("monte_carlo_samples", 12000))
    seed = int(cg.get("random_seed", 42))
    result = run_causal_graph_monte_carlo(
        graph,
        n_samples=n_samples,
        interventions=None,
        seed=seed,
        config=config,
    )
    result["node_sensitivity"] = compute_node_sensitivity(
        graph,
        baseline_p=result["target_probability"],
        config=config,
    )
    result["chain_sensitivity"] = compute_chain_sensitivity(
        graph,
        baseline_p=result["target_probability"],
        config=config,
    )
    return result


def compute_causal_graph_probability(
    base_p: float,
    factors: List[Dict[str, Any]],
    evidence_cards: List[Dict[str, Any]],
    contract: Optional[Dict[str, Any]] = None,
    decomposition: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    graph = build_causal_graph(
        base_p=base_p,
        factors=factors,
        evidence_cards=evidence_cards,
        contract=contract,
        decomposition=decomposition,
        config=config,
    )
    inference = infer_causal_graph_monte_carlo(graph, config=config)
    return {
        "method": "mechanism_chain_factor_graph_monte_carlo",
        "target_probability": clamp(
            inference.get("target_probability", base_p),
            config["engine"]["min_probability"],
            config["engine"]["max_probability"],
        ),
        "credible_interval": [inference.get("p05", base_p), inference.get("p95", base_p)],
        "p50": inference.get("p50", base_p),
        "n_samples": inference.get("n_samples", 0),
        "graph": graph,
        "node_marginals": inference.get("node_marginals", {}),
        "node_sensitivity": inference.get("node_sensitivity", []),
        "chain_sensitivity": inference.get("chain_sensitivity", []),
    }


def compute_causal_probability(
    base_p: float,
    factors: List[Dict[str, Any]],
    config: Dict[str, Any] = CONFIG,
) -> float:
    """向后兼容旧接口：没有证据/合约上下文时，也使用 causal graph 推断。"""
    result = compute_causal_graph_probability(
        base_p=base_p,
        factors=factors,
        evidence_cards=[],
        contract=None,
        decomposition={"factors": factors},
        config=config,
    )
    return result["target_probability"]


def compute_panel_probability(
    agent_runs: List[Dict[str, Any]],
    base_p: float,
    config: Dict[str, Any] = CONFIG,
) -> Tuple[float, float]:
    engine = config["engine"]

    ps = [
        clamp(
            r.get("probability", base_p),
            engine["min_base_probability"],
            engine["max_base_probability"],
        )
        for r in agent_runs
    ]

    if not ps:
        return base_p, 0.0

    logits_all = [logit(p) for p in ps]
    logits_trimmed = sorted(logits_all)

    if len(logits_trimmed) >= 5:
        logits_trimmed = logits_trimmed[1:-1]

    panel_logit = mean(logits_trimmed)
    disagreement = pstdev(logits_all) if len(logits_all) > 1 else 0.0

    return (
        clamp(sigmoid(panel_logit), engine["min_probability"], engine["max_probability"]),
        disagreement,
    )


def ensemble_probabilities(
    base_p: float,
    evidence_p: float,
    causal_p: float,
    panel_p: float,
    forecastability: float,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    engine = config["engine"]
    ew = engine["ensemble_weights"]
    f = clamp(forecastability, 0.0, 1.0)

    weights = {
        "base": ew["base_const"] + ew["base_low_forecastability_bonus"] * (1.0 - f),
        "evidence": ew["evidence_const"] + ew["evidence_forecastability_bonus"] * f,
        "causal": ew["causal_const"] + ew["causal_forecastability_bonus"] * f,
        "panel": ew["panel_const"],
    }

    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    x = (
        weights["base"] * logit(base_p)
        + weights["evidence"] * logit(evidence_p)
        + weights["causal"] * logit(causal_p)
        + weights["panel"] * logit(panel_p)
    )

    p = clamp(
        sigmoid(x),
        engine["min_probability"],
        engine["max_probability"],
    )

    return {
        "probability": p,
        "weights": weights,
    }


def calibrate_probability(
    raw_p: float,
    forecastability: float,
    local_stats: Dict[str, Any],
    config: Dict[str, Any] = CONFIG,
) -> Tuple[float, Dict[str, Any]]:
    engine = config["engine"]

    n = int(local_stats.get("n") or 0)
    avg_brier = local_stats.get("avg_brier")
    f = clamp(forecastability, 0.0, 1.0)

    if n < engine["cold_start_min_history"] or avg_brier is None:
        temperature = (
            engine["cold_start_temperature_base"]
            - engine["cold_start_temperature_forecastability_discount"] * f
        )
        mode = "cold_start_conservative_shrinkage"
    else:
        bt = engine["brier_temperature"]
        avg_brier = float(avg_brier)

        if avg_brier > bt["bad_threshold"]:
            temperature = bt["bad_temperature"]
        elif avg_brier > bt["weak_threshold"]:
            temperature = bt["weak_temperature"]
        elif avg_brier < bt["strong_threshold"]:
            temperature = bt["strong_temperature"]
        else:
            temperature = bt["normal_temperature"]

        mode = "local_brier_temperature"

    calibrated = sigmoid(logit(raw_p) / temperature)

    meta = {
        "calibration_mode": mode,
        "temperature": temperature,
        "domain_history_n": n,
        "domain_avg_brier": avg_brier,
    }

    return (
        clamp(calibrated, engine["min_probability"], engine["max_probability"]),
        meta,
    )


def confidence_interval(
    p: float,
    forecastability: float,
    panel_disagreement: float,
    avg_evidence_quality: float,
    evidence_count: int,
    config: Dict[str, Any] = CONFIG,
) -> Tuple[float, float, Dict[str, Any]]:
    engine = config["engine"]
    interval = engine["interval"]

    f = clamp(forecastability, 0.0, 1.0)
    q = clamp(avg_evidence_quality, 0.0, 1.0)

    n_bonus = min(
        interval["max_evidence_count_bonus"],
        interval["evidence_count_bonus_per_card"] * max(0, evidence_count - 4),
    )

    sigma = (
        interval["base_sigma"]
        + interval["forecastability_penalty"] * (1.0 - f)
        + interval["panel_disagreement_weight"] * min(panel_disagreement, 2.0)
        + interval["evidence_quality_penalty"] * (1.0 - q)
        - n_bonus
    )

    sigma = clamp(
        sigma,
        interval["min_sigma"],
        interval["max_sigma"],
    )

    lo = sigmoid(logit(p) - sigma)
    hi = sigmoid(logit(p) + sigma)

    return (
        clamp(lo, 0.0, 1.0),
        clamp(hi, 0.0, 1.0),
        {"logit_sigma": sigma},
    )


def compute_probability_bundle(
    contract: Dict[str, Any],
    decomposition: Dict[str, Any],
    evidence_obj: Dict[str, Any],
    panel_obj: Dict[str, Any],
    local_stats: Dict[str, Any],
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    engine = config["engine"]

    base_p = clamp(
        (decomposition.get("base_rate") or {}).get("base_probability", 0.5),
        engine["min_base_probability"],
        engine["max_base_probability"],
    )

    forecastability = clamp(
        contract.get("forecastability_score", 0.5),
        0.0,
        1.0,
    )

    evidence_cards, total_evidence_delta, avg_quality = weight_evidence_cards(
        evidence_obj.get("evidence_cards") or [],
        config=config,
    )

    evidence_p = clamp(
        sigmoid(logit(base_p) + total_evidence_delta),
        engine["min_probability"],
        engine["max_probability"],
    )

    causal_graph_result = compute_causal_graph_probability(
        base_p=base_p,
        factors=decomposition.get("factors") or [],
        evidence_cards=evidence_cards,
        contract=contract,
        decomposition=decomposition,
        config=config,
    )
    causal_p = causal_graph_result["target_probability"]

    panel_p, disagreement = compute_panel_probability(
        panel_obj.get("agent_forecasts") or [],
        base_p,
        config=config,
    )

    ensemble = ensemble_probabilities(
        base_p,
        evidence_p,
        causal_p,
        panel_p,
        forecastability,
        config=config,
    )

    raw_p = ensemble["probability"]

    calibrated_p, calibration_meta = calibrate_probability(
        raw_p,
        forecastability,
        local_stats,
        config=config,
    )

    low, high, interval_meta = confidence_interval(
        calibrated_p,
        forecastability,
        disagreement,
        avg_quality,
        len(evidence_cards),
        config=config,
    )

    return {
        "base_probability": base_p,
        "evidence_probability": evidence_p,
        "causal_probability": causal_p,
        "causal_graph_probability": causal_p,
        "causal_graph_result": causal_graph_result,
        "panel_probability": panel_p,
        "raw_probability": raw_p,
        "calibrated_probability": calibrated_p,
        "confidence_low": low,
        "confidence_high": high,
        "weighted_evidence_cards": evidence_cards,
        "total_evidence_delta_log_odds": total_evidence_delta,
        "avg_evidence_quality": avg_quality,
        "panel_disagreement_logit_std": disagreement,
        "ensemble_weights": ensemble["weights"],
        "calibration": calibration_meta,
        "interval": interval_meta,
    }
