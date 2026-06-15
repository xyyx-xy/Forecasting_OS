from __future__ import annotations


import json
import math
import random
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Tuple, Optional


from model import llm_qwen
from config import CONFIG
from agent0_11 import run_question_decomposition  # 内嵌版 question decomposition 逻辑
from schema import DECOMPOSITION_SCHEMA, EVIDENCE_SCHEMA, PANEL_SCHEMA
from utils import (
    now_iso,
    short_id,
    clamp,
    safe_float,
    logit,
    sigmoid,
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


# -----------------------------------------------------------------------------
# v0.5.3: uncertainty propagation helpers
# -----------------------------------------------------------------------------

def uncertainty_sampling_config(config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    return (config.get("causal_graph", {}) or {}).get("uncertainty_sampling", {}) or {}


def summarize_numeric_samples(values: List[float]) -> Dict[str, Any]:
    xs = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    if not xs:
        return {"n": 0, "mean": None, "std": None, "p05": None, "p50": None, "p95": None}
    return {
        "n": len(xs),
        "mean": mean(xs),
        "std": pstdev(xs) if len(xs) > 1 else 0.0,
        "p05": percentile(xs, 0.05),
        "p50": percentile(xs, 0.50),
        "p95": percentile(xs, 0.95),
    }


def sample_probability_around(
    p: float,
    confidence: float,
    rng: random.Random,
    config: Dict[str, Any] = CONFIG,
    min_p: Optional[float] = None,
    max_p: Optional[float] = None,
    enabled: bool = True,
) -> float:
    cg = config.get("causal_graph", {}) or {}
    lo = cg.get("min_target_probability", 0.01) if min_p is None else min_p
    hi = cg.get("max_target_probability", 0.99) if max_p is None else max_p
    p = clamp(p, lo, hi)
    if not enabled:
        return p
    a, b = beta_params_from_prob_confidence(p, confidence, config=config)
    return clamp(rng.betavariate(a, b), lo, hi)


def sample_log_odds_effect(
    effect: float,
    confidence: float,
    rng: random.Random,
    config: Dict[str, Any] = CONFIG,
) -> float:
    us = uncertainty_sampling_config(config)
    if not us.get("enabled", True) or not us.get("sample_factor_effect", True):
        return safe_float(effect, 0.0)

    e = safe_float(effect, 0.0)
    c = clamp(confidence, 0.0, 1.0)
    sigma = (
        safe_float(us.get("factor_effect_sigma_min"), 0.03)
        + (1.0 - c) * safe_float(us.get("factor_effect_sigma_max"), 0.45)
        + abs(e) * (1.0 - c) * safe_float(us.get("factor_effect_relative_sigma"), 0.20)
    )
    clip_abs = safe_float(
        us.get("factor_effect_clip_abs"),
        config.get("engine", {}).get("max_factor_effect_log_odds", 1.5),
    )
    return clamp(rng.gauss(e, sigma), -clip_abs, clip_abs)


def sample_evidence_delta(
    delta: float,
    confidence: float,
    rng: random.Random,
    config: Dict[str, Any] = CONFIG,
) -> float:
    us = uncertainty_sampling_config(config)
    d = safe_float(delta, 0.0)
    if not us.get("enabled", True) or not us.get("sample_evidence_update", True):
        return d
    if abs(d) < 1e-12 and not us.get("sample_evidence_noise_when_zero", False):
        return 0.0

    c = clamp(confidence, 0.0, 1.0)
    sigma = (
        safe_float(us.get("evidence_delta_sigma_min"), 0.02)
        + (1.0 - c) * safe_float(us.get("evidence_delta_sigma_max"), 0.35)
        + abs(d) * (1.0 - c) * safe_float(us.get("evidence_delta_relative_sigma"), 0.25)
    )
    clip_abs = safe_float(
        us.get("evidence_delta_clip_abs"),
        (config.get("causal_graph", {}) or {}).get("target_evidence_max_abs_log_odds", 1.0),
    )
    return clamp(rng.gauss(d, sigma), -clip_abs, clip_abs)


def sample_target_logit_noise(
    graph_confidence: float,
    rng: random.Random,
    config: Dict[str, Any] = CONFIG,
) -> float:
    us = uncertainty_sampling_config(config)
    if not us.get("enabled", True) or not us.get("sample_target_logit_noise", True):
        return 0.0
    c = clamp(graph_confidence, 0.0, 1.0)
    sigma = (
        safe_float(us.get("target_logit_noise_sigma_min"), 0.0)
        + (1.0 - c) * safe_float(us.get("target_logit_noise_sigma_max"), 0.30)
    )
    if sigma <= 0:
        return 0.0
    return rng.gauss(0.0, sigma)


def compute_causal_graph_confidence(
    inference: Dict[str, Any],
    graph: Dict[str, Any],
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    cg = config.get("causal_graph", {}) or {}
    cc = cg.get("confidence_label", {}) or {}
    diag = graph.get("diagnostics", {}) or {}

    p05 = safe_float(inference.get("p05"), 0.5)
    p95 = safe_float(inference.get("p95"), 0.5)
    width = max(0.0, p95 - p05)
    node_count = int(diag.get("node_count") or len(graph.get("nodes", []) or []))
    edge_count = int(diag.get("edge_count") or len(graph.get("edges", []) or []))
    edge_ratio = edge_count / max(1, node_count - 1)

    wide_t = safe_float(cc.get("wide_interval_threshold"), 0.55)
    med_t = safe_float(cc.get("medium_interval_threshold"), 0.30)
    sparse_t = safe_float(cc.get("sparse_edge_ratio_threshold"), 0.35)

    score = safe_float(diag.get("graph_confidence"), 0.5)
    penalties = []

    if width >= wide_t:
        score -= 0.30
        penalties.append("wide_interval")
    elif width >= med_t:
        score -= 0.12
        penalties.append("medium_interval")

    if edge_ratio < sparse_t and node_count >= 4:
        score -= 0.18
        penalties.append("sparse_dag")

    if node_count < 3:
        score -= 0.10
        penalties.append("few_nodes")

    score = clamp(score, 0.0, 1.0)
    low_t = safe_float(cc.get("low_score_threshold"), 0.40)
    medium_t = safe_float(cc.get("medium_score_threshold"), 0.70)
    if score < low_t:
        label = "low"
    elif score < medium_t:
        label = "medium"
    else:
        label = "high"

    if width >= wide_t:
        interval_label = "low"
    elif width >= med_t:
        interval_label = "medium"
    else:
        interval_label = "high"

    return {
        "confidence_score": score,
        "confidence_label": label,
        "interval_width": width,
        "interval_confidence_label": interval_label,
        "edge_ratio": edge_ratio,
        "penalties": penalties,
    }


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

    base_meta = (decomposition or {}).get("base_rate") or {}
    base_confidence = clamp(
        base_meta.get("confidence", base_meta.get("base_rate_confidence", cg.get("default_base_confidence", 0.5))),
        0.0,
        1.0,
    )

    evidence_quality_values: List[float] = []
    for c in evidence_cards or []:
        q = c.get("quality_weight")
        if q is None:
            q = (
                safe_float(c.get("relevance"), 0.5)
                * safe_float(c.get("reliability"), 0.5)
                * safe_float(c.get("diagnosticity"), 0.5)
                * safe_float(c.get("freshness"), 0.5)
            )
        evidence_quality_values.append(clamp(q, 0.0, 1.0))
    evidence_update_confidence = (
        mean(evidence_quality_values)
        if evidence_quality_values
        else cg.get("default_evidence_update_confidence", 0.45)
    )

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

    target_parents = [n["node_id"] for n in nodes]
    target_weights = {
        n["node_id"]: n["target_effect_log_odds"] * clamp(n.get("target_effect_confidence", 0.5), 0.0, 1.0)
        for n in nodes
    }

    return {
        "graph_id": short_id(),
        "target_node": "Y",
        "target_label": (contract or {}).get("normalized_question", "target_event"),
        "nodes": nodes,
        "edges": edges,
        "target_cpd": {
            "type": "logistic",
            "base_probability": base_p,
            "base_confidence": base_confidence,
            "target_evidence_log_odds_update": target_evidence_update,
            "evidence_update_confidence": evidence_update_confidence,
            "evidence_card_count": len(evidence_cards or []),
            "parents": target_parents,
            "weights": target_weights,
            "intercept_logit": logit(base_p) + target_evidence_update,
        },
        "evidence_links": evidence_links,
        "diagnostics": {
            "graph_confidence": mean([n.get("prior_confidence", 0.5) for n in nodes]) if nodes else 0.5,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "target_evidence_update": target_evidence_update,
            "base_confidence": base_confidence,
            "evidence_update_confidence": evidence_update_confidence,
            "uncertainty_sampling": (cg.get("uncertainty_sampling", {}) or {}).get("enabled", True),
            "known_bad_assumptions": [
                "使用 logistic CPD 近似完整条件概率表。",
                "factor.dependencies 仅用于弱依赖边；非严格因果发现。",
                "evidence-to-node binding 使用轻量文本匹配，后续应升级为 embedding/LLM binding。",
                "v0.5.3 Monte Carlo 传播 base/evidence/effect/target-logit 不确定性，但仍不是真实世界仿真。",
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
    """
    v0.5.3 uncertainty propagation Monte Carlo.

    旧版主要采样 factor true/false 状态。
    现在每轮同时传播：
    - base rate 不确定性；
    - factor 状态不确定性；
    - factor effect 不确定性；
    - evidence update 不确定性；
    - target logit 残差不确定性。

    注意：这不是“真实世界仿真”，而是把预测假设的不确定性传播到目标概率。
    """
    cg = config.get("causal_graph", {}) or {}
    us = uncertainty_sampling_config(config)
    sampling_enabled = bool(us.get("enabled", True))
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

    base_p_mean = clamp(
        target_cpd.get("base_probability", 0.5),
        cg.get("min_target_probability", 0.01),
        cg.get("max_target_probability", 0.99),
    )
    base_confidence = clamp(
        target_cpd.get("base_confidence", graph.get("diagnostics", {}).get("base_confidence", cg.get("default_base_confidence", 0.5))),
        0.0,
        1.0,
    )
    target_evidence_delta_mean = safe_float(target_cpd.get("target_evidence_log_odds_update"), 0.0)
    evidence_update_confidence = clamp(
        target_cpd.get("evidence_update_confidence", graph.get("diagnostics", {}).get("evidence_update_confidence", cg.get("default_evidence_update_confidence", 0.45))),
        0.0,
        1.0,
    )
    graph_confidence = clamp((graph.get("diagnostics", {}) or {}).get("graph_confidence", 0.5), 0.0, 1.0)

    y_probs: List[float] = []
    node_true_counts = {nid: 0 for nid in nodes}

    base_p_samples: List[float] = []
    evidence_delta_samples: List[float] = []
    target_logit_noise_samples: List[float] = []
    sampled_weight_values: List[float] = []

    n = max(1, int(n_samples))
    for _ in range(n):
        states: Dict[str, bool] = {}

        # 1) factor state uncertainty：节点概率 Beta 采样 + Bernoulli 状态采样。
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

                if sampling_enabled and us.get("sample_factor_state", True):
                    a, b = beta_params_from_prob_confidence(
                        p_node,
                        node.get("prior_confidence", cg.get("default_node_confidence", 0.5)),
                        config=config,
                    )
                    p_sample = rng.betavariate(a, b)
                    states[nid] = rng.random() < p_sample
                else:
                    states[nid] = rng.random() < p_node

            if states[nid]:
                node_true_counts[nid] += 1

        # 2) base rate uncertainty：每轮采样 base_p。
        base_p_sample = sample_probability_around(
            base_p_mean,
            base_confidence,
            rng,
            config=config,
            min_p=cg.get("min_target_probability", 0.01),
            max_p=cg.get("max_target_probability", 0.99),
            enabled=sampling_enabled and us.get("sample_base_rate", True),
        )

        # 3) evidence update uncertainty：每轮采样 target evidence delta。
        evidence_delta_sample = sample_evidence_delta(
            target_evidence_delta_mean,
            evidence_update_confidence,
            rng,
            config=config,
        )
        if not sampling_enabled:
            evidence_delta_sample = target_evidence_delta_mean

        # 4) target logit uncertainty：模型/结构残差噪声。
        target_logit_noise = sample_target_logit_noise(graph_confidence, rng, config=config)
        if not sampling_enabled:
            target_logit_noise = 0.0

        y_logit = logit(base_p_sample) + evidence_delta_sample + target_logit_noise

        # 5) factor effect uncertainty：每轮扰动 factor 对目标的 log-odds 影响强度。
        for parent, w in target_weights.items():
            if parent not in states:
                continue
            parent_node = nodes.get(parent, {})
            effect_confidence = clamp(
                parent_node.get("target_effect_confidence", parent_node.get("prior_confidence", cg.get("default_node_confidence", 0.5))),
                0.0,
                1.0,
            )
            w_sample = sample_log_odds_effect(
                safe_float(w, 0.0),
                effect_confidence,
                rng,
                config=config,
            ) if sampling_enabled else safe_float(w, 0.0)
            sampled_weight_values.append(w_sample)

            x = 1.0 if states[parent] else -1.0
            y_logit += w_sample * x

        y_p = clamp(
            sigmoid(y_logit),
            cg.get("min_target_probability", 0.01),
            cg.get("max_target_probability", 0.99),
        )
        y_probs.append(y_p)
        base_p_samples.append(base_p_sample)
        evidence_delta_samples.append(evidence_delta_sample)
        target_logit_noise_samples.append(target_logit_noise)

    uncertainty_diagnostics = {
        "sampling_enabled": sampling_enabled,
        "sampled_components": {
            "base_rate_uncertainty": bool(us.get("sample_base_rate", True)) and sampling_enabled,
            "factor_state_uncertainty": bool(us.get("sample_factor_state", True)) and sampling_enabled,
            "factor_effect_uncertainty": bool(us.get("sample_factor_effect", True)) and sampling_enabled,
            "evidence_update_uncertainty": bool(us.get("sample_evidence_update", True)) and sampling_enabled,
            "target_logit_uncertainty": bool(us.get("sample_target_logit_noise", True)) and sampling_enabled,
        },
        "base_probability_samples": summarize_numeric_samples(base_p_samples),
        "target_evidence_delta_samples": summarize_numeric_samples(evidence_delta_samples),
        "target_logit_noise_samples": summarize_numeric_samples(target_logit_noise_samples),
        "sampled_target_weight_values": summarize_numeric_samples(sampled_weight_values),
        "interpretation": (
            "Monte Carlo samples uncertainty in assumptions, not real-world trajectories: "
            "base rate, factor states, factor effects, evidence update, and target-logit residual noise."
        ),
    }

    return {
        "target_probability": mean(y_probs) if y_probs else 0.5,
        "p05": percentile(y_probs, 0.05),
        "p50": percentile(y_probs, 0.50),
        "p95": percentile(y_probs, 0.95),
        "n_samples": n,
        "node_marginals": {
            nid: node_true_counts[nid] / max(1, n)
            for nid in node_true_counts
        },
        "uncertainty_diagnostics": uncertainty_diagnostics,
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
    graph_confidence = compute_causal_graph_confidence(inference, graph, config=config)
    return {
        "method": "bayesian_causal_graph_uncertainty_propagation_monte_carlo",
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
        "uncertainty_diagnostics": inference.get("uncertainty_diagnostics", {}),
        "causal_graph_confidence": graph_confidence,
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


# 流程测试
def _assert_probability(x: Any, name: str) -> None:
    assert isinstance(x, (int, float)), f"{name} should be numeric, got {type(x)}"
    assert math.isfinite(float(x)), f"{name} should be finite, got {x}"
    assert 0.0 <= float(x) <= 1.0, f"{name} should be in [0, 1], got {x}"


def build_mock_inputs() -> Dict[str, Any]:
    contract = {
        "normalized_question": "2027年中国鸡肉批发均价是否高于2026年平均水平？",
        "resolution_criteria": "比较2027年1-12月全国鸡肉批发均价与2026年1-12月均价。",
        "forecastability_score": 0.62,
        "domain": "business",
        "deadline": "2028-02-28",
        "proxy_metric": "全国鸡肉批发均价",
        "proxy_risk": "low",
    }

    decomposition = {
        "base_rate": {
            "reference_class": "中国农产品价格年度同比变动",
            "base_probability": 0.46,
            "confidence": 0.62,
            "rationale": "年度农产品价格涨跌大致均衡，略偏保守。",
        },
        "factors": [
            {
                "factor": "2026年供给过剩导致的产能去化",
                "probability": 0.60,
                "confidence": 0.66,
                "effect_log_odds": 0.80,
                "direction_if_true": "increase",
                "dependencies": [],
                "rationale": "若2026年亏损导致产能去化，2027年供给收缩会推高鸡价。",
            },
            {
                "factor": "头部企业产能扩张计划执行",
                "probability": 0.70,
                "confidence": 0.62,
                "effect_log_odds": -0.65,
                "direction_if_true": "decrease",
                "dependencies": ["2026年供给过剩导致的产能去化"],
                "rationale": "头部企业扩产会抵消产能去化，压制价格上涨。",
            },
            {
                "factor": "饲料成本上涨",
                "probability": 0.42,
                "confidence": 0.58,
                "effect_log_odds": 0.45,
                "direction_if_true": "increase",
                "dependencies": [],
                "rationale": "玉米豆粕等饲料成本上行会抬升养殖成本。",
            },
            {
                "factor": "猪肉价格高位带来的替代效应",
                "probability": 0.52,
                "confidence": 0.55,
                "effect_log_odds": 0.50,
                "direction_if_true": "increase",
                "dependencies": [],
                "rationale": "猪肉价格高会增强鸡肉替代需求。",
            },
            {
                "factor": "宏观经济与消费需求疲软",
                "probability": 0.38,
                "confidence": 0.57,
                "effect_log_odds": -0.55,
                "direction_if_true": "decrease",
                "dependencies": [],
                "rationale": "需求疲软会压制肉类消费和价格上涨空间。",
            },
        ],
    }

    evidence_obj = {
        "evidence_cards": [
            {
                "claim": "如果2026年行业亏损扩大，父母代种鸡淘汰会增加，2027年供给可能收缩。",
                "stance": "increase",
                "impact_log_odds": 0.35,
                "relevance": 0.85,
                "reliability": 0.70,
                "diagnosticity": 0.75,
                "freshness": 0.60,
                "independence_group": "supply_cycle",
                "source_type": "mock_prior",
            },
            {
                "claim": "若头部企业扩产按计划落地，2027年商品代出栏量可能偏高。",
                "stance": "decrease",
                "impact_log_odds": -0.28,
                "relevance": 0.80,
                "reliability": 0.68,
                "diagnosticity": 0.70,
                "freshness": 0.60,
                "independence_group": "capacity_expansion",
                "source_type": "mock_prior",
            },
            {
                "claim": "猪肉价格上行会提升鸡肉替代需求，但强度取决于居民消费能力。",
                "stance": "increase",
                "impact_log_odds": 0.20,
                "relevance": 0.70,
                "reliability": 0.65,
                "diagnosticity": 0.60,
                "freshness": 0.55,
                "independence_group": "substitution_demand",
                "source_type": "mock_prior",
            },
        ]
    }

    panel_obj = {
        "agent_forecasts": [
            {"agent_name": "outside_view", "probability": 0.47, "confidence": 0.65},
            {"agent_name": "inside_view", "probability": 0.57, "confidence": 0.66},
            {"agent_name": "skeptic", "probability": 0.40, "confidence": 0.62},
            {"agent_name": "base_rate_guardian", "probability": 0.46, "confidence": 0.75},
            {"agent_name": "domain_generalist", "probability": 0.52, "confidence": 0.68},
        ]
    }

    local_stats = {"n": 0, "avg_brier": None}

    return {
        "contract": contract,
        "decomposition": decomposition,
        "evidence_obj": evidence_obj,
        "panel_obj": panel_obj,
        "local_stats": local_stats,
    }


def test_compute_probability_bundle_input_output_shape() -> Dict[str, Any]:

    from config import CONFIG
    from pengine import compute_probability_bundle
    import copy
    
    config = copy.deepcopy(CONFIG)

    # Keep the unit test fast while still exercising Monte Carlo and sensitivity.
    config["causal_graph"]["monte_carlo_samples"] = 300
    config["causal_graph"]["sensitivity_samples"] = 80
    config["causal_graph"]["random_seed"] = 123

    inputs = build_mock_inputs()
    result = compute_probability_bundle(
        inputs["contract"],
        inputs["decomposition"],
        inputs["evidence_obj"],
        inputs["panel_obj"],
        inputs["local_stats"],
        config=config,
    )

    required_top_keys = {
        "base_probability",
        "evidence_probability",
        "causal_probability",
        "causal_graph_probability",
        "causal_graph_result",
        "panel_probability",
        "raw_probability",
        "calibrated_probability",
        "confidence_low",
        "confidence_high",
        "weighted_evidence_cards",
        "total_evidence_delta_log_odds",
        "avg_evidence_quality",
        "panel_disagreement_logit_std",
        "ensemble_weights",
        "calibration",
        "interval",
    }
    missing = required_top_keys - set(result.keys())
    assert not missing, f"Missing top-level keys: {sorted(missing)}"

    for key in [
        "base_probability",
        "evidence_probability",
        "causal_probability",
        "causal_graph_probability",
        "panel_probability",
        "raw_probability",
        "calibrated_probability",
        "confidence_low",
        "confidence_high",
    ]:
        _assert_probability(result[key], key)

    assert result["confidence_low"] <= result["calibrated_probability"] <= result["confidence_high"]
    assert len(result["weighted_evidence_cards"]) == len(inputs["evidence_obj"]["evidence_cards"])
    assert 0.99 <= sum(result["ensemble_weights"].values()) <= 1.01

    cg = result["causal_graph_result"]
    assert cg["method"] == "bayesian_causal_graph_uncertainty_propagation_monte_carlo"
    _assert_probability(cg["target_probability"], "causal_graph_result.target_probability")
    assert cg["n_samples"] == config["causal_graph"]["monte_carlo_samples"]
    assert len(cg["credible_interval"]) == 2
    assert 0.0 <= cg["credible_interval"][0] <= cg["credible_interval"][1] <= 1.0

    graph = cg["graph"]
    assert graph["target_node"] == "Y"
    assert len(graph["nodes"]) == len(inputs["decomposition"]["factors"])
    assert graph["target_cpd"]["type"] == "logistic"
    assert graph["diagnostics"]["node_count"] == len(inputs["decomposition"]["factors"])

    diagnostics = cg["uncertainty_diagnostics"]
    components = diagnostics["sampled_components"]
    assert components["base_rate_uncertainty"] is True
    assert components["factor_state_uncertainty"] is True
    assert components["factor_effect_uncertainty"] is True
    assert components["evidence_update_uncertainty"] is True
    assert components["target_logit_uncertainty"] is True
    assert diagnostics["base_probability_samples"]["n"] == config["causal_graph"]["monte_carlo_samples"]
    assert diagnostics["target_evidence_delta_samples"]["n"] == config["causal_graph"]["monte_carlo_samples"]
    assert diagnostics["target_logit_noise_samples"]["n"] == config["causal_graph"]["monte_carlo_samples"]
    assert diagnostics["sampled_target_weight_values"]["n"] > 0

    confidence = cg["causal_graph_confidence"]
    assert confidence["confidence_label"] in {"low", "medium", "high"}
    assert confidence["interval_confidence_label"] in {"low", "medium", "high"}
    assert 0.0 <= confidence["confidence_score"] <= 1.0
    assert confidence["interval_width"] >= 0.0

    assert isinstance(cg["node_sensitivity"], list)
    assert cg["node_sensitivity"], "node_sensitivity should not be empty for factor-rich input"
    for row in cg["node_sensitivity"]:
        _assert_probability(row["do_true"], "node_sensitivity.do_true")
        _assert_probability(row["do_false"], "node_sensitivity.do_false")
        assert row["swing"] >= 0.0

    return result


if __name__ == "__main__":
    output = test_compute_probability_bundle_input_output_shape()
    cg = output["causal_graph_result"]
    print("compute_probability_bundle smoke test passed.")
    print(f"final calibrated_probability = {output['calibrated_probability']:.4f}")
    print(f"causal_probability = {output['causal_probability']:.4f}")
    print(f"causal interval = {cg['credible_interval'][0]:.4f} - {cg['credible_interval'][1]:.4f}")
    print(f"causal_graph_confidence = {cg['causal_graph_confidence']['confidence_label']}")
