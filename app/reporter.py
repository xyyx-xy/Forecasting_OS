# -*- coding: utf-8 -*-
"""
reporter.py

只负责把预测中间结果整理成清晰 Markdown 和结构化 report_json。
主流程 main.py 不在这里做 LLM 调用，也不做概率计算。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CONFIG
from utils import now_iso, safe_float, probability_to_percent


def top_evidence(cards: List[Dict[str, Any]], k: int = 6) -> List[Dict[str, Any]]:
    return sorted(
        cards,
        key=lambda c: abs(safe_float(c.get("weighted_impact_log_odds"), 0.0)),
        reverse=True,
    )[:k]

def build_single_report_json(
    forecast_id: str,
    original_question: str,
    contract: Dict[str, Any],
    decomposition: Dict[str, Any],
    evidence_obj: Dict[str, Any],
    panel_obj: Dict[str, Any],
    prob: Dict[str, Any],
    expansion: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    return {
        "id": forecast_id,
        "forecast_kind": "single_contract",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "open",
        "outcome": None,
        "resolved_at": None,
        "brier_score": None,
        "original_question": original_question,
        "question_expansion": expansion,
        "contract": contract,
        "decomposition": decomposition,
        "evidence": {
            **evidence_obj,
            "evidence_cards": prob["weighted_evidence_cards"],
        },
        "panel": panel_obj,
        "probability_engine": {
            k: v
            for k, v in prob.items()
            if k not in {"weighted_evidence_cards"}
        },
        "runtime_config_snapshot": {
            "model": config["model"],
            "base_url": config["base_url"],
            "engine": config["engine"],
            "temperature": config["temperature"],
        },
    }

def build_single_markdown_report(report: Dict[str, Any]) -> str:
    contract = report["contract"]
    decomp = report["decomposition"]
    engine = report["probability_engine"]
    cards = report["evidence"]["evidence_cards"]
    panel = report.get("panel", {}).get("agent_forecasts", [])

    p = float(engine["calibrated_probability"])
    low = float(engine["confidence_low"])
    high = float(engine["confidence_high"])

    base_rate = decomp.get("base_rate", {}) or {}
    factors = decomp.get("factors", []) or []
    known_unknowns = decomp.get("known_unknowns", []) or []
    ambiguity_flags = contract.get("ambiguity_flags", []) or []
    assumptions = contract.get("clarifying_assumptions", []) or []

    lines = []

    lines.append(f"# Forecast {report['id']}")
    lines.append("")
    lines.append(f"**预测类型**：single_contract")
    lines.append(f"**预测题**：{contract.get('normalized_question', '')}")
    lines.append(f"**最终概率**：{probability_to_percent(p)}")
    lines.append(f"**粗略区间**：{probability_to_percent(low)} - {probability_to_percent(high)}")
    lines.append(f"**截止日期**：{contract.get('deadline', '')}")
    lines.append(f"**领域**：{contract.get('domain', 'other')}")
    lines.append(f"**可预测性评分**：{safe_float(contract.get('forecastability_score'), 0.5):.2f}")

    if contract.get("dimension_name"):
        lines.append("")
        lines.append("## 语义覆盖信息")
        lines.append(f"- 当前维度：{contract.get('dimension_name')}")
        lines.append(f"- 代理指标：{contract.get('proxy_metric')}")
        lines.append(f"- proxy_risk：{contract.get('proxy_risk')}")
        lines.append(f"- 原意保留分：{safe_float(contract.get('user_intent_preservation_score'), 0.0):.2f}")
        lines.append(f"- 语义覆盖权重：{safe_float(contract.get('semantic_coverage_weight'), 0.0):.2f}")
        lost = contract.get("lost_dimensions", []) or []
        if lost:
            lines.append(f"- 该子合约未覆盖：{', '.join(map(str, lost[:8]))}")

    lines.append("")
    lines.append("## 判定标准")
    lines.append(str(contract.get("resolution_criteria", "")))
    sources = contract.get("resolution_sources", []) or []
    if sources:
        lines.append(f"判定来源：{', '.join(map(str, sources))}")
    lines.append("")

    lines.append("## 概率计算拆解")
    lines.append(f"- Base rate prior：{probability_to_percent(engine['base_probability'])}")
    lines.append(f"- Evidence update 后：{probability_to_percent(engine['evidence_probability'])}")
    lines.append(f"- Mechanism Chain Factor Graph / Monte Carlo 后：{probability_to_percent(engine['causal_probability'])}")
    lines.append(f"- 多 Agent panel 聚合后：{probability_to_percent(engine['panel_probability'])}")
    lines.append(f"- Raw ensemble：{probability_to_percent(engine['raw_probability'])}")
    lines.append(f"- Calibrated final：{probability_to_percent(engine['calibrated_probability'])}")
    lines.append("")

    lines.append("## Ensemble 权重")
    weights = engine.get("ensemble_weights", {})
    for k, v in weights.items():
        lines.append(f"- {k}: {float(v):.3f}")
    lines.append("")

    lines.append("## 参考类 / Base Rate")
    lines.append(f"参考类：{base_rate.get('reference_class', '')}")
    lines.append(f"先验概率：{probability_to_percent(safe_float(base_rate.get('base_probability'), 0.5))}")
    lines.append(f"置信度：{safe_float(base_rate.get('confidence'), 0.5):.2f}")
    lines.append(f"说明：{base_rate.get('rationale', '')}")
    lines.append("")

    lines.append("## 关键因子")
    if factors:
        for f in factors[:8]:
            lines.append(
                f"- **{f.get('factor', '')}**："
                f"P={probability_to_percent(safe_float(f.get('probability'), 0.5))}，"
                f"effect_log_odds={safe_float(f.get('effect_log_odds'), 0.0):+.2f}，"
                f"方向={f.get('direction_if_true', '')}。"
                f"{f.get('rationale', '')}"
            )
    else:
        lines.append("- 无结构化因子。")
    lines.append("")

    causal_result = engine.get("causal_graph_result", {}) or {}
    causal_graph = causal_result.get("graph", {}) or {}
    if causal_graph:
        lines.append("## Bayesian Causal Graph / Mechanism Chain Factor Graph")
        lines.append(f"- method：{causal_result.get('method')}")
        lines.append(f"- Monte Carlo samples：{causal_result.get('n_samples')}")
        ci = causal_result.get("credible_interval", []) or []
        if len(ci) == 2:
            lines.append(
                f"- causal credible interval：{probability_to_percent(ci[0])} - {probability_to_percent(ci[1])}"
            )
        diag = causal_graph.get("diagnostics", {}) or {}
        lines.append(
            f"- node_count：{diag.get('node_count')}, "
            f"edge_count：{diag.get('edge_count')}, "
            f"chain_count：{diag.get('chain_count')}, "
            f"weak_edge_count：{diag.get('weak_edge_count')}"
        )
        lines.append(f"- double_counting_control：{diag.get('double_counting_control', 'unknown')}")
        lines.append(f"- target_evidence_update：{safe_float(diag.get('target_evidence_update'), 0.0):+.3f}")

        nodes = causal_graph.get("nodes", []) or []
        weights = (causal_graph.get("target_cpd", {}) or {}).get("weights", {}) or {}
        if nodes:
            lines.append("- 关键节点：")
            top_nodes = sorted(
                nodes,
                key=lambda n: abs(safe_float(weights.get(n.get("node_id")), 0.0)),
                reverse=True,
            )[:6]
            for n in top_nodes:
                nid = n.get("node_id")
                lines.append(
                    f"  - {n.get('label', nid)} | "
                    f"prior={probability_to_percent(n.get('prior_probability'))}, "
                    f"adjusted={probability_to_percent(n.get('adjusted_prior_probability'))}, "
                    f"target_weight={safe_float(weights.get(nid), 0.0):+.3f}"
                )

        target_cpd = causal_graph.get("target_cpd", {}) or {}
        chains = target_cpd.get("chain_factors", {}) or {}
        if chains:
            lines.append("- Mechanism Chain Audit：")
            for cid, chain in list(chains.items())[:6]:
                primary = chain.get("primary_signal", {}) or {}
                support = chain.get("supporting_signals", []) or []
                lines.append(
                    f"  - {chain.get('label', cid)} ({cid}) | "
                    f"effect={safe_float(chain.get('chain_effect_log_odds'), 0.0):+.3f}, "
                    f"confidence={safe_float(chain.get('chain_confidence'), 0.0):.2f}, "
                    f"nodes={chain.get('node_count')}"
                )
                lines.append(f"    - primary：{primary.get('label', primary.get('node_id', ''))}")
                if support:
                    support_labels = [str(x.get('label', x.get('node_id'))) for x in support[:4]]
                    lines.append(f"    - supporting：{', '.join(support_labels)}")
                lines.append(f"    - control：{chain.get('double_counting_control')}")

        chain_sens = causal_result.get("chain_sensitivity", []) or []
        if chain_sens:
            lines.append("- chain-level sensitivity：")
            for s in chain_sens[:5]:
                lines.append(
                    f"  - {s.get('label', s.get('chain_id'))}: "
                    f"do_true={probability_to_percent(s.get('do_true'))}, "
                    f"do_false={probability_to_percent(s.get('do_false'))}, "
                    f"swing={safe_float(s.get('swing'), 0.0):.3f}"
                )

        sens = causal_result.get("node_sensitivity", []) or []
        if sens:
            lines.append("- node-level do-intervention sensitivity：")
            for s in sens[:5]:
                lines.append(
                    f"  - {s.get('label', s.get('node_id'))}: "
                    f"do_true={probability_to_percent(s.get('do_true'))}, "
                    f"do_false={probability_to_percent(s.get('do_false'))}, "
                    f"swing={safe_float(s.get('swing'), 0.0):.3f}"
                )
        lines.append("")

    lines.append("## 最有诊断价值的证据")
    top_cards = top_evidence(cards, k=6)
    if top_cards:
        for c in top_cards:
            lines.append(
                f"- [{c.get('direction', 'neutral')}] {c.get('claim', '')} "
                f"| weighted_log_odds={safe_float(c.get('weighted_impact_log_odds'), 0.0):+.3f} "
                f"| quality_weight={safe_float(c.get('quality_weight'), 0.0):.3f} "
                f"| source={c.get('source_type', '')}/{c.get('source', '')}"
            )
            rat = str(c.get("rationale", "")).strip()
            if rat:
                lines.append(f"  - {rat}")
    else:
        lines.append("- 无证据卡。")
    lines.append("")

    lines.append("## 多 Agent 分歧")
    if panel:
        for r in panel:
            lines.append(
                f"- **{r.get('agent_name', 'agent')}**："
                f"{probability_to_percent(safe_float(r.get('probability'), 0.5))}，"
                f"confidence={safe_float(r.get('confidence'), 0.5):.2f}。"
                f"{r.get('rationale', '')}"
            )
            trigger = str(r.get("strongest_update_trigger", "")).strip()
            if trigger:
                lines.append(f"  - 更新触发器：{trigger}")
    else:
        lines.append("- 无 panel 结果。")
    lines.append("")

    if known_unknowns:
        lines.append("## 关键未知项")
        for x in known_unknowns[:8]:
            lines.append(f"- {x}")
        lines.append("")

    if ambiguity_flags or assumptions:
        lines.append("## 模糊点与假设")
        for x in ambiguity_flags[:8]:
            lines.append(f"- 模糊点：{x}")
        for x in assumptions[:8]:
            lines.append(f"- 假设：{x}")
        lines.append("")

    cal = engine.get("calibration", {})
    lines.append("## 校准信息")
    lines.append(f"- calibration_mode：{cal.get('calibration_mode')}")
    lines.append(f"- temperature：{safe_float(cal.get('temperature'), 1.0):.3f}")
    lines.append(f"- domain_history_n：{cal.get('domain_history_n')}")
    lines.append(f"- domain_avg_brier：{cal.get('domain_avg_brier')}")
    lines.append("")

    lines.append("## 结论")
    lines.append(
        f"当前给出的概率是 **{probability_to_percent(p)}**。"
        f"这个数字由 base rate、证据 log-odds、Mechanism Chain Factor Graph / Monte Carlo、多 Agent panel 和本地校准共同计算得到。"
    )

    return "\n".join(lines).strip() + "\n"

def build_portfolio_report_json(
    forecast_id: str,
    original_question: str,
    expansion: Dict[str, Any],
    sub_records: List[Dict[str, Any]],
    portfolio_engine: Dict[str, Any],
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    domains = []
    for r in sub_records:
        domains.append(r.get("contract", {}).get("domain", "other"))
    dominant_domain = max(set(domains), key=domains.count) if domains else "other"

    return {
        "id": forecast_id,
        "forecast_kind": "multi_contract_portfolio",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "open",
        "outcome": None,
        "resolved_at": None,
        "brier_score": None,
        "original_question": original_question,
        "question_expansion": expansion,
        "sub_forecasts": sub_records,
        "portfolio_probability_engine": portfolio_engine,
        "portfolio_meta": {
            "dominant_domain": dominant_domain,
            "subforecast_count": len(sub_records),
        },
        "runtime_config_snapshot": {
            "model": config["model"],
            "base_url": config["base_url"],
            "portfolio": config["portfolio"],
            "engine": config["engine"],
            "temperature": config["temperature"],
        },
    }

def build_portfolio_markdown_report(report: Dict[str, Any]) -> str:
    expansion = report["question_expansion"]
    engine = report["portfolio_probability_engine"]
    items = engine.get("portfolio_items", [])
    sub_records = report.get("sub_forecasts", [])

    p = float(engine["calibrated_probability"])
    low = float(engine["confidence_low"])
    high = float(engine["confidence_high"])

    lines = []
    lines.append(f"# Forecast {report['id']}")
    lines.append("")
    lines.append("**预测类型**：multi_contract_portfolio")
    lines.append(f"**原始问题**：{report.get('original_question', '')}")
    lines.append(f"**综合概率**：{probability_to_percent(p)}")
    lines.append(f"**粗略区间**：{probability_to_percent(low)} - {probability_to_percent(high)}")
    lines.append(f"**问题类型**：{expansion.get('question_type')}")
    lines.append(f"**语义坍缩风险**：{expansion.get('semantic_collapse_risk')}")
    lines.append(f"**推荐模式**：{expansion.get('recommended_mode')}")
    lines.append("")

    lines.append("## 原始语义")
    lines.append(str(expansion.get("overall_semantic_intent", "")))
    collapse_reason = str(expansion.get("collapse_reason", "")).strip()
    if collapse_reason:
        lines.append("")
        lines.append(f"语义坍缩说明：{collapse_reason}")
    lost = expansion.get("lost_dimensions_if_single_metric", []) or []
    if lost:
        lines.append("")
        lines.append("如果强行单指标化，会丢失这些维度：")
        for x in lost[:10]:
            lines.append(f"- {x}")
    lines.append("")

    lines.append("## 维度展开")
    dims = expansion.get("dimension_map", []) or []
    if dims:
        for d in dims:
            lines.append(
                f"- **{d.get('dimension_name', d.get('dimension_id'))}** "
                f"| weight={safe_float(d.get('semantic_coverage_weight'), 0.0):.2f} "
                f"| measurability={safe_float(d.get('measurability'), 0.0):.2f} "
                f"| {d.get('meaning', '')}"
            )
    else:
        lines.append("- 无维度展开。")
    lines.append("")

    lines.append("## Contract Portfolio 结果")
    if items:
        for item in sorted(items, key=lambda x: x.get("portfolio_weight", 0.0), reverse=True):
            lines.append(
                f"- **{item.get('dimension_name')}** "
                f"| P={probability_to_percent(item.get('probability'))} "
                f"| weight={safe_float(item.get('portfolio_weight'), 0.0):.3f} "
                f"| proxy={item.get('proxy_metric')} "
                f"| proxy_risk={item.get('proxy_risk')}"
            )
            lines.append(f"  - 预测题：{item.get('normalized_question')}")
    else:
        lines.append("- 无 portfolio item。")
    lines.append("")

    lines.append("## 子预测摘要")
    for r in sub_records:
        c = r["contract"]
        e = r["probability_engine"]
        lines.append(
            f"- **{c.get('dimension_name', c.get('contract_id'))}**："
            f"{probability_to_percent(e.get('calibrated_probability'))} "
            f"区间 {probability_to_percent(e.get('confidence_low'))} - {probability_to_percent(e.get('confidence_high'))}"
        )
        lines.append(f"  - contract：{c.get('normalized_question')}")
        lines.append(
            f"  - base={probability_to_percent(e.get('base_probability'))}, "
            f"evidence={probability_to_percent(e.get('evidence_probability'))}, "
            f"causal={probability_to_percent(e.get('causal_probability'))}, "
            f"panel={probability_to_percent(e.get('panel_probability'))}"
        )

        cg = e.get("causal_graph_result", {}) or {}
        graph = cg.get("graph", {}) or {}
        if cg:
            ci = cg.get("credible_interval", []) or []
            ci_text = ""
            if len(ci) == 2:
                ci_text = f", causal_interval={probability_to_percent(ci[0])}-{probability_to_percent(ci[1])}"

            diag = graph.get("diagnostics", {}) or {}
            lines.append(
                f"  - causal_graph：method={cg.get('method')}, "
                f"samples={cg.get('n_samples')}, "
                f"nodes={diag.get('node_count')}, "
                f"edges={diag.get('edge_count')}, "
                f"chains={diag.get('chain_count')}, "
                f"weak_edges={diag.get('weak_edge_count')}, "
                f"double_counting={diag.get('double_counting_control', 'unknown')}"
                f"{ci_text}"
            )

            chain_sens = cg.get("chain_sensitivity", []) or []
            if chain_sens:
                lines.append("  - top chain sensitivity：")
                for s in chain_sens[:3]:
                    lines.append(
                        f"    - {s.get('label', s.get('chain_id'))}: "
                        f"do_true={probability_to_percent(s.get('do_true'))}, "
                        f"do_false={probability_to_percent(s.get('do_false'))}, "
                        f"swing={safe_float(s.get('swing'), 0.0):.3f}"
                    )

            sens = cg.get("node_sensitivity", []) or []
            if sens:
                lines.append("  - top causal sensitivity：")
                for s in sens[:3]:
                    lines.append(
                        f"    - {s.get('label', s.get('node_id'))}: "
                        f"do_true={probability_to_percent(s.get('do_true'))}, "
                        f"do_false={probability_to_percent(s.get('do_false'))}, "
                        f"swing={safe_float(s.get('swing'), 0.0):.3f}"
                    )
    lines.append("")

    lines.append("## 聚合方法")
    lines.append("- 使用 weighted logit portfolio，不是简单平均概率。")
    lines.append("- 权重由 semantic_coverage_weight、measurability、user_intent_preservation_score、proxy_risk 共同决定。")
    lines.append(f"- 子预测 logit 分歧：{safe_float(engine.get('subforecast_logit_disagreement'), 0.0):.3f}")
    lines.append(f"- portfolio logit sigma：{safe_float(engine.get('portfolio_logit_sigma'), 0.0):.3f}")
    lines.append("")

    lines.append("## 结论")
    lines.append(
        f"对原始云状问题，当前综合概率是 **{probability_to_percent(p)}**。"
    )

    return "\n".join(lines).strip() + "\n"
