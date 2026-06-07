# v0.6 Markdown Output Module Patch

本版本把项目从“主流程里直接写本地 JSON store”改成“每个问题直接输出一份清晰 Markdown 报告”。

## 核心变化

### 1. 新增 `reporter.py`

`reporter.py` 只负责结果表达：

- `build_single_report_json()`
- `build_single_markdown_report()`
- `build_portfolio_report_json()`
- `build_portfolio_markdown_report()`

`main.py` 不再内置大段报告拼装逻辑，主流程只负责调用模块。

### 2. `utils.py` 负责本地输出

`utils.py` 现在集中负责本地文件输出和兼容存储接口：

- `save_forecast_record(record, config)`
- `save_markdown_report(record, config)`
- `save_json_record(record, config)`
- `load_store(config)`
- `find_forecast(forecast_id, config)`
- `update_forecast_record(forecast_id, patch, config)`
- `local_domain_brier_stats(domain, config)`

注意：`save_forecast_record()` 保留函数名，是为了兼容 `main.py` 原有调用；但它不再 append 写入 `forecast_mvp_store.json`。

### 3. 每个问题输出单独文件

默认输出：

```text
outputs/md/<时间>_<id>_<问题>.md
outputs/json/<时间>_<id>_<问题>.json
```

Markdown 是主要结果；JSON 是结构化记录，可关闭。

### 4. `config.py` 新增输出配置

```python
"report_output_dir": "./outputs/md",
"json_output_dir": "./outputs/json",
"save_markdown_report": True,
"save_json_record": True,
"save_output_index": False,
```

旧字段 `storage_path` 保留，只用于兼容读取历史文件，不再默认写入。

### 5. 新增 `run_questions.py`

用于批量跑多个问题：

```python
from run_questions import run_questions

records = run_questions([
    "明年中国鸡肉价格会不会上涨？",
    "2027年中国AI创业公司融资环境会不会比2026年更好？",
])
```

每个问题会各自输出一份 Markdown。

## 当前文件职责

```text
main.py          主流程编排
reporter.py      清晰 Markdown / report_json 生成
utils.py         本地 Markdown/JSON 文件输出、查询、更新、Brier 统计
pengine.py       概率引擎与 Mechanism Chain Factor Graph
agent0_11.py     Cloud-to-Contract 问题拆解
agent_panel.py   证据卡、问题分解、多 Agent panel
config.py        所有参数配置
model.py         OpenAI-compatible LLM client
schema.py        prompt JSON schema
run_questions.py 批量运行入口
```

## 检查

已执行：

```bash
python -m py_compile config.py model.py utils.py schema.py agent_panel.py agent0_11.py pengine.py reporter.py main.py run_questions.py
```

并验证 `utils.save_forecast_record()` 会输出单条 Markdown 和 JSON 文件。
