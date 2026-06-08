# -*- coding: utf-8 -*-
"""
Superforecast MVP - Markdown 结果输出版 / 模块化版
版本：v0.6-md-output-module

核心改动：
1. 第一层不再直接 build_contract。
2. 内嵌 Cloud-to-Contract 多 Agent 拆题逻辑，不再依赖 question_decomposition_agents.py。
3. 对 cloud_judgment 自动走 multi_contract_portfolio。
4. 单个 contract 仍沿用原有 decomposition / evidence / panel / probability engine。
5. causal_probability 使用 Mechanism Chain Factor Graph + Monte Carlo 推断，链内防重复计数。
6. reporter.py 专门生成清晰 Markdown 报告；utils.py 负责每题一个 Markdown/JSON 文件输出。
7. 报告中明确展示：
   - question_type
   - semantic_collapse_risk
   - lost_dimensions
   - contract portfolio
   - 每个维度概率
   - 综合概率
"""
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Tuple, Optional


from config import CONFIG
from agent0_11 import run_question_decomposition  # 内嵌版 question decomposition 逻辑
from utils import (
    now_iso,
    short_id,
    clamp,
    safe_float,
    logit,
    sigmoid,
    probability_to_percent,
    risk_factor,
    get_record_probability,
    load_store,
    save_forecast_record,
    find_forecast,
    update_forecast_record,
    local_domain_brier_stats,
)
from agent_panel import run_forecaster_panel,build_evidence_cards,decompose_question
from pengine import compute_probability_bundle
from reporter import (
    build_single_report_json,
    build_single_markdown_report,
    build_portfolio_report_json,
    build_portfolio_markdown_report,
)

