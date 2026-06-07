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
    probability_to_percent,
    json_dumps,
    current_date_context_text,
    strip_think_blocks,
    extract_json_object,
    llm_json,
    normalize_weight_list,
    has_cloud_term,
    risk_factor,
    get_record_probability,
    empty_store,
    load_store,
    save_store,
    save_forecast_record,
    find_forecast,
    update_forecast_record,
    local_domain_brier_stats,
)
from agent_panel import run_forecaster_panel,build_evidence_cards,decompose_question

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
            "target_evidence_log_odds_update": target_evidence_update,
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
            "known_bad_assumptions": [
                "第一版使用 logistic CPD 近似完整条件概率表。",
                "factor.dependencies 仅用于弱依赖边；非严格因果发现。",
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
        "method": "bayesian_causal_graph_logistic_cpd_monte_carlo",
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
