
from __future__ import annotations

import json
import math

import re
import uuid
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Tuple, Optional

from app.config import CONFIG
from app.model import llm_qwen
# =============================================================================
# 2. 基础工具函数
# =============================================================================

def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def short_id() -> str:
    return uuid.uuid4().hex[:12]


def clamp(x: Any, lo: float, hi: float) -> float:
    try:
        x = float(x)
    except Exception:
        x = 0.0
    return max(lo, min(hi, x))


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def logit(p: float) -> float:
    p = clamp(p, 1e-5, 1 - 1e-5)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def probability_to_percent(p: float) -> str:
    return f"{float(p) * 100:.1f}%"


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def current_date_context_text() -> str:
    """全流程 LLM 提示词统一注入当前日期与相对时间解释规则。"""
    today = date.today()
    current_year = today.year
    return f"""
当前日期上下文：
- 今天日期：{today.isoformat()}
- 当前年份：{current_year}

相对时间解释硬规则：
1. 如果用户说“未来三年 / 接下来三年 / 今后三年”等预测语境，默认从今天日期向后推三年。
2. 以当前年份作为 current_period，以当前年份 + 3 作为 target_period。
3. 不允许自行猜测 2024、2025 或其他历史年份作为“当前”。
4. 如果用户给出明确年份，以用户明确年份为准；否则必须使用今天日期推导。
5. 所有后续合约、deadline、resolution_criteria 必须与上述时间解释一致。
""".strip()


def strip_think_blocks(text: str) -> str:
    return re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    text = strip_think_blocks(text).strip()

    fence = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence:
        text = fence.group(1).strip()

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        return {"value": obj}
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
            return {"value": obj}
        except Exception as e:
            raise ValueError(f"JSON 解析失败：{e}\n\n原始输出前2000字符：\n{text[:2000]}")

    raise ValueError(f"没有找到 JSON 对象。\n\n原始输出前2000字符：\n{text[:2000]}")


def llm_json(
    prompt: str,
    config: Dict[str, Any] = CONFIG,
    temperature: float = 0.20,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    strict_prompt = current_date_context_text() + "\n\n" + prompt.strip() + """

硬性要求：
1. 只输出一个合法 JSON 对象。
2. 不要输出 Markdown。
3. 不要输出解释。
4. 不要输出代码块。
5. 所有字符串必须使用双引号。
"""
    raw = llm_qwen(
        strict_prompt,
        config=config,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    try:
        return extract_json_object(raw)
    except Exception:
        repair_prompt = f"""
下面是一段模型输出。请把它修复成一个合法 JSON 对象。

要求：
1. 只输出 JSON。
2. 不要解释。
3. 不要 Markdown。
4. 不要代码块。

原始输出：
{raw}
"""
        repaired = llm_qwen(
            repair_prompt,
            config=config,
            temperature=config["temperature"]["json_repair"],
            max_tokens=max_tokens,
        )
        return extract_json_object(repaired)


def normalize_weight_list(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    vals = []
    for item in items:
        v = safe_float(item.get(key), 0.0)
        if v < 0:
            v = 0.0
        vals.append(v)

    s = sum(vals)
    if s <= 0:
        n = max(1, len(items))
        for item in items:
            item[key] = 1.0 / n
        return items

    for item, v in zip(items, vals):
        item[key] = v / s
    return items


def has_cloud_term(question: str, config: Dict[str, Any] = CONFIG) -> bool:
    q = str(question)
    for term in config["cloud_question"]["cloud_terms"]:
        if term in q:
            return True
    return False


def risk_factor(proxy_risk: str, config: Dict[str, Any] = CONFIG) -> float:
    m = config["portfolio"]["proxy_risk_weight_factor"]
    key = str(proxy_risk or "unknown").lower()
    return float(m.get(key, m["unknown"]))


def get_record_probability(record: Dict[str, Any]) -> float:
    if "portfolio_probability_engine" in record:
        return float(record["portfolio_probability_engine"]["calibrated_probability"])
    return float(record.get("probability_engine", {}).get("calibrated_probability", 0.5))
# =============================================================================
# 3. JSON 本地存储
# =============================================================================

def empty_store() -> Dict[str, Any]:
    return {
        "meta": {
            "name": "superforecast_mvp_json_store",
            "version": "0.2-cloud-expansion",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        "forecasts": [],
    }


def load_store(config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    path = Path(config["storage_path"])
    if not path.exists():
        return empty_store()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return empty_store()
        if "forecasts" not in data:
            data["forecasts"] = []
        if "meta" not in data:
            data["meta"] = {}
        return data
    except Exception:
        backup = path.with_suffix(path.suffix + f".broken.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        path.rename(backup)
        print(f"原 JSON 文件解析失败，已备份到：{backup}")
        return empty_store()


def save_store(store: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> None:
    path = Path(config["storage_path"])
    path.parent.mkdir(parents=True, exist_ok=True)

    store.setdefault("meta", {})
    store["meta"]["updated_at"] = now_iso()
    store["meta"]["version"] = "0.2-cloud-expansion"

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def save_forecast_record(record: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> None:
    store = load_store(config)
    store.setdefault("forecasts", [])
    store["forecasts"].append(record)
    save_store(store, config)


def find_forecast(forecast_id: str, config: Dict[str, Any] = CONFIG) -> Optional[Dict[str, Any]]:
    store = load_store(config)
    for item in store.get("forecasts", []):
        if item.get("id") == forecast_id:
            return item
    return None


def update_forecast_record(forecast_id: str, patch: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    store = load_store(config)
    for idx, item in enumerate(store.get("forecasts", [])):
        if item.get("id") == forecast_id:
            item.update(patch)
            item["updated_at"] = now_iso()
            store["forecasts"][idx] = item
            save_store(store, config)
            return item
    raise ValueError(f"forecast_id 不存在：{forecast_id}")


def local_domain_brier_stats(domain: str, config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    store = load_store(config)
    scores = []
    for item in store.get("forecasts", []):
        item_domain = item.get("contract", {}).get("domain")
        if not item_domain:
            item_domain = item.get("portfolio_meta", {}).get("dominant_domain", "other")

        if (
            item.get("status") == "resolved"
            and item_domain == domain
            and item.get("brier_score") is not None
        ):
            scores.append(float(item["brier_score"]))

    if not scores:
        return {
            "n": 0,
            "avg_brier": None,
        }

    return {
        "n": len(scores),
        "avg_brier": mean(scores),
    }