def expand_question(question: str, config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    """
    主流程第一步入口：调用内嵌 Cloud-to-Contract 多 Agent 拆题模块，
    并转换成后续 run_forecast 需要的 legacy expansion 结构。
    """
    decomposition_record = run_question_decomposition(question, config=config)
    final = decomposition_record.get("final", {}) or {}
    audit = final.get("semantic_collapse_audit", {}) or {}

    expansion = dict(final)
    expansion["semantic_collapse_risk"] = audit.get("semantic_collapse_risk", "unknown")
    expansion["collapse_reason"] = audit.get("collapse_reason", "")
    expansion["lost_dimensions_if_single_metric"] = audit.get("lost_dimensions_if_single_metric", [])
    expansion["recommended_mode"] = audit.get("recommended_mode", "single_contract")
    expansion["allowed_single_contract"] = audit.get("allowed_single_contract", True)
    expansion["recommended_user_choice_prompt"] = final.get("recommended_user_choice_prompt", "")
    expansion["decomposition_record_id"] = decomposition_record.get("id")
    expansion["decomposition_module"] = decomposition_record.get("module")
    expansion["decomposition_validation_errors"] = decomposition_record.get("validation_errors", [])
    return expansion

def contract_from_candidate(candidate: Dict[str, Any], expansion: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(candidate)

    contract = {
        "normalized_question": c.get("normalized_question", ""),
        "target_type": "binary",
        "deadline": c.get("deadline", ""),
        "resolution_criteria": c.get("resolution_criteria", ""),
        "resolution_sources": c.get("resolution_sources", []),
        "domain": c.get("domain", "other"),
        "forecastability_score": clamp(c.get("forecastability_score", 0.5), 0.0, 1.0),
        "ambiguity_flags": c.get("ambiguity_flags", []),
        "clarifying_assumptions": c.get("clarifying_assumptions", []),
        "reason": c.get("reason", ""),

        # 新增字段：用于防止语义坍缩
        "contract_id": c.get("contract_id", ""),
        "dimension_id": c.get("dimension_id", ""),
        "dimension_name": c.get("dimension_name", ""),
        "semantic_coverage_weight": clamp(c.get("semantic_coverage_weight", 0.0), 0.0, 1.0),
        "measurability": clamp(c.get("measurability", 0.5), 0.0, 1.0),
        "user_intent_preservation_score": clamp(c.get("user_intent_preservation_score", 0.5), 0.0, 1.0),
        "proxy_metric": c.get("proxy_metric", ""),
        "proxy_risk": c.get("proxy_risk", "unknown"),
        "lost_dimensions": c.get("lost_dimensions", []),

        "source_question_type": expansion.get("question_type", "mixed"),
        "source_semantic_collapse_risk": expansion.get("semantic_collapse_risk", "unknown"),
        "source_overall_semantic_intent": expansion.get("overall_semantic_intent", ""),
    }

    return contract


# =============================================================================
# 9. Portfolio 聚合
# =============================================================================

def compute_portfolio_probability(
    expansion: Dict[str, Any],
    sub_records: List[Dict[str, Any]],
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    items = []

    for r in sub_records:
        contract = r["contract"]
        engine = r["probability_engine"]

        p = float(engine["calibrated_probability"])
        lo = float(engine["confidence_low"])
        hi = float(engine["confidence_high"])

        semantic_w = safe_float(contract.get("semantic_coverage_weight"), 0.0)
        meas = safe_float(contract.get("measurability"), 0.5)
        intent = safe_float(contract.get("user_intent_preservation_score"), 0.5)
        proxy = risk_factor(contract.get("proxy_risk", "unknown"), config=config)

        raw_weight = semantic_w * (0.5 + 0.5 * meas) * (0.5 + 0.5 * intent) * proxy

        items.append({
            "forecast_id": r["id"],
            "contract_id": contract.get("contract_id", ""),
            "dimension_id": contract.get("dimension_id", ""),
            "dimension_name": contract.get("dimension_name", ""),
            "normalized_question": contract.get("normalized_question", ""),
            "proxy_metric": contract.get("proxy_metric", ""),
            "proxy_risk": contract.get("proxy_risk", "unknown"),
            "semantic_coverage_weight": semantic_w,
            "measurability": meas,
            "user_intent_preservation_score": intent,
            "risk_factor": proxy,
            "raw_portfolio_weight": raw_weight,
            "probability": p,
            "confidence_low": lo,
            "confidence_high": hi,
        })

    s = sum(max(0.0, x["raw_portfolio_weight"]) for x in items)
    if s <= 0:
        n = max(1, len(items))
        for x in items:
            x["portfolio_weight"] = 1.0 / n
    else:
        for x in items:
            x["portfolio_weight"] = max(0.0, x["raw_portfolio_weight"]) / s

    if not items:
        return {
            "calibrated_probability": 0.5,
            "confidence_low": 0.2,
            "confidence_high": 0.8,
            "portfolio_items": [],
            "method": "empty_fallback",
        }

    # logit 加权，而不是概率线性平均
    x = 0.0
    for item in items:
        x += item["portfolio_weight"] * logit(item["probability"])
    p = clamp(sigmoid(x), 0.01, 0.99)

    logits = [logit(item["probability"]) for item in items]
    disagreement = pstdev(logits) if len(logits) > 1 else 0.0

    interval_cfg = config["portfolio"]["portfolio_interval"]
    risk = str(expansion.get("semantic_collapse_risk", "unknown")).lower()
    risk_penalty = interval_cfg["semantic_risk_penalty"].get(
        risk,
        interval_cfg["semantic_risk_penalty"]["unknown"],
    )

    sigma = (
        interval_cfg["base_sigma"]
        + risk_penalty
        + interval_cfg["subforecast_disagreement_weight"] * min(disagreement, 2.0)
    )
    sigma = clamp(sigma, interval_cfg["min_sigma"], interval_cfg["max_sigma"])

    low = clamp(sigmoid(logit(p) - sigma), 0.0, 1.0)
    high = clamp(sigmoid(logit(p) + sigma), 0.0, 1.0)

    return {
        "calibrated_probability": p,
        "confidence_low": low,
        "confidence_high": high,
        "portfolio_items": items,
        "method": "weighted_logit_portfolio",
        "subforecast_logit_disagreement": disagreement,
        "portfolio_logit_sigma": sigma,
        "semantic_collapse_risk": expansion.get("semantic_collapse_risk", "unknown"),
    }






# =============================================================================
# 10. 主流程
# =============================================================================

def run_single_contract_forecast(
    question: str,
    contract: Dict[str, Any],
    user_evidence: str = "",
    expansion: Optional[Dict[str, Any]] = None,
    config: Dict[str, Any] = CONFIG,
    save: bool = False,
    print_report: bool = False,
    print_prefix: str = "",
) -> Dict[str, Any]:
    runtime = config["runtime"]

    def step(msg: str):
        if runtime.get("print_steps", True):
            print(f"{print_prefix}{msg}")

    step("[single 1/4] 拆解问题、生成参考类和因子...")
    decomposition = decompose_question(question, contract, expansion=expansion, config=config)
    if runtime.get("print_intermediate_json", True):
        print(f"{print_prefix}问题拆解:", json.dumps(decomposition, ensure_ascii=False, indent=2))

    step("[single 2/4] 结构化证据卡...")
    evidence_obj = build_evidence_cards(
        question,
        contract,
        decomposition,
        user_evidence=user_evidence,
        expansion=expansion,
        config=config,
    )
    if runtime.get("print_intermediate_json", True):
        print(f"{print_prefix}证据卡:", json.dumps(evidence_obj, ensure_ascii=False, indent=2))

    step("[single 3/4] 运行多 Agent 预测委员会...")
    panel_obj = run_forecaster_panel(
        question,
        contract,
        decomposition,
        evidence_obj,
        expansion=expansion,
        config=config,
    )
    if runtime.get("print_intermediate_json", True):
        print(f"{print_prefix}Panel 结果:", json.dumps(panel_obj, ensure_ascii=False, indent=2))

    step("[single 4/4] 概率聚合、校准...")
    domain = str(contract.get("domain", "other"))
    stats = local_domain_brier_stats(domain, config=config)

    prob = compute_probability_bundle(
        contract,
        decomposition,
        evidence_obj,
        panel_obj,
        stats,
        config=config,
    )

    if runtime.get("print_intermediate_json", True):
        cg = prob.get("causal_graph_result", {}) or {}
        graph = cg.get("graph", {}) or {}
        diag = graph.get("diagnostics", {}) or {}
        print(
            f"{print_prefix}Causal Graph 摘要:",
            json.dumps(
                {
                    "method": cg.get("method"),
                    "target_probability": cg.get("target_probability"),
                    "credible_interval": cg.get("credible_interval"),
                    "n_samples": cg.get("n_samples"),
                    "node_count": diag.get("node_count"),
                    "edge_count": diag.get("edge_count"),
                    "top_chain_sensitivity": (cg.get("chain_sensitivity") or [])[:3],
                    "top_node_sensitivity": (cg.get("node_sensitivity") or [])[:3],
                    "chain_count": diag.get("chain_count"),
                    "weak_edge_count": diag.get("weak_edge_count"),
                    "double_counting_control": diag.get("double_counting_control"),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    forecast_id = short_id()

    report_json = build_single_report_json(
        forecast_id,
        question,
        contract,
        decomposition,
        evidence_obj,
        panel_obj,
        prob,
        expansion=expansion,
        config=config,
    )

    markdown_report = build_single_markdown_report(report_json)

    record = {
        **report_json,
        "markdown_report": markdown_report,
    }

    if save:
        output_paths = save_forecast_record(record, config=config)
        if runtime.get("print_steps", True) and output_paths.get("markdown"):
            print(f"{print_prefix}Markdown 已输出：{output_paths.get('markdown')}")

    if print_report:
        print("\n" + markdown_report)

    return record


def run_forecast(
    question: str,
    user_evidence: str = "",
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    runtime = config["runtime"]

    def step(msg: str):
        if runtime.get("print_steps", True):
            print(msg)

    step("[0/6] 原始问题语义展开...")
    expansion = expand_question(question, config=config)

    if runtime.get("print_expansion_json", True):
        print("语义展开:", json.dumps(expansion, ensure_ascii=False, indent=2))

    mode = expansion.get("recommended_mode", "single_contract")
    candidates = expansion.get("contract_candidates", []) or []

    # single contract
    if mode == "single_contract" and expansion.get("allowed_single_contract", True):
        step("[1/6] 使用 single_contract 模式...")
        contract = contract_from_candidate(candidates[0], expansion)

        if runtime.get("print_intermediate_json", True):
            print("最终预测合约:", json.dumps(contract, ensure_ascii=False, indent=2))

        record = run_single_contract_forecast(
            question,
            contract,
            user_evidence=user_evidence,
            expansion=expansion,
            config=config,
            save=True,
            print_report=runtime.get("print_markdown", True),
        )
        return record

    # ask_user_to_choose 暂时不阻塞；MVP 自动转 portfolio
    if mode == "ask_user_to_choose":
        if len(candidates) >= 2:
            step("[1/6] recommended_mode=ask_user_to_choose，但 MVP 自动使用 portfolio 模式继续...")
            mode = "multi_contract_portfolio"
        else:
            step("[1/6] recommended_mode=ask_user_to_choose，但只有一个候选合约，使用 single_contract fallback...")
            contract = contract_from_candidate(candidates[0], expansion)
            record = run_single_contract_forecast(
                question,
                contract,
                user_evidence=user_evidence,
                expansion=expansion,
                config=config,
                save=True,
                print_report=runtime.get("print_markdown", True),
            )
            return record

    # portfolio
    if mode in {"multi_contract_portfolio", "distribution_forecast", "mixed"} or not expansion.get("allowed_single_contract", True):
        step("[1/6] 使用 multi_contract_portfolio 模式...")

        max_n = config["portfolio"]["max_contract_candidates"]
        sub_records = []

        for idx, cand in enumerate(candidates[:max_n], start=1):
            contract = contract_from_candidate(cand, expansion)
            print("")
            step(f"[2-5/6] 子合约 {idx}/{min(len(candidates), max_n)}：{contract.get('dimension_name')}")

            if runtime.get("print_intermediate_json", True):
                print("子预测合约:", json.dumps(contract, ensure_ascii=False, indent=2))

            sub = run_single_contract_forecast(
                question,
                contract,
                user_evidence=user_evidence,
                expansion=expansion,
                config=config,
                save=False,
                print_report=runtime.get("print_subcontract_reports", False),
                print_prefix=f"[{idx}] ",
            )
            sub_records.append(sub)

        step("[6/6] 聚合 portfolio 概率并输出 Markdown...")
        portfolio_engine = compute_portfolio_probability(
            expansion,
            sub_records,
            config=config,
        )

        forecast_id = short_id()
        report_json = build_portfolio_report_json(
            forecast_id,
            question,
            expansion,
            sub_records,
            portfolio_engine,
            config=config,
        )
        markdown_report = build_portfolio_markdown_report(report_json)

        record = {
            **report_json,
            "markdown_report": markdown_report,
        }

        output_paths = save_forecast_record(record, config=config)
        if runtime.get("print_steps", True) and output_paths.get("markdown"):
            print(f"Markdown 已输出：{output_paths.get('markdown')}")

        if runtime.get("print_markdown", True):
            print("\n" + markdown_report)

        if runtime.get("print_raw_json", False):
            print("\n--- RAW JSON ---")
            print(json.dumps(record, ensure_ascii=False, indent=2))

        return record

    # 未知模式兜底
    step(f"[fallback] 未知 recommended_mode={mode}，使用第一个合约。")
    contract = contract_from_candidate(candidates[0], expansion)
    record = run_single_contract_forecast(
        question,
        contract,
        user_evidence=user_evidence,
        expansion=expansion,
        config=config,
        save=True,
        print_report=runtime.get("print_markdown", True),
    )
    return record


# =============================================================================
# 11. 本地管理函数
# =============================================================================

def list_forecasts(config: Dict[str, Any] = CONFIG, limit: int = 20) -> List[Dict[str, Any]]:
    store = load_store(config)
    items = store.get("forecasts", [])
    items = sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    for item in items:
        p = get_record_probability(item)
        p_str = probability_to_percent(p)

        status = item.get("status", "open")
        brier = item.get("brier_score")
        brier_str = f", brier={float(brier):.4f}" if brier is not None else ""

        kind = item.get("forecast_kind", "unknown")
        if kind == "multi_contract_portfolio":
            question = item.get("original_question", "")
        else:
            question = item.get("contract", {}).get("normalized_question", item.get("original_question", ""))

        print(f'{item.get("id")} | {item.get("created_at")} | {kind} | {p_str} | {status}{brier_str} | {question}')

    return items


def show_forecast(
    forecast_id: str,
    config: Dict[str, Any] = CONFIG,
    raw_json: bool = False,
) -> Dict[str, Any]:
    item = find_forecast(forecast_id, config=config)
    if item is None:
        raise ValueError(f"forecast_id 不存在：{forecast_id}")

    print(item.get("markdown_report", ""))

    if raw_json:
        print("\n--- RAW JSON ---")
        print(json.dumps(item, ensure_ascii=False, indent=2))

    return item


def resolve_forecast(
    forecast_id: str,
    outcome: int,
    config: Dict[str, Any] = CONFIG,
    force: bool = False,
) -> Dict[str, Any]:
    if outcome not in (0, 1):
        raise ValueError("outcome 只能是 0 或 1")

    item = find_forecast(forecast_id, config=config)
    if item is None:
        raise ValueError(f"forecast_id 不存在：{forecast_id}")

    if item.get("status") == "resolved" and not force:
        raise ValueError("该预测已经结算。如果要覆盖，设置 force=True。")

    p = get_record_probability(item)
    brier = (p - outcome) ** 2

    patch = {
        "status": "resolved",
        "outcome": outcome,
        "resolved_at": now_iso(),
        "brier_score": brier,
    }

    updated = update_forecast_record(forecast_id, patch, config=config)

    print(f"Resolved {forecast_id}: outcome={outcome}, p={p:.4f}, brier={brier:.4f}")
    return updated


def export_forecast(
    forecast_id: str,
    out_path: str,
    config: Dict[str, Any] = CONFIG,
    fmt: str = "md",
) -> str:
    item = find_forecast(forecast_id, config=config)
    if item is None:
        raise ValueError(f"forecast_id 不存在：{forecast_id}")

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "md":
        path.write_text(item.get("markdown_report", ""), encoding="utf-8")
    else:
        raise ValueError("fmt 只能是 md 或 json")

    print(f"已导出：{path}")
    return str(path)


def stability_test(
    question: str,
    user_evidence: str = "",
    n: int = 3,
    config: Dict[str, Any] = CONFIG,
) -> Dict[str, Any]:
    """
    同一个问题跑 n 次，看第一层是否稳定。
    注意：会真实调用 LLM n 次，并输出 n 份 Markdown/JSON 文件。
    """
    results = []
    for i in range(n):
        print(f"\n========== stability run {i+1}/{n} ==========")
        r = run_forecast(question, user_evidence=user_evidence, config=config)
        results.append({
            "id": r["id"],
            "kind": r.get("forecast_kind"),
            "p": get_record_probability(r),
            "question_type": (r.get("question_expansion") or {}).get("question_type"),
            "semantic_collapse_risk": (r.get("question_expansion") or {}).get("semantic_collapse_risk"),
            "recommended_mode": (r.get("question_expansion") or {}).get("recommended_mode"),
            "contracts": [
                c.get("normalized_question")
                for c in (r.get("question_expansion") or {}).get("contract_candidates", [])
            ],
        })

    ps = [x["p"] for x in results]
    out = {
        "runs": results,
        "mean": mean(ps) if ps else None,
        "min": min(ps) if ps else None,
        "max": max(ps) if ps else None,
        "spread": (max(ps) - min(ps)) if ps else None,
    }
    print("\n========== stability summary ==========")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


# =============================================================================
# 12. 直接运行示例
# =============================================================================
# 你在 ipynb 里主要改这里
# 中国在近20年是否会发生战争
# 2028年固态电池是否会普及？
# 2028年后北京房价会不会小幅上涨？
# 2030年中美会不会发生军事冲突？
# 明年中国鸡肉价格会不会上涨？
# 预测万物的世界模型在2027年是否会实现
QUESTION = """
ai会促进共产主义的实现吗？
""".strip()

USER_EVIDENCE = """
""".strip()

if __name__ == "__main__":
    print("原始问题:", QUESTION)
    record = run_forecast(QUESTION, USER_EVIDENCE, CONFIG)
