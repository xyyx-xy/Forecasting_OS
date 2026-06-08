# -*- coding: utf-8 -*-
"""
run_questions.py

批量运行预测问题。每个问题都会通过 main.run_forecast 输出一份 Markdown，
并按 config 决定是否输出对应 JSON。
"""

from __future__ import annotations

from typing import Dict, List, Any

from config import CONFIG
from main import run_forecast


def run_questions(
    questions: List[str],
    user_evidence: str = "",
    config: Dict[str, Any] = CONFIG,
) -> List[Dict[str, Any]]:
    records = []
    for idx, q in enumerate(questions, start=1):
        q = str(q or "").strip()
        if not q:
            continue
        print(f"\n========== Question {idx}/{len(questions)} ==========")
        print(q)
        record = run_forecast(q, user_evidence=user_evidence, config=config)
        records.append(record)
    return records


if __name__ == "__main__":
    QUESTIONS = [
        # "2035年前中国是否会统一台湾？",
        # "未来十年美国是否会爆发内战？",
        # "未来15年全球是否会发生一次大规模金融危机？",
        # "2027年底比特币价格会是多少？",
        # "2030年前人形机器人是否会进入普通家庭？",
        # "OpenAI 未来五年是否会成为一家成功的商业公司？",
        "华为手机未来三年是否能重回高端市场第一梯队？",
        "延迟退休政策是否会改善中国养老金压力？",
        "中国未来五年的房地产政策是否能成功救市？",
        "未来十年中国中产阶级会不会缩水？",
    ]
    run_questions(QUESTIONS, config=CONFIG)
