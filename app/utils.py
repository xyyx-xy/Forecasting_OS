
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

from config import CONFIG
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


import ast
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


def strip_think_blocks(text: str) -> str:
    """
    去掉 Qwen / DeepSeek 等模型常见的 <think>...</think>。
    对未闭合 think 标签，只移除标签本身，不粗暴删除后文。
    """
    if text is None:
        return ""

    text = str(text)

    text = re.sub(
        r"<think\b[^>]*>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 处理残留标签
    text = re.sub(r"</?think\b[^>]*>", "", text, flags=re.IGNORECASE)

    return text.strip()


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()

    fence = re.search(
        r"```(?:json|JSON)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence:
        return fence.group(1).strip()

    return text


def _try_json_loads(s: str) -> Any:
    return json.loads(s)


def _try_ast_literal_eval(s: str) -> Any:
    """
    兼容 Python dict 风格：
    {'a': 1, 'b': True, 'c': None}
    """
    obj = ast.literal_eval(s)
    return obj


def _to_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        obj.setdefault("__json_parse_ok__", True)
        return obj
    return {
        "value": obj,
        "__json_parse_ok__": True,
    }


def _remove_json_comments(s: str) -> str:
    """
    移除 // 和 /* */ 注释。
    注意：这是宽松修复，不适合保留字符串中的 // URL。
    所以只在严格解析失败后使用。
    """
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = re.sub(r"(?m)^\s*//.*$", "", s)
    return s


def _normalize_quotes(s: str) -> str:
    """
    标准化常见智能引号。
    """
    return (
        s.replace("\ufeff", "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("＂", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def _replace_python_literals(s: str) -> str:
    """
    Python literal → JSON literal.
    """
    s = re.sub(r"\bNone\b", "null", s)
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    return s


def _remove_trailing_commas(s: str) -> str:
    """
    删除 JSON 尾逗号：
    {"a": 1,}
    [1,2,]
    """
    return re.sub(r",\s*([}\]])", r"\1", s)


def _quote_unquoted_ascii_keys(s: str) -> str:
    """
    宽松支持：
    {a: 1, foo_bar: 2}
    只处理 ASCII key，避免误伤中文正文。
    """
    return re.sub(
        r'([{\[,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)\s*:',
        r'\1"\2":',
        s,
    )


def _single_quoted_strings_to_double(s: str) -> str:
    """
    将简单单引号字符串转成 JSON 双引号字符串。
    已经优先 ast.literal_eval，这里只是兜底修复。
    """
    def repl(m: re.Match) -> str:
        content = m.group(1)
        try:
            # 让 json.dumps 负责转义内部字符
            return json.dumps(content, ensure_ascii=False)
        except Exception:
            return '"' + content.replace('"', '\\"') + '"'

    return re.sub(
        r"'([^'\\]*(?:\\.[^'\\]*)*)'",
        repl,
        s,
    )


def _insert_missing_commas(s: str) -> str:
    """
    修复模型常见错误：
    {
      "a": "xxx"
      "b": "yyy"
    }

    或：
    {
      "a": 1
      "b": 2
    }

    或同一行：
    {"a": "x" "b": "y"}
    """
    # value 后换行接下一个 "key":
    s = re.sub(
        r'((?:"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[}\]]))\s*\n\s*("([^"\\]|\\.)+"\s*:)',
        r"\1,\n\2",
        s,
    )

    # value 后同一行接下一个 "key":
    s = re.sub(
        r'((?:"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[}\]]))\s+(?="([^"\\]|\\.)+"\s*:)',
        r"\1, ",
        s,
    )

    # } 或 ] 后接 "key":
    s = re.sub(
        r"([}\]])\s*(\"[^\"\\]*(?:\\.[^\"\\]*)*\"\s*:)",
        r"\1, \2",
        s,
    )

    # 连续逗号
    s = re.sub(r",\s*,+", ",", s)

    return s


def _repair_json_like_text(s: str) -> str:
    """
    对“接近 JSON”的模型输出做有限修复。
    """
    s = s.strip()
    s = _strip_markdown_fence(s)
    s = _normalize_quotes(s)
    s = _remove_json_comments(s)
    s = _replace_python_literals(s)
    s = _remove_trailing_commas(s)
    s = _quote_unquoted_ascii_keys(s)

    # ast 已经处理过单引号，这里作为兜底再转一次
    s = _single_quoted_strings_to_double(s)

    # 缺逗号是你这次遇到的主要问题
    s = _insert_missing_commas(s)

    # 修完缺逗号后再删一次尾逗号
    s = _remove_trailing_commas(s)

    return s.strip()


def _iter_fenced_blocks(text: str) -> Iterable[str]:
    for m in re.finditer(
        r"```(?:json|JSON)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        yield m.group(1).strip()


def _iter_balanced_json_candidates(text: str) -> Iterable[str]:
    """
    从混杂文本中扫描平衡的 {...} 或 [...] 片段。
    比 first { + last } 更安全。
    """
    pairs = {
        "{": "}",
        "[": "]",
    }

    for start, ch in enumerate(text):
        if ch not in pairs:
            continue

        expected_stack = [pairs[ch]]
        in_string = False
        string_quote = ""
        escaped = False

        for i in range(start + 1, len(text)):
            c = text[i]

            if in_string:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == string_quote:
                    in_string = False
                continue

            if c in ('"', "'"):
                in_string = True
                string_quote = c
                continue

            if c in pairs:
                expected_stack.append(pairs[c])
                continue

            if expected_stack and c == expected_stack[-1]:
                expected_stack.pop()
                if not expected_stack:
                    yield text[start:i + 1].strip()
                    break


def _loose_key_value_parse(text: str) -> Optional[Dict[str, Any]]:
    """
    最后兜底：从类似
    key: value
    "key": value
    的行里抽取扁平 dict。

    这个不能还原嵌套结构，只用于保证流程不中断。
    """
    out: Dict[str, Any] = {}

    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line or line.startswith(("#", "-", "*", "//")):
            continue

        m = re.match(r"""^["']?([^"'{}\[\]:]{1,80})["']?\s*:\s*(.+?)$""", line)
        if not m:
            continue

        key = m.group(1).strip()
        val_raw = m.group(2).strip().rstrip(",")

        if not key:
            continue

        # 尝试解析 value
        val: Any
        try:
            val = json.loads(_repair_json_like_text(val_raw))
        except Exception:
            try:
                val = ast.literal_eval(val_raw)
            except Exception:
                val = val_raw.strip().strip('"').strip("'")

        out[key] = val

    if out:
        out["__json_parse_ok__"] = False
        out["__parse_mode__"] = "loose_key_value_parse"
        return out

    return None


def _parse_candidate(candidate: str) -> Optional[Dict[str, Any]]:
    """
    对单个候选 JSON 字符串进行多策略解析。
    """
    candidate = candidate.strip()
    if not candidate:
        return None

    # 1. 严格 JSON
    try:
        return _to_dict(_try_json_loads(candidate))
    except Exception:
        pass

    # 2. Python dict/list 风格
    try:
        return _to_dict(_try_ast_literal_eval(candidate))
    except Exception:
        pass

    # 3. 修复后 JSON
    repaired = _repair_json_like_text(candidate)
    try:
        obj = _try_json_loads(repaired)
        d = _to_dict(obj)
        d.setdefault("__json_repaired__", True)
        return d
    except Exception:
        pass

    # 4. 修复后 Python literal
    try:
        obj = _try_ast_literal_eval(repaired)
        d = _to_dict(obj)
        d.setdefault("__json_repaired__", True)
        return d
    except Exception:
        pass

    return None


def extract_json_object(text: str) -> Dict[str, Any]:
    """
    尽最大努力从模型输出中提取 JSON。

    保证：
    - 能解析就返回解析结果；
    - 解析不了也不 raise，返回 fallback dict；
    - fallback dict 带 raw_text，避免批量任务中断。

    注意：
    - fallback 不保证有业务字段；
    - 下游最好对 __json_parse_ok__ == False 的情况做 repair_status 或重试。
    """
    raw_text = "" if text is None else str(text)
    text = strip_think_blocks(raw_text).strip()

    if not text:
        return {
            "__json_parse_ok__": False,
            "__parse_mode__": "empty_output",
            "__raw_text__": raw_text,
        }

    candidates: List[Tuple[str, str]] = []

    # 1. markdown fenced blocks 优先
    for block in _iter_fenced_blocks(text):
        candidates.append(("fenced_block", block))

    # 2. 去掉 fence 后的全文
    stripped = _strip_markdown_fence(text)
    candidates.append(("full_text", stripped))

    # 3. 平衡 JSON 片段
    for cand in _iter_balanced_json_candidates(stripped):
        candidates.append(("balanced_candidate", cand))

    # 4. 旧逻辑兜底：first { 到 last }
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        candidates.append(("first_last_brace", stripped[start:end + 1]))

    # 5. array 兜底：first [ 到 last ]
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start >= 0 and end > start:
        candidates.append(("first_last_bracket", stripped[start:end + 1]))

    # 去重，保持顺序
    seen = set()
    uniq_candidates: List[Tuple[str, str]] = []
    for mode, cand in candidates:
        key = cand.strip()
        if key and key not in seen:
            seen.add(key)
            uniq_candidates.append((mode, key))

    last_error = None

    for mode, candidate in uniq_candidates:
        try:
            obj = _parse_candidate(candidate)
            if obj is not None:
                obj.setdefault("__parse_mode__", mode)
                return obj
        except Exception as e:
            last_error = e

    # 6. loose key-value parse
    loose = _loose_key_value_parse(stripped)
    if loose is not None:
        loose["__raw_text__"] = raw_text
        return loose

    # 7. 最后兜底：不再抛异常，避免批量流程崩掉
    return {
        "__json_parse_ok__": False,
        "__parse_mode__": "raw_fallback",
        "__parse_error__": str(last_error) if last_error else "unable_to_parse_json",
        "__raw_text__": raw_text,
        "__raw_text_head__": raw_text[:2000],
    }

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
    from model import llm_qwen

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
# 3. 本地输出：每个问题一个 Markdown + 可选单条 JSON
# =============================================================================


def empty_store() -> Dict[str, Any]:
    return {
        "meta": {
            "name": "superforecast_file_outputs",
            "version": "0.6-md-output",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "mode": "one_record_per_file",
        },
        "forecasts": [],
    }


def slugify_filename(text: str, max_len: int = 48) -> str:
    """生成适合文件名的短 slug。中文保留，去掉危险字符。"""
    text = str(text or "forecast").strip()
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    if not text:
        text = "forecast"
    return text[:max_len]


def output_dirs(config: Dict[str, Any] = CONFIG) -> Tuple[Path, Path]:
    report_dir = Path(config.get("report_output_dir", "./outputs/md"))
    json_dir = Path(config.get("json_output_dir", "./outputs/json"))
    report_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    return report_dir, json_dir


def record_output_basename(record: Dict[str, Any]) -> str:
    forecast_id = str(record.get("id") or short_id())
    created_at = str(record.get("created_at") or now_iso()).replace(":", "").replace("-", "")
    created_at = created_at.replace("T", "_")[:15]
    question = record.get("original_question") or record.get("contract", {}).get("normalized_question") or "forecast"
    return f"{created_at}_{forecast_id}_{slugify_filename(question)}"


def save_markdown_report(record: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> Optional[str]:
    if not config.get("save_markdown_report", True):
        return None
    report_dir, _ = output_dirs(config)
    basename = record_output_basename(record)
    path = report_dir / f"{basename}.md"
    markdown = str(record.get("markdown_report") or "")
    path.write_text(markdown, encoding="utf-8")
    return str(path)


def save_json_record(record: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> Optional[str]:
    if not config.get("save_json_record", True):
        return None
    _, json_dir = output_dirs(config)
    basename = record_output_basename(record)
    path = json_dir / f"{basename}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def save_forecast_record(record: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> Dict[str, Optional[str]]:
    """
    v0.6 输出策略：不再追加写入一个巨大的 forecast_mvp_store.json。

    每次预测输出：
    - outputs/md/<timestamp>_<id>_<question>.md
    - outputs/json/<timestamp>_<id>_<question>.json  可关闭

    函数名保留，是为了兼容 main.py 的既有调用。
    """
    record.setdefault("created_at", now_iso())
    record["updated_at"] = now_iso()

    # 先写入初版路径，随后把路径写回 record，再重写 JSON，保证 JSON 里也有输出路径。
    md_path = save_markdown_report(record, config=config)
    record.setdefault("output_paths", {})
    record["output_paths"]["markdown"] = md_path
    json_path = save_json_record(record, config=config)
    record["output_paths"]["json"] = json_path
    if json_path:
        Path(json_path).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": md_path, "json": json_path}


def _load_json_record_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def load_store(config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    """
    兼容旧接口：从 outputs/json/*.json 聚合出一个内存 store。
    不再依赖旧的单文件 storage_path。
    """
    store = empty_store()
    _, json_dir = output_dirs(config)
    records = []
    for path in sorted(json_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        obj = _load_json_record_file(path)
        if obj and obj.get("id"):
            obj.setdefault("output_paths", {})
            obj["output_paths"].setdefault("json", str(path))
            records.append(obj)

    # 兼容读取旧单文件，但不再写回旧 store。
    legacy_path = Path(config.get("storage_path", "./forecast_mvp_store.json"))
    if legacy_path.exists():
        try:
            legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
            for item in legacy.get("forecasts", []) if isinstance(legacy, dict) else []:
                if isinstance(item, dict) and item.get("id") and not any(r.get("id") == item.get("id") for r in records):
                    records.append(item)
        except Exception:
            pass

    records = sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)
    store["forecasts"] = records
    store["meta"]["updated_at"] = now_iso()
    store["meta"]["count"] = len(records)
    return store


def save_store(store: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> None:
    """
    兼容旧函数名。新版本不写 forecast_mvp_store.json。
    如确实需要索引，可打开 save_output_index。
    """
    if not config.get("save_output_index", False):
        return
    _, json_dir = output_dirs(config)
    index_path = json_dir / "_index.json"
    index_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def find_forecast(forecast_id: str, config: Dict[str, Any] = CONFIG) -> Optional[Dict[str, Any]]:
    store = load_store(config)
    for item in store.get("forecasts", []):
        if item.get("id") == forecast_id:
            return item
    return None


def update_forecast_record(forecast_id: str, patch: Dict[str, Any], config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    item = find_forecast(forecast_id, config=config)
    if item is None:
        raise ValueError(f"forecast_id 不存在：{forecast_id}")
    item.update(patch)
    item["updated_at"] = now_iso()

    # 重新写 JSON；Markdown 不自动改历史报告正文，除非调用方主动更新 markdown_report。
    json_path = item.get("output_paths", {}).get("json")
    if json_path:
        Path(json_path).write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        save_json_record(item, config=config)
    return item


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
        return {"n": 0, "avg_brier": None}

    return {"n": len(scores), "avg_brier": mean(scores)}
