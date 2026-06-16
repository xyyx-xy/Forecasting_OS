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
from openai import OpenAI

from config import CONFIG
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
# =============================================================================
# 5. Question Expansion / Contract 生成
# =============================================================================
def run_question_decomposition(question: str, config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    """
    内嵌版 Cloud-to-Contract Multi-Agent Decomposition。

    只做：问题类型识别、云状语义展开、Contract Portfolio 生成和审计。
    不做：概率预测、证据检索、后续概率聚合。
    """
    CONFIG = {
        "api_key": "0",
        # macstudio
        "base_url": "http://127.0.0.1:1234/v1",
        "model": "Qwen3.5-27B",

        "storage_path": "./question_decomposition_store.json",

        "llm": {
            "max_tokens": 100000,
            "top_p": 0.95,
            "system": "You are a rigorous superforecasting question decomposition assistant. Output exactly what the user asks for.",
        },

        "temperature": {
            "classifier": 0.05,
            "intent": 0.10,
            "cloud_expander": 0.15,
            "fermi": 0.20,
            "outside_view": 0.20,
            "inside_view": 0.25,
            "proxy_generator": 0.15,
            "contract_builder": 0.10,
            "proxy_auditor": 0.05,
            "adversarial": 0.25,
            "collapse_auditor": 0.05,
            "synthesizer": 0.05,
            "json_repair": 0.00,
        },

        "cloud_question": {
            "cloud_terms": [
                "更好", "更差", "改善", "恶化", "成功", "失败", "爆发", "崩溃",
                "变强", "变弱", "繁荣", "衰退", "领先", "落后", "有前途", "没前途",
                "过得好", "幸福", "压力", "景气", "复苏", "危机", "牛市", "熊市",
                "普及", "主流", "取代", "流行", "火", "好起来", "坏下去"
            ],
            "min_dimensions_for_cloud": 5,
            "min_contracts_for_cloud": 3,
            "max_dimensions": 10,
            "max_contracts": 8,
            "min_intent_preservation_for_single_contract": 0.70,
            "force_multi_contract_when_cloud": True,
            "high_risk_blocks_single_contract": True,
        },

        "normalization": {
            "default_proxy_risk": "unknown",
            "default_measurability": 0.50,
            "default_forecastability": 0.50,
            "default_intent_preservation": 0.60,
        },

        "runtime": {
            "print_steps": True,
            "print_agent_outputs": True,
            "save_record": True,
        },
    }

    CONFIG["api_key"] = config.get("api_key", CONFIG["api_key"])
    CONFIG["base_url"] = config.get("base_url", CONFIG["base_url"])
    CONFIG["model"] = config.get("model", CONFIG["model"])
    CONFIG["storage_path"] = config.get(
        "question_decomposition_storage_path",
        CONFIG.get("storage_path", "./question_decomposition_store.json"),
    )
    CONFIG["llm"]["max_tokens"] = config.get("llm", {}).get("max_tokens", CONFIG["llm"]["max_tokens"])
    CONFIG["llm"]["top_p"] = config.get("llm", {}).get("top_p", CONFIG["llm"]["top_p"])

    runtime = config.get("runtime", {})
    CONFIG["runtime"]["print_steps"] = runtime.get("print_steps", True)
    CONFIG["runtime"]["print_agent_outputs"] = runtime.get("print_expansion_json", True)
    CONFIG["runtime"]["save_record"] = config.get("save_question_decomposition_record", True)

    client = OpenAI(api_key=CONFIG["api_key"], base_url=CONFIG["base_url"])

    def llm_qwen(
        prompt: str,
        config: Dict[str, Any] = CONFIG,
        temperature: float = 0.20,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        max_tokens = max_tokens or config["llm"]["max_tokens"]
        top_p = top_p if top_p is not None else config["llm"]["top_p"]
        system = system or config["llm"]["system"]

        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return response.choices[0].message.content or ""

    # =============================================================================
    # 3. 本地 JSON 存储
    # =============================================================================

    def empty_store() -> Dict[str, Any]:
        return {
            "meta": {
                "name": "question_decomposition_store",
                "version": "0.1-multi-agent",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
            "records": [],
        }


    def load_store(config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
        path = Path(config["storage_path"])
        if not path.exists():
            return empty_store()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return empty_store()
            data.setdefault("records", [])
            data.setdefault("meta", {})
            return data
        except Exception:
            backup = path.with_suffix(path.suffix + f".broken.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            path.rename(backup)
            print(f"原 JSON 文件解析失败，已备份到：{backup}")
            return empty_store()


    def save_record(record: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> None:
        store = load_store(config)
        store.setdefault("records", [])
        store["records"].append(record)
        store.setdefault("meta", {})
        store["meta"]["updated_at"] = now_iso()
        store["meta"]["version"] = "0.1-multi-agent"

        path = Path(config["storage_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


    # =============================================================================
    # 4. Tetlock 方法库：写进所有 Agent 的通用思维
    # =============================================================================

    TETLOCK_METHOD_LIBRARY = """
    你必须使用以下 Superforecasting 通用思维：

    1. Triage / 问题分诊
       先判断问题类型。不要把所有问题都强行改写为一个二元预测题。
       区分：
       - explicit_binary：用户已经给出清晰事件。
       - continuous：用户问数值。
       - cloud_judgment：用户问“更好/成功/爆发/普及/变强”等多维评价。
       - subjective_value：用户问主观体验或价值判断。
       - mixed：混合问题。

    2. Fermi-izing / 费米化拆解
       把难问题拆成可知部分、未知部分、假设和可估计子问题。
       不要躲在“更好”“成功”“普及”这种模糊词后面。
       要显式列出：
       - knowable parts
       - unknowable parts
       - assumptions
       - measurable proxies
       - unresolved ambiguity

    3. Outside View / 参考类视角
       在进入具体故事之前，先问：
       - 这类问题在历史上通常用哪些指标判断？
       - 类似事件通常由哪些维度构成？
       - 有哪些常见参考类？
       但注意：参考类不能替代原问题，只能帮助设计维度。

    4. Inside View / 具体机制视角
       分析当前对象的独特机制：
       - 技术机制
       - 经济机制
       - 政策机制
       - 社会机制
       - 用户体验机制
       - 约束条件
       但不要让 inside view 变成单一路径叙事。

    5. Dragonfly Eye / 蜻蜓眼多视角
       像蜻蜓眼一样同时看多个视角，把冲突视角综合起来。
       一个云状问题通常需要多个维度共同表达，而不是单一指标。

    6. Avoid Accidental Substitution / 避免意外偷换问题
       这是最高优先级之一。
       不要把难问题替换成容易但不等价的问题。
       典型错误：
       - “经济更好” → “GDP更高”
       - “公司成功” → “股价上涨”
       - “AI爆发” → “某公司发布产品”
       - “普通人过得更好” → “人均GDP增长”
       - “国家变强” → “军费增长”
       - “市场景气” → “指数上涨”
       - “技术普及” → “发布一款产品”

    7. Proxy Risk / 代理指标风险
       如果使用代理指标，必须说明：
       - 它覆盖了原问题多少语义？
       - 它遗漏了哪些维度？
       - 它是否存在 Goodhart 风险？
       - 它是否可能方向冲突：指标改善但真实问题变差？

    8. Signs That Would Change the View / 反向信号
       对每个维度或合约，列出什么信息会说明这个拆解方向错了。
       注意：这里不是预测概率，而是设计未来可更新的观察点。

    9. Precision Without False Precision / 精确但不伪精确
       可以拆成可结算合约，但不能假装云状问题天然就是单一可结算问题。
       多维问题应输出 contract portfolio。
    """


    CASE_LIBRARY_PROMPT = """
    通用案例库。遇到类似问题时，必须参考这些维度，但可以按问题调整。

    A. “某地经济是否更好”
    不能只看 GDP。至少考虑：
    1. 经济总量与产出：实际GDP、名义GDP、GDP增速
    2. 居民收入与就业：可支配收入、失业率、新增就业、招聘岗位
    3. 消费与信心：社零、服务消费、消费者信心
    4. 产业活力：高技术产业、企业注册、融资、核心行业收入
    5. 房地产与资产负债：房价、成交量、居民杠杆、土地财政
    6. 财政与公共服务：财政收入、公共服务支出、地方债务
    7. 外部环境：全国宏观、全球贸易、外资、地缘政治
    8. 主观体感：收入预期、消费信心、幸福感、生活压力

    B. “某技术是否普及”
    不能只看发布产品。至少考虑：
    1. 市场份额/渗透率
    2. 消费者可及性：买得到、用得起、用得上
    3. 量产能力与供应链
    4. 成本和性能是否达到替代门槛
    5. 标准、监管、安全认证
    6. 主流厂商采用情况
    7. 生态配套
    8. 真实使用频率

    C. “某公司是否成功”
    不能只看股价。至少考虑：
    1. 收入增长
    2. 利润/现金流
    3. 用户增长与留存
    4. 市场份额
    5. 产品质量和口碑
    6. 组织稳定性
    7. 融资/资本市场
    8. 战略护城河

    D. “AI 是否爆发”
    不能只看某公司发布模型。至少考虑：
    1. 能力突破
    2. 产品化和用户采用
    3. 收入与商业模式
    4. 算力和成本
    5. 监管和安全
    6. 开源生态
    7. 对工作流的真实替代
    8. 基础设施成熟度

    E. “国家是否变强”
    不能只看军费。至少考虑：
    1. 经济实力
    2. 科技能力
    3. 军事能力
    4. 国际联盟和外交
    5. 社会凝聚力
    6. 人口和教育
    7. 金融与货币影响力
    8. 软实力

    F. “政策是否有效”
    不能只看目标指标。至少考虑：
    1. 目标指标是否改善
    2. 副作用
    3. 成本
    4. 可持续性
    5. 分配影响
    6. 执行质量
    7. 与反事实相比是否更好
    """


    # =============================================================================
    # 5. Schema
    # =============================================================================

    FINAL_SCHEMA = {
        "original_question": "",
        "question_type": "explicit_binary | continuous | cloud_judgment | subjective_value | mixed",
        "is_cloud_question": True,
        "cloud_terms": [],
        "overall_semantic_intent": "",
        "time_interpretation": {
            "current_period": "",
            "target_period": "",
            "comparison": ""
        },
        "core_ambiguities": [],
        "triage": {
            "forecastability_zone": "clocklike | cloudlike | goldilocks | mixed",
            "reason": "",
            "requires_decomposition": True,
            "single_contract_allowed_by_type": False
        },
        "dimension_map": [
            {
                "dimension_id": "",
                "dimension_name": "",
                "meaning": "",
                "candidate_metrics": [],
                "semantic_coverage_weight": 0.0,
                "measurability": 0.0,
                "why_it_matters": "",
                "knowable_parts": [],
                "unknowable_parts": [],
                "assumptions": [],
                "outside_view_reference_classes": [],
                "inside_view_mechanisms": [],
                "update_signals": []
            }
        ],
        "contract_candidates": [
            {
                "contract_id": "",
                "dimension_id": "",
                "dimension_name": "",
                "normalized_question": "",
                "target_type": "binary",
                "deadline": "",
                "resolution_criteria": "",
                "resolution_sources": [],
                "domain": "",
                "forecastability_score": 0.0,
                "semantic_coverage_weight": 0.0,
                "measurability": 0.0,
                "user_intent_preservation_score": 0.0,
                "proxy_metric": "",
                "proxy_risk": "low | medium | high",
                "goodhart_risk": "low | medium | high",
                "direction_conflict_risk": "low | medium | high",
                "lost_dimensions": [],
                "ambiguity_flags": [],
                "clarifying_assumptions": [],
                "outside_view_note": "",
                "inside_view_note": "",
                "update_signals": [],
                "reason": ""
            }
        ],
        "semantic_collapse_audit": {
            "semantic_collapse_risk": "low | medium | high",
            "collapse_reason": "",
            "lost_dimensions_if_single_metric": [],
            "allowed_single_contract": False,
            "recommended_mode": "single_contract | multi_contract_portfolio | ask_user_to_choose | distribution_forecast",
            "required_warning": "",
            "final_guardrails": []
        },
        "adversarial_audit": {
            "verdict": "pass | revise | reject",
            "substitution_errors": [],
            "missing_dimensions": [],
            "overweighted_metrics": [],
            "underweighted_dimensions": [],
            "repair_suggestions": []
        },
        "recommended_user_choice_prompt": "",
        "machine_notes": []
    }


    # =============================================================================
    # 6. Agent 0：问题类型分类器
    # =============================================================================

    def agent_question_type_classifier(question: str, config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 0：Question Type Classifier。

    任务：
    判断用户问题属于哪种预测问题类型。不要生成预测合约，不要输出概率。

    用户问题：
    {question}

    分类标准：
    1. explicit_binary：
       用户已经给出明确事件、时间范围、判定条件。
       例：2027年底前中美是否发生直接军事冲突？

    2. continuous：
       用户问连续数值。
       例：2027年12月29日道琼斯运输指数是多少？

    3. cloud_judgment：
       用户问“更好/成功/爆发/普及/变强/衰退”等多维评价。
       例：北京经济是否更好？2028年固态电池是否普及？

    4. subjective_value：
       用户问主观体验、人群感受或价值判断。
       例：年轻人明年是否会过得更好？

    5. mixed：
       同时包含多个类型。

    输出 JSON：
    {{
      "question_type": "",
      "is_cloud_question": true,
      "cloud_terms": [],
      "triage": {{
        "forecastability_zone": "clocklike | cloudlike | goldilocks | mixed",
        "reason": "",
        "requires_decomposition": true,
        "single_contract_allowed_by_type": false
      }},
      "reason": ""
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["classifier"],
        )


    # =============================================================================
    # 7. Agent 1：原始意图解释器
    # =============================================================================

    def agent_original_intent_interpreter(
        question: str,
        classifier: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 1：Original Intent Interpreter。

    任务：
    解释用户真正想知道什么。不要生成预测合约，不要输出概率。
    你的最高优先级是保护原始语义，防止后续 Agent 偷换问题。

    用户问题：
    {question}

    问题类型分类：
    {json_dumps(classifier)}

    要求：
    1. 用一句话写出用户真正关心的对象。
    2. 解释问题中有哪些模糊词。
    3. 解释如果直接单指标化，最容易发生什么偷换。
    4. 解析时间：
       - 今年/当前期是什么？
       - 明年/目标期是什么？
       - 比较方式是什么？
    5. 不要把问题直接替换成 GDP、股价、销量、市场份额等单一指标。

    输出 JSON：
    {{
      "overall_semantic_intent": "",
      "time_interpretation": {{
        "current_period": "",
        "target_period": "",
        "comparison": ""
      }},
      "core_ambiguities": [],
      "likely_substitution_traps": [],
      "semantic_guardrails": []
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["intent"],
        )


    # =============================================================================
    # 8. Agent 2：云状语义展开器
    # =============================================================================

    def agent_cloud_semantics_expander(
        question: str,
        classifier: Dict[str, Any],
        intent: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    {CASE_LIBRARY_PROMPT}

    你是 Agent 2：Cloud Semantics Expander。

    任务：
    把云状词展开成多个语义维度。不要生成预测合约，不要输出概率。

    用户问题：
    {question}

    分类：
    {json_dumps(classifier)}

    原始意图：
    {json_dumps(intent)}

    要求：
    1. 如果是 cloud_judgment 或 subjective_value，至少展开 5 个维度，最多 10 个。
    2. 每个维度必须说明它覆盖原问题的哪部分含义。
    3. 每个维度必须给出候选指标。
    4. 每个维度必须给 semantic_coverage_weight，总和约为 1。
    5. 每个维度必须给 measurability。
    6. 必须包含难量化但重要的维度，不能只选择容易量化的指标。
    7. 不要输出预测合约。
    8. 不要输出概率。

    输出 JSON：
    {{
      "dimension_map": [
        {{
          "dimension_id": "",
          "dimension_name": "",
          "meaning": "",
          "candidate_metrics": [],
          "semantic_coverage_weight": 0.0,
          "measurability": 0.0,
          "why_it_matters": "",
          "non_quantifiable_warning": ""
        }}
      ],
      "non_quantifiable_but_important_dimensions": [],
      "warning_against_single_metric": ""
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["cloud_expander"],
        )


    # =============================================================================
    # 9. Agent 3：Fermi 拆解器
    # =============================================================================

    def agent_fermi_decomposer(
        question: str,
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 3：Fermi Decomposer。

    任务：
    对每个语义维度做费米化拆解。
    不要预测概率，不要生成最终合约。

    用户问题：
    {question}

    原始意图：
    {json_dumps(intent)}

    语义维度：
    {json_dumps(dimensions)}

    对每个维度回答：
    1. 哪些部分是可知的？
    2. 哪些部分是未知的？
    3. 需要哪些假设？
    4. 可以用哪些近似指标？
    5. 未来什么信号会改变这个维度的判断？
    6. 这个维度是否太宽，需要继续拆？

    输出 JSON：
    {{
      "fermi_dimensions": [
        {{
          "dimension_id": "",
          "knowable_parts": [],
          "unknowable_parts": [],
          "assumptions": [],
          "approximation_metrics": [],
          "update_signals": [],
          "needs_further_split": false,
          "fermi_note": ""
        }}
      ]
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["fermi"],
        )


    # =============================================================================
    # 10. Agent 4：Outside View / 参考类 Agent
    # =============================================================================

    def agent_outside_view_reference_agent(
        question: str,
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        fermi: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 4：Outside View Reference Class Agent。

    任务：
    为每个维度寻找参考类和历史类比。不要输出概率，不要假装已经检索数据。

    用户问题：
    {question}

    原始意图：
    {json_dumps(intent)}

    语义维度：
    {json_dumps(dimensions)}

    Fermi 拆解：
    {json_dumps(fermi)}

    要求：
    1. 对每个维度列出可能的参考类。
    2. 说明参考类为什么相关。
    3. 说明参考类有哪些局限。
    4. 不要把参考类当成原问题本身。
    5. 不要编造具体统计数据。
    6. 输出的是未来检索和建模方向。

    输出 JSON：
    {{
      "outside_view_dimensions": [
        {{
          "dimension_id": "",
          "reference_classes": [
            {{
              "name": "",
              "why_relevant": "",
              "limitations": "",
              "possible_resolution_sources": []
            }}
          ],
          "outside_view_note": ""
        }}
      ]
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["outside_view"],
        )


    # =============================================================================
    # 11. Agent 5：Inside View / 因果机制 Agent
    # =============================================================================

    def agent_inside_view_causal_agent(
        question: str,
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        fermi: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 5：Inside View Causal Agent。

    任务：
    分析每个维度的具体因果机制。不要输出概率。

    用户问题：
    {question}

    原始意图：
    {json_dumps(intent)}

    语义维度：
    {json_dumps(dimensions)}

    Fermi 拆解：
    {json_dumps(fermi)}

    要求：
    1. 对每个维度列出 3-6 个关键机制。
    2. 区分正向机制和反向机制。
    3. 说明机制之间是否互相依赖。
    4. 不要把一个机制当成完整问题。
    5. 记录哪些机制适合变成 contract。

    输出 JSON：
    {{
      "inside_view_dimensions": [
        {{
          "dimension_id": "",
          "positive_mechanisms": [],
          "negative_mechanisms": [],
          "dependencies": [],
          "candidate_contract_angles": [],
          "inside_view_note": ""
        }}
      ]
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["inside_view"],
        )


    # =============================================================================
    # 12. Agent 6：代理指标生成器
    # =============================================================================

    def agent_proxy_metric_generator(
        question: str,
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        fermi: Dict[str, Any],
        outside_view: Dict[str, Any],
        inside_view: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    {CASE_LIBRARY_PROMPT}

    你是 Agent 6：Proxy Metric Generator。

    任务：
    为每个维度提出可观测代理指标。不要生成最终合约，不要输出概率。

    用户问题：
    {question}

    原始意图：
    {json_dumps(intent)}

    语义维度：
    {json_dumps(dimensions)}

    Fermi 拆解：
    {json_dumps(fermi)}

    Outside View：
    {json_dumps(outside_view)}

    Inside View：
    {json_dumps(inside_view)}

    要求：
    1. 每个维度至少给 2 个代理指标。
    2. 对每个代理指标说明：
       - coverage_score：覆盖该维度多少含义
       - measurability：是否容易验证
       - proxy_risk：low/medium/high
       - goodhart_risk：指标被优化但真实问题没改善的风险
       - direction_conflict_risk：指标改善但真实状态变差的风险
       - lost_meanings：遗漏什么
    3. 不要把代理指标当成完整原问题。

    输出 JSON：
    {{
      "proxy_metrics_by_dimension": [
        {{
          "dimension_id": "",
          "dimension_name": "",
          "proxy_metrics": [
            {{
              "proxy_metric": "",
              "coverage_score": 0.0,
              "measurability": 0.0,
              "proxy_risk": "low | medium | high",
              "goodhart_risk": "low | medium | high",
              "direction_conflict_risk": "low | medium | high",
              "lost_meanings": [],
              "resolution_sources": [],
              "note": ""
            }}
          ]
        }}
      ]
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["proxy_generator"],
        )


    # =============================================================================
    # 13. Agent 7：Contract Portfolio Builder
    # =============================================================================

    def agent_contract_portfolio_builder(
        question: str,
        classifier: Dict[str, Any],
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        fermi: Dict[str, Any],
        outside_view: Dict[str, Any],
        inside_view: Dict[str, Any],
        proxy_metrics: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 7：Contract Portfolio Builder。

    任务：
    基于前面 Agent 的结果，为每个重要维度生成可结算的二元预测合约。
    不要输出概率。

    今天日期：{date.today().isoformat()}

    用户问题：
    {question}

    分类：
    {json_dumps(classifier)}

    原始意图：
    {json_dumps(intent)}

    语义维度：
    {json_dumps(dimensions)}

    Fermi 拆解：
    {json_dumps(fermi)}

    Outside View：
    {json_dumps(outside_view)}

    Inside View：
    {json_dumps(inside_view)}

    代理指标：
    {json_dumps(proxy_metrics)}

    要求：
    1. 每个合约只能覆盖一个维度。
    2. 每个合约必须是 binary。
    3. 每个合约必须有 deadline。
    4. 每个合约必须有 resolution_criteria。
    5. 每个合约必须有 resolution_sources。
    6. 每个合约必须声明 proxy_metric。
    7. 每个合约必须声明 proxy_risk。
    8. 每个合约必须声明 lost_dimensions。
    9. 每个合约必须声明 user_intent_preservation_score。
    10. 不得用一个合约冒充完整原始问题。
    11. 对云状问题，至少生成 {config["cloud_question"]["min_contracts_for_cloud"]} 个合约，最多 {config["cloud_question"]["max_contracts"]} 个。
    12. 不要假装已经查询实时数据。

    输出 JSON：
    {{
      "contract_candidates": [
        {{
          "contract_id": "",
          "dimension_id": "",
          "dimension_name": "",
          "normalized_question": "",
          "target_type": "binary",
          "deadline": "YYYY-MM-DD",
          "resolution_criteria": "",
          "resolution_sources": [],
          "domain": "AI | finance | geopolitics | tech_product | science | business | social | other",
          "forecastability_score": 0.0,
          "semantic_coverage_weight": 0.0,
          "measurability": 0.0,
          "user_intent_preservation_score": 0.0,
          "proxy_metric": "",
          "proxy_risk": "low | medium | high",
          "goodhart_risk": "low | medium | high",
          "direction_conflict_risk": "low | medium | high",
          "lost_dimensions": [],
          "ambiguity_flags": [],
          "clarifying_assumptions": [],
          "outside_view_note": "",
          "inside_view_note": "",
          "update_signals": [],
          "reason": ""
        }}
      ]
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["contract_builder"],
        )


    # =============================================================================
    # 14. Agent 8：代理指标风险审计器
    # =============================================================================

    def agent_proxy_risk_auditor(
        question: str,
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        contracts: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 8：Proxy Risk Auditor。

    任务：
    审计每个候选合约是否偷换了原始问题。
    不要生成新合约，不要输出概率。

    用户问题：
    {question}

    原始意图：
    {json_dumps(intent)}

    语义维度：
    {json_dumps(dimensions)}

    候选合约：
    {json_dumps(contracts)}

    审计标准：
    1. 该合约覆盖原问题多少语义？
    2. 是否只是容易量化，但不是真正相关？
    3. 是否存在 Goodhart 风险？
    4. 是否存在方向冲突风险？
    5. 用户是否可能不同意这个合约代表原问题？
    6. lost_dimensions 是否写全？
    7. proxy_risk 是否低估？

    输出 JSON：
    {{
      "proxy_audits": [
        {{
          "contract_id": "",
          "audit_verdict": "accept | accept_with_warning | revise | reject",
          "coverage_score": 0.0,
          "user_intent_preservation_score": 0.0,
          "proxy_risk": "low | medium | high",
          "goodhart_risk": "low | medium | high",
          "direction_conflict_risk": "low | medium | high",
          "missing_lost_dimensions": [],
          "risk_correction": "",
          "reason": ""
        }}
      ]
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["proxy_auditor"],
        )


    # =============================================================================
    # 15. Agent 9：反方重拆器
    # =============================================================================

    def agent_adversarial_redecomposer(
        question: str,
        classifier: Dict[str, Any],
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        contracts: Dict[str, Any],
        proxy_audit: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 9：Adversarial Re-Decomposer。

    任务：
    专门攻击当前拆解方案。不要输出概率。

    用户问题：
    {question}

    分类：
    {json_dumps(classifier)}

    原始意图：
    {json_dumps(intent)}

    维度拆解：
    {json_dumps(dimensions)}

    候选合约：
    {json_dumps(contracts)}

    代理指标审计：
    {json_dumps(proxy_audit)}

    请找出：
    1. 是否把用户问题偷换成了更容易回答的问题？
    2. 是否遗漏关键维度？
    3. 是否过度依赖某个代理指标？
    4. 是否把主观问题伪装成客观问题？
    5. 是否把长期结构问题伪装成短期数据问题？
    6. 是否把整体问题伪装成局部指标？
    7. 哪些合约应该删除、修改或新增？

    输出 JSON：
    {{
      "adversarial_audit": {{
        "verdict": "pass | revise | reject",
        "attack_summary": "",
        "substitution_errors": [],
        "missing_dimensions": [],
        "overweighted_metrics": [],
        "underweighted_dimensions": [],
        "contracts_to_revise": [],
        "contracts_to_remove": [],
        "contracts_to_add": [],
        "repair_suggestions": []
      }}
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["adversarial"],
        )


    # =============================================================================
    # 16. Agent 10：语义坍缩审计器
    # =============================================================================

    def agent_semantic_collapse_auditor(
        question: str,
        classifier: Dict[str, Any],
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        contracts: Dict[str, Any],
        proxy_audit: Dict[str, Any],
        adversarial: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 10：Semantic Collapse Auditor。

    任务：
    判断最终是否存在语义坍缩。不要输出概率。

    语义坍缩定义：
    把一个多维、云状、价值含义丰富的问题，压缩成一个单一、容易量化但不等价的指标。

    典型错误：
    1. “经济更好” → “GDP更高”
    2. “公司成功” → “股价上涨”
    3. “AI爆发” → “某公司发布产品”
    4. “普通人过得更好” → “人均GDP增长”
    5. “国家变强” → “军费增长”
    6. “市场景气” → “指数上涨”
    7. “技术普及” → “发布一款产品”

    用户问题：
    {question}

    分类：
    {json_dumps(classifier)}

    原始意图：
    {json_dumps(intent)}

    维度拆解：
    {json_dumps(dimensions)}

    候选合约：
    {json_dumps(contracts)}

    代理审计：
    {json_dumps(proxy_audit)}

    反方审计：
    {json_dumps(adversarial)}

    输出 JSON：
    {{
      "semantic_collapse_audit": {{
        "semantic_collapse_risk": "low | medium | high",
        "collapse_reason": "",
        "lost_dimensions_if_single_metric": [],
        "allowed_single_contract": true,
        "recommended_mode": "single_contract | multi_contract_portfolio | ask_user_to_choose | distribution_forecast",
        "required_warning": "",
        "final_guardrails": []
      }}
    }}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["collapse_auditor"],
        )


    # =============================================================================
    # 17. Agent 11：最终综合器
    # =============================================================================

    def agent_final_synthesizer(
        question: str,
        classifier: Dict[str, Any],
        intent: Dict[str, Any],
        dimensions: Dict[str, Any],
        fermi: Dict[str, Any],
        outside_view: Dict[str, Any],
        inside_view: Dict[str, Any],
        proxy_metrics: Dict[str, Any],
        contracts: Dict[str, Any],
        proxy_audit: Dict[str, Any],
        adversarial: Dict[str, Any],
        collapse_audit: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        prompt = f"""
    {TETLOCK_METHOD_LIBRARY}

    你是 Agent 11：Final Synthesizer。

    任务：
    把所有 Agent 的结果合成最终 Question Decomposition Record。
    不要输出概率，不要做预测。

    用户问题：
    {question}

    Agent 0 分类：
    {json_dumps(classifier)}

    Agent 1 原始意图：
    {json_dumps(intent)}

    Agent 2 语义展开：
    {json_dumps(dimensions)}

    Agent 3 Fermi 拆解：
    {json_dumps(fermi)}

    Agent 4 Outside View：
    {json_dumps(outside_view)}

    Agent 5 Inside View：
    {json_dumps(inside_view)}

    Agent 6 Proxy Metrics：
    {json_dumps(proxy_metrics)}

    Agent 7 Contracts：
    {json_dumps(contracts)}

    Agent 8 Proxy Audit：
    {json_dumps(proxy_audit)}

    Agent 9 Adversarial Audit：
    {json_dumps(adversarial)}

    Agent 10 Collapse Audit：
    {json_dumps(collapse_audit)}

    合成要求：
    1. 输出最终完整 JSON。
    2. dimension_map 要融合 Fermi、outside view、inside view。
    3. contract_candidates 要融合 proxy audit 的修正。
    4. 如果 proxy_audit 认为风险更高，以 proxy_audit 为准。
    5. 如果 adversarial_audit 要求补充维度，要在 machine_notes 里记录。
    6. 如果 semantic_collapse_risk 为 high，allowed_single_contract 必须是 false。
    7. 云状问题默认 recommended_mode 为 multi_contract_portfolio。
    8. 不要输出概率。

    输出 JSON schema：
    {json_dumps(FINAL_SCHEMA)}
    """
        return llm_json(
            prompt,
            config=config,
            temperature=config["temperature"]["synthesizer"],
        )


    # =============================================================================
    # 18. 结果规范化与硬规则
    # =============================================================================

    def merge_by_dimension_id(base_dims: List[Dict[str, Any]], extra_list: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        idx = {d.get("dimension_id"): d for d in base_dims if d.get("dimension_id")}

        for extra in extra_list or []:
            did = extra.get("dimension_id")
            if not did:
                continue
            if did not in idx:
                idx[did] = {"dimension_id": did, "dimension_name": did}
            idx[did][key] = extra

        return list(idx.values())



    def get_nested_dict(obj: Dict[str, Any], *keys: str) -> Dict[str, Any]:
        """安全读取嵌套 dict；读不到时返回空 dict。"""
        cur: Any = obj
        for key in keys:
            if not isinstance(cur, dict):
                return {}
            cur = cur.get(key, {})
        return cur if isinstance(cur, dict) else {}


    def extract_collapse_guardrails(collapse_audit: Dict[str, Any]) -> List[Any]:
        """从 Agent 10 输出中取 final_guardrails，兼容包裹和非包裹两种结构。"""
        if not isinstance(collapse_audit, dict):
            return []

        audit = collapse_audit.get("semantic_collapse_audit", collapse_audit)
        if not isinstance(audit, dict):
            return []

        guardrails = audit.get("final_guardrails", [])
        return guardrails if isinstance(guardrails, list) else []


    def contract_text_blob(contract: Dict[str, Any]) -> str:
        parts = [
            contract.get("dimension_name", ""),
            contract.get("normalized_question", ""),
            contract.get("resolution_criteria", ""),
            contract.get("proxy_metric", ""),
            contract.get("reason", ""),
        ]
        return "\n".join(str(x) for x in parts if x is not None)


    def is_income_growth_contract(contract: Dict[str, Any]) -> bool:
        """
        收入类合约硬规则：不能比较“增速是否高于基准年”，应比较“实际水平是否高于基准年”。
        这里只处理明显的收入/购买力 + 增速 合约，避免误伤其他维度。
        """
        blob = contract_text_blob(contract)
        income_terms = ["收入", "可支配收入", "购买力", "工资", "薪资", "income", "wage", "salary"]
        return any(t in blob for t in income_terms) and "增速" in blob


    def compute_proxy_risk_factor(proxy_risk: Any) -> float:
        """
        将 proxy_risk 转换为组合权重惩罚因子。
        该因子用于后续 portfolio raw_weight，不改变合约本身的语义覆盖说明。
        """
        risk = str(proxy_risk or "unknown").lower().strip()
        return {
            "low": 1.00,
            "medium": 0.80,
            "high": 0.55,
            "unknown": 0.65,
        }.get(risk, 0.65)


    def compute_lost_dimension_factor(contract: Dict[str, Any]) -> float:
        """
        根据 lost_dimensions 数量自动衰减组合权重。

        设计原则：
        - 丢失维度越多，合约在 portfolio 中权重越低；
        - 不直接归零，避免有用但不完整的代理指标被完全丢弃；
        - 作为 raw_portfolio_weight 的一部分，避免先乘后归一化被完全抵消的问题。
        """
        lost_dimensions = contract.get("lost_dimensions", [])
        if not isinstance(lost_dimensions, list):
            lost_dimensions = []

        lost_dimension_count = len(lost_dimensions)
        return max(0.40, 1.0 - 0.12 * lost_dimension_count)


    def compute_contract_raw_portfolio_weight(contract: Dict[str, Any]) -> float:
        """
        后续 portfolio 权重计算的通用 raw_weight。

        raw_weight = semantic_coverage_weight * measurability * intent_score * proxy_risk_factor * lost_dimension_factor

        注意：
        - semantic_coverage_weight 表示语义覆盖；
        - measurability 表示可结算性；
        - intent_score 表示是否保留用户原意；
        - proxy_risk_factor 惩罚高代理风险；
        - lost_dimension_factor 惩罚遗漏维度过多的代理合约。
        """
        semantic_coverage_weight = clamp(
            contract.get("semantic_coverage_weight", 0.0),
            0.0,
            1.0,
        )
        measurability = clamp(
            contract.get("measurability", CONFIG["normalization"]["default_measurability"]),
            0.0,
            1.0,
        )
        intent_score = clamp(
            contract.get("user_intent_preservation_score", CONFIG["normalization"]["default_intent_preservation"]),
            0.0,
            1.0,
        )
        proxy_risk_factor = compute_proxy_risk_factor(contract.get("proxy_risk"))
        lost_dimension_factor = compute_lost_dimension_factor(contract)

        raw_weight = (
            semantic_coverage_weight
            * measurability
            * intent_score
            * proxy_risk_factor
            * lost_dimension_factor
        )
        return max(0.0, float(raw_weight))


    def normalize_contracts_by_raw_portfolio_weight(
        contracts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        使用 raw_portfolio_weight 归一化最终 semantic_coverage_weight。
        同时保留 original_semantic_coverage_weight，便于调试与审计。
        """
        if not contracts:
            return contracts

        raw_values = []
        for c in contracts:
            if "original_semantic_coverage_weight" not in c:
                c["original_semantic_coverage_weight"] = c.get("semantic_coverage_weight", 0.0)

            c["proxy_risk_factor"] = compute_proxy_risk_factor(c.get("proxy_risk"))
            c["lost_dimension_factor"] = compute_lost_dimension_factor(c)
            c["raw_portfolio_weight"] = compute_contract_raw_portfolio_weight(c)
            raw_values.append(c["raw_portfolio_weight"])

        total = sum(raw_values)
        if total <= 0:
            return normalize_weight_list(contracts, "semantic_coverage_weight")

        for c in contracts:
            c["semantic_coverage_weight"] = c["raw_portfolio_weight"] / total

        return contracts



    def apply_final_hard_rules(
        final: Dict[str, Any],
        classifier: Dict[str, Any],
        collapse_audit: Dict[str, Any],
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        """
        Final Synthesizer 后处理硬规则。

        - Final 分类结果以 Agent 0 为准；
        - 保留 semantic collapse guardrails；
        - 不把 adversarial_audit.verdict 粗暴改成 pass，只写 repair_status；
        - 收入类合约只检测/提示，不做代码层自动改写。
        """
        final = dict(final or {})
        final.setdefault("machine_notes", [])

        # 1. Final 强制继承 Agent 0 分类结果。
        for key in ("question_type", "is_cloud_question", "cloud_terms"):
            if key in classifier:
                final[key] = classifier[key]

        # 2. 保留 Agent 10 collapse guardrails。
        audit = final.setdefault("semantic_collapse_audit", {})
        guardrails = (
            collapse_audit.get("semantic_collapse_audit", {}).get("final_guardrails")
            or collapse_audit.get("final_guardrails")
            or extract_collapse_guardrails(collapse_audit)
        )
        if isinstance(guardrails, list):
            audit["final_guardrails"] = guardrails

        # 3. 收入类合约不做自动改写，只提示。
        income_growth_contracts = [
            str(c.get("contract_id", ""))
            for c in final.get("contract_candidates", []) or []
            if is_income_growth_contract(c)
        ]
        if income_growth_contracts:
            note = (
                "提示：检测到收入类合约仍使用‘增速’口径。"
                "代码不自动改写，请在 Agent 7 / Final Synthesizer 中判断："
                "收入维度通常应优先比较实际收入水平、收入中位数、低收入组收入或购买力水平；"
                "只有当用户明确关心增长速度时，才保留增速口径。"
                f" 涉及合约：{', '.join(income_growth_contracts)}"
            )
            if note not in final["machine_notes"]:
                final["machine_notes"].append(note)

        # 4. adversarial verdict 不再粗暴改 pass，只记录修复状态。
        adv = final.setdefault("adversarial_audit", {})
        if isinstance(adv, dict):
            if adv.get("verdict") == "revise":
                adv["repair_status"] = "requires_review" if income_growth_contracts else adv.get("repair_status", "partially_repaired")
                note = (
                    f"Adversarial audit verdict 保持为 {adv.get('verdict')}；"
                    f"repair_status={adv.get('repair_status')}，不再自动改成 pass。"
                )
                if note not in final["machine_notes"]:
                    final["machine_notes"].append(note)
            else:
                adv.setdefault("repair_status", "not_required")

        return final


    def normalize_final_record(record: Dict[str, Any], question: str, config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
        cq = config["cloud_question"]
        norm = config["normalization"]

        record.setdefault("original_question", question)
        record.setdefault("question_type", "mixed")
        record.setdefault("is_cloud_question", has_cloud_term(question, config))
        record.setdefault("cloud_terms", [])
        record.setdefault("overall_semantic_intent", question)
        record.setdefault("time_interpretation", {})
        record.setdefault("core_ambiguities", [])
        record.setdefault("triage", {})
        record.setdefault("dimension_map", [])
        record.setdefault("contract_candidates", [])
        record.setdefault("semantic_collapse_audit", {})
        record.setdefault("adversarial_audit", {})
        record.setdefault("recommended_user_choice_prompt", "")
        record.setdefault("machine_notes", [])

        # 兼容 is_cloud_question 字符串
        if isinstance(record["is_cloud_question"], str):
            record["is_cloud_question"] = record["is_cloud_question"].lower() == "true"

        if has_cloud_term(question, config):
            record["is_cloud_question"] = True
            if record.get("question_type") == "explicit_binary":
                record["question_type"] = "cloud_judgment"

        # 维度清洗
        dims = []
        for i, d in enumerate(record.get("dimension_map") or []):
            d = dict(d or {})
            d.setdefault("dimension_id", f"dimension_{i+1}")
            d.setdefault("dimension_name", d["dimension_id"])
            d.setdefault("meaning", "")
            d.setdefault("candidate_metrics", [])
            d["semantic_coverage_weight"] = clamp(d.get("semantic_coverage_weight", 0.0), 0.0, 1.0)
            d["measurability"] = clamp(d.get("measurability", norm["default_measurability"]), 0.0, 1.0)
            d.setdefault("why_it_matters", "")
            d.setdefault("knowable_parts", [])
            d.setdefault("unknowable_parts", [])
            d.setdefault("assumptions", [])
            d.setdefault("outside_view_reference_classes", [])
            d.setdefault("inside_view_mechanisms", [])
            d.setdefault("update_signals", [])
            dims.append(d)

        if record["is_cloud_question"] and len(dims) < cq["min_dimensions_for_cloud"]:
            record["machine_notes"].append(
                f"WARNING: cloud question has only {len(dims)} dimensions; expected at least {cq['min_dimensions_for_cloud']}."
            )

        dims = dims[:cq["max_dimensions"]]
        dims = normalize_weight_list(dims, "semantic_coverage_weight") if dims else []
        record["dimension_map"] = dims

        dim_name = {d["dimension_id"]: d.get("dimension_name", d["dimension_id"]) for d in dims}
        dim_weight = {d["dimension_id"]: safe_float(d.get("semantic_coverage_weight"), 0.0) for d in dims}
        dim_meas = {d["dimension_id"]: safe_float(d.get("measurability"), norm["default_measurability"]) for d in dims}

        # 合约清洗
        contracts = []
        for i, c in enumerate(record.get("contract_candidates") or []):
            c = dict(c or {})
            c.setdefault("contract_id", f"contract_{i+1}")
            c.setdefault("dimension_id", f"dimension_{i+1}")
            c.setdefault("dimension_name", dim_name.get(c["dimension_id"], c["dimension_id"]))
            c.setdefault("normalized_question", question)
            c["target_type"] = "binary"
            c.setdefault("deadline", "")
            c.setdefault("resolution_criteria", "")
            c.setdefault("resolution_sources", [])
            c.setdefault("domain", "other")

            c["forecastability_score"] = clamp(
                c.get("forecastability_score", norm["default_forecastability"]),
                0.0,
                1.0
            )

            default_cov = dim_weight.get(c["dimension_id"], 0.0)
            if default_cov <= 0:
                default_cov = 1.0 / max(1, len(record.get("contract_candidates") or []))
            c["semantic_coverage_weight"] = clamp(
                c.get("semantic_coverage_weight", default_cov),
                0.0,
                1.0
            )

            c["measurability"] = clamp(
                c.get("measurability", dim_meas.get(c["dimension_id"], norm["default_measurability"])),
                0.0,
                1.0
            )

            c["user_intent_preservation_score"] = clamp(
                c.get("user_intent_preservation_score", norm["default_intent_preservation"]),
                0.0,
                1.0
            )

            c.setdefault("proxy_metric", "")
            c.setdefault("proxy_risk", norm["default_proxy_risk"])
            c["proxy_risk"] = str(c["proxy_risk"]).lower()
            if c["proxy_risk"] not in {"low", "medium", "high"}:
                c["proxy_risk"] = "unknown"

            c.setdefault("goodhart_risk", "unknown")
            c.setdefault("direction_conflict_risk", "unknown")
            c.setdefault("lost_dimensions", [])
            c.setdefault("ambiguity_flags", [])
            c.setdefault("clarifying_assumptions", [])
            c.setdefault("outside_view_note", "")
            c.setdefault("inside_view_note", "")
            c.setdefault("update_signals", [])
            c.setdefault("reason", "")

            # 记录原始语义覆盖权重，并计算后续 portfolio raw_weight。
            # raw_weight = semantic_coverage_weight * measurability * intent_score * proxy_risk_factor * lost_dimension_factor
            c["original_semantic_coverage_weight"] = c.get("semantic_coverage_weight", 0.0)
            c["proxy_risk_factor"] = compute_proxy_risk_factor(c.get("proxy_risk"))
            c["lost_dimension_factor"] = compute_lost_dimension_factor(c)
            c["raw_portfolio_weight"] = compute_contract_raw_portfolio_weight(c)

            if c["original_semantic_coverage_weight"] >= 0.15 and len(c.get("lost_dimensions", [])) >= 3:
                c.setdefault("ambiguity_flags", []).append(
                    "硬规则提示：该高权重合约 lost_dimensions >= 3，已通过 lost_dimension_factor 进入 raw_portfolio_weight 进行组合权重惩罚。"
                )
                record["machine_notes"].append(
                    f"{c.get('contract_id')} lost_dimensions 较多，lost_dimension_factor={c['lost_dimension_factor']:.3f}，已进入 raw_portfolio_weight。"
                )

            contracts.append(c)

        contracts = contracts[:cq["max_contracts"]]
        contracts = normalize_contracts_by_raw_portfolio_weight(contracts) if contracts else []
        record["contract_candidates"] = contracts

        if record["is_cloud_question"] and len(contracts) < cq["min_contracts_for_cloud"]:
            record["machine_notes"].append(
                f"WARNING: cloud question has only {len(contracts)} contracts; expected at least {cq['min_contracts_for_cloud']}."
            )

        # 审计字段
        audit = record.get("semantic_collapse_audit") or {}
        audit.setdefault("semantic_collapse_risk", "unknown")
        audit["semantic_collapse_risk"] = str(audit["semantic_collapse_risk"]).lower()
        if audit["semantic_collapse_risk"] not in {"low", "medium", "high"}:
            audit["semantic_collapse_risk"] = "unknown"

        audit.setdefault("collapse_reason", "")
        audit.setdefault("lost_dimensions_if_single_metric", [])
        audit.setdefault("allowed_single_contract", True)
        audit.setdefault("recommended_mode", "single_contract")
        audit.setdefault("required_warning", "")
        audit.setdefault("final_guardrails", [])

        # 硬规则：云状问题默认不允许 single_contract
        if record["is_cloud_question"] and cq["force_multi_contract_when_cloud"]:
            audit["allowed_single_contract"] = False
            if len(contracts) >= 2:
                audit["recommended_mode"] = "multi_contract_portfolio"

        # 硬规则：高语义坍缩风险不允许 single_contract
        if audit["semantic_collapse_risk"] == "high" and cq["high_risk_blocks_single_contract"]:
            audit["allowed_single_contract"] = False
            if len(contracts) >= 2:
                audit["recommended_mode"] = "multi_contract_portfolio"

        # 硬规则：最低原意保留分
        if contracts:
            min_intent = min(c["user_intent_preservation_score"] for c in contracts)
            if min_intent < cq["min_intent_preservation_for_single_contract"] and len(contracts) >= 2:
                audit["allowed_single_contract"] = False
                audit["recommended_mode"] = "multi_contract_portfolio"

        record["semantic_collapse_audit"] = audit

        # 推荐问题
        if not record.get("recommended_user_choice_prompt"):
            if record["is_cloud_question"]:
                record["recommended_user_choice_prompt"] = (
                    "你更关心这个问题的哪个维度？如果不指定，我会使用多维 contract portfolio 进行综合判断。"
                )
            else:
                record["recommended_user_choice_prompt"] = ""

        return record


    def validate_final_record(record: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> List[str]:
        errors = []
        cq = config["cloud_question"]

        if record.get("is_cloud_question"):
            if len(record.get("dimension_map", [])) < cq["min_dimensions_for_cloud"]:
                errors.append("云状问题维度数量不足")
            if len(record.get("contract_candidates", [])) < cq["min_contracts_for_cloud"]:
                errors.append("云状问题 contract 数量不足")
            if record.get("semantic_collapse_audit", {}).get("allowed_single_contract") is True:
                errors.append("云状问题不应允许 single_contract")

        for c in record.get("contract_candidates", []):
            if not c.get("normalized_question"):
                errors.append(f"{c.get('contract_id')} 缺少 normalized_question")
            if not c.get("resolution_criteria"):
                errors.append(f"{c.get('contract_id')} 缺少 resolution_criteria")
            if not c.get("proxy_metric"):
                errors.append(f"{c.get('contract_id')} 缺少 proxy_metric")
            if not c.get("lost_dimensions"):
                errors.append(f"{c.get('contract_id')} 缺少 lost_dimensions")
            if c.get("proxy_risk") in {"high", "unknown"} and c.get("user_intent_preservation_score", 0) > 0.9:
                errors.append(f"{c.get('contract_id')} 代理风险高但原意保留分异常过高")
            if is_income_growth_contract(c):
                errors.append(
                    f"{c.get('contract_id')} 收入类合约使用了‘增速’口径；请确认这是否真能代表原问题。"
                    "通常应优先比较实际收入水平、中位数收入、低收入组收入或购买力水平；"
                    "只有用户明确关心增长速度时才保留增速口径。"
                )

        return errors


    # =============================================================================
    # 19. 主流程：多 Agent 编排
    # =============================================================================

    def run_question_decomposition_agents(
        question: str,
        config: Dict[str, Any] = CONFIG,
    ) -> Dict[str, Any]:
        runtime = config["runtime"]

        def step(msg: str):
            if runtime.get("print_steps", True):
                print(msg)

        def show(name: str, obj: Dict[str, Any]):
            if runtime.get("print_agent_outputs", True):
                print(f"\n===== {name} =====")
                print(json.dumps(obj, ensure_ascii=False, indent=2))

        record_id = short_id()

        step("[0/11] Agent 0：问题类型分类...")
        classifier = agent_question_type_classifier(question, config=config)
        show("Agent 0 分类结果", classifier)

        step("[1/11] Agent 1：解释原始意图...")
        intent = agent_original_intent_interpreter(question, classifier, config=config)
        show("Agent 1 原始意图", intent)

        step("[2/11] Agent 2：云状语义展开...")
        dimensions = agent_cloud_semantics_expander(question, classifier, intent, config=config)
        show("Agent 2 语义维度", dimensions)

        step("[3/11] Agent 3：Fermi 化拆解...")
        fermi = agent_fermi_decomposer(question, intent, dimensions, config=config)
        show("Agent 3 Fermi 拆解", fermi)

        step("[4/11] Agent 4：Outside View 参考类...")
        outside_view = agent_outside_view_reference_agent(question, intent, dimensions, fermi, config=config)
        show("Agent 4 Outside View", outside_view)

        step("[5/11] Agent 5：Inside View 因果机制...")
        inside_view = agent_inside_view_causal_agent(question, intent, dimensions, fermi, config=config)
        show("Agent 5 Inside View", inside_view)

        step("[6/11] Agent 6：生成代理指标...")
        proxy_metrics = agent_proxy_metric_generator(
            question,
            intent,
            dimensions,
            fermi,
            outside_view,
            inside_view,
            config=config,
        )
        show("Agent 6 Proxy Metrics", proxy_metrics)

        step("[7/11] Agent 7：生成 Contract Portfolio...")
        contracts = agent_contract_portfolio_builder(
            question,
            classifier,
            intent,
            dimensions,
            fermi,
            outside_view,
            inside_view,
            proxy_metrics,
            config=config,
        )
        show("Agent 7 Contracts", contracts)

        step("[8/11] Agent 8：代理指标风险审计...")
        proxy_audit = agent_proxy_risk_auditor(
            question,
            intent,
            dimensions,
            contracts,
            config=config,
        )
        show("Agent 8 Proxy Audit", proxy_audit)

        step("[9/11] Agent 9：反方重拆审计...")
        adversarial = agent_adversarial_redecomposer(
            question,
            classifier,
            intent,
            dimensions,
            contracts,
            proxy_audit,
            config=config,
        )
        show("Agent 9 Adversarial Audit", adversarial)

        step("[10/11] Agent 10：语义坍缩审计...")
        collapse_audit = agent_semantic_collapse_auditor(
            question,
            classifier,
            intent,
            dimensions,
            contracts,
            proxy_audit,
            adversarial,
            config=config,
        )
        show("Agent 10 Collapse Audit", collapse_audit)

        step("[11/11] Agent 11：最终综合...")
        final = agent_final_synthesizer(
            question,
            classifier,
            intent,
            dimensions,
            fermi,
            outside_view,
            inside_view,
            proxy_metrics,
            contracts,
            proxy_audit,
            adversarial,
            collapse_audit,
            config=config,
        )

        # Final Synthesizer 后处理硬规则：
        # 1) 继承 Agent 0 分类；2) 修正已落地的 adversarial verdict；
        # 3) 保留 collapse guardrails；4) 收入合约改为实际水平比较。
        final = apply_final_hard_rules(final, classifier, collapse_audit, config=config)
        final = normalize_final_record(final, question, config=config)
        # normalize_final_record 内部可能基于旧 cloud_terms 做兜底判断；这里再次应用硬规则，保证最终输出以 Agent 0 为准。
        final = apply_final_hard_rules(final, classifier, collapse_audit, config=config)
        validation_errors = validate_final_record(final, config=config)

        final_record = {
            "id": record_id,
            "created_at": now_iso(),
            "module": "cloud_to_contract_decomposition",
            "version": "0.1-multi-agent",
            "original_question": question,
            "agent_outputs": {
                "classifier": classifier,
                "intent": intent,
                "dimensions": dimensions,
                "fermi": fermi,
                "outside_view": outside_view,
                "inside_view": inside_view,
                "proxy_metrics": proxy_metrics,
                "contracts": contracts,
                "proxy_audit": proxy_audit,
                "adversarial": adversarial,
                "collapse_audit": collapse_audit,
            },
            "final": final,
            "validation_errors": validation_errors,
        }

        if validation_errors:
            print("\n===== VALIDATION WARNINGS =====")
            for e in validation_errors:
                print("-", e)

        print("\n===== FINAL DECOMPOSITION =====")
        print(json.dumps(final, ensure_ascii=False, indent=2))

        if runtime.get("save_record", True):
            save_record(final_record, config=config)

        return final_record


    # =============================================================================
    # 20. 便捷函数
    # =============================================================================

    def print_contract_portfolio(record: Dict[str, Any]) -> None:
        final = record["final"]
        print("\n# Contract Portfolio")
        print(f"原始问题：{final.get('original_question')}")
        print(f"问题类型：{final.get('question_type')}")
        print(f"是否云状问题：{final.get('is_cloud_question')}")
        print(f"推荐模式：{final.get('semantic_collapse_audit', {}).get('recommended_mode')}")
        print(f"语义坍缩风险：{final.get('semantic_collapse_audit', {}).get('semantic_collapse_risk')}")
        print("\n## 原始语义")
        print(final.get("overall_semantic_intent", ""))

        print("\n## 维度")
        for d in final.get("dimension_map", []):
            print(
                f"- {d.get('dimension_name')} "
                f"| weight={d.get('semantic_coverage_weight'):.3f} "
                f"| meas={d.get('measurability'):.2f}"
            )
            print(f"  - {d.get('meaning')}")

        print("\n## 合约")
        for c in final.get("contract_candidates", []):
            print(
                f"- {c.get('contract_id')} / {c.get('dimension_name')} "
                f"| weight={c.get('semantic_coverage_weight'):.3f} "
                f"| proxy_risk={c.get('proxy_risk')} "
                f"| intent={c.get('user_intent_preservation_score'):.2f}"
            )
            print(f"  - {c.get('normalized_question')}")
            print(f"  - proxy={c.get('proxy_metric')}")
            print(f"  - lost={', '.join(map(str, c.get('lost_dimensions', [])[:5]))}")


    def export_final_json(record: Dict[str, Any], out_path: str) -> str:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record["final"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已导出：{path}")
        return str(path)

    return run_question_decomposition_agents(question, CONFIG)

