# v0.5.2 Mechanism Chain Factor Graph Patch

本压缩包基于用户上传的模块化项目文件修改，核心变更集中在 `pengine.py`、`config.py`、`main.py`。

## 主要新增能力

1. LLM 机制链结构化
   - 新增 `MECHANISM_CHAIN_STRUCTURER_PROMPT`
   - 新增 `structure_mechanism_chains_by_llm()`
   - LLM 只负责结构识别，不输出最终概率。

2. 机制角色识别
   - `upstream_driver`
   - `mediator`
   - `direct_driver`
   - `proxy_indicator`
   - `shock_driver`
   - `counterforce`
   - `unknown`

3. 链内防重复计数
   - 新增 `aggregate_chain_effects_from_llm_structure()`
   - 使用 `strongest signal + partial corroboration`
   - 同方向链内信号只部分加权；反方向信号保留较高抵消权重。

4. Mechanism Chain Factor Graph Monte Carlo
   - `target_cpd.type = mechanism_chain_logistic`
   - target 从直接吃所有 factor，改为吃 chain_factors。

5. chain-level sensitivity
   - 新增 `compute_chain_sensitivity()`
   - 报告中展示 top chain sensitivity。

6. 弱边展示
   - LLM 输出 `weak_edges_for_display`
   - 转换成 graph edges，仅用于解释展示和链内关系提示，不作为严格因果发现。

## 修改文件

- `pengine.py`
  - 核心概率引擎改造。
- `config.py`
  - 新增 `CONFIG["causal_graph"]["mechanism_chain"]` 配置。
- `main.py`
  - 报告展示新增 Mechanism Chain Audit、chain sensitivity、chain_count、weak_edge_count。

## 未修改核心流程

- Cloud-to-Contract Agent 0-11 未改。
- evidence cards 生成逻辑未改。
- panel 预测逻辑未改。
- portfolio weighted logit 聚合逻辑未改。
- 本地 JSON 存储和 resolve/Brier 逻辑未改。

## 检查

已执行：

```bash
python -m py_compile config.py model.py utils.py schema.py agent_panel.py agent0_11.py pengine.py main.py
```

并通过一个 mock 测试验证 `mechanism_chain_logistic` fallback 路径可运行。
