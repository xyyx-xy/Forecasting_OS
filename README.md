利用Tetlock 的超预测思想，来开发LLM 组织预测流程，概率系统负责计算的大型Agent系统
conda create -n forecasting_os python=3.12
conda activate forecasting_os
=================================================
版本：LLM 结构化先验 + 数学聚合
模型：qwen/qwen3.6-27b
问题：2028年后北京房价会不会小幅上涨？
结果：
**预测类型**：multi_contract_portfolio
**原始问题**：2028年后北京房价会不会小幅上涨？
**综合概率**：61.0%
**粗略区间**：40.9% - 77.9%
**问题类型**：cloud_judgment
**语义坍缩风险**：medium
**推荐模式**：multi_contract_portfolio

## 原始语义
用户希望了解在2028年之后的时间段内，北京住宅房地产市场价格是否会出现温和的、非剧烈的正向变动，核心关切在于资产保值或适度增值的可能性，而非暴涨或暴跌。

语义坍缩说明：The original question 'slight increase' is a cloud judgment involving magnitude, direction, and potentially real vs. nominal value. Collapsing this into a single binary contract (e.g., 'Is CAGR between 0-5%?') risks losing the nuance of 'real purchasing power' (inflation adjustment) and 'market liquidity' (validity of price). While the decomposition provided multiple dimensions, the risk lies in the user or forecaster selecting only the nominal price metric as the sole truth, ignoring that a 4% nominal rise with 6% inflation is a 'loss' in user intent. Additionally, 'Beijing housing prices' is an aggregate that masks severe structural divergence between core and suburban areas, which a single average metric collapses.

如果强行单指标化，会丢失这些维度：
- Real purchasing power adjustment (inflation impact)
- Structural divergence between core and suburban districts
- Market liquidity and transaction volume validity
- Holding costs (interest rates, taxes) affecting net yield

## 维度展开
- **名义价格变动幅度** | weight=0.40 | measurability=0.95 | 直接对应‘小幅上涨’中的‘上涨’与‘小幅’。这是最核心的语义，指北京住宅市场平均成交价格在特定时间窗口内的绝对数值增长比例。
- **实际购买力/通胀调整后的价值** | weight=0.20 | measurability=0.85 | 对应‘小幅上涨’中隐含的‘真实收益’语义。如果名义上涨但通胀更高，实际资产价值是缩水的。用户可能关心的是资产是否保值或轻微增值，而非仅仅是数字变大。
- **市场流动性与交易活跃度** | weight=0.15 | measurability=0.90 | 对应‘上涨’的可持续性语义。有价无市的‘上涨’是脆弱的。小幅上涨通常伴随着健康的换手率，而非死水一潭或疯狂炒作。
- **政策与监管环境的稳定性** | weight=0.10 | measurability=0.70 | 对应‘2028年后’这一时间背景下的外部约束。‘小幅’暗示政策处于‘房住不炒’的平衡状态，既不限死也不刺激。
- **宏观经济与人口基本面支撑** | weight=0.10 | measurability=0.80 | 对应‘上涨’的内在动力。小幅上涨需要基本面的温和支撑，如人口净流入、收入增长。
- **市场情绪与预期管理** | weight=0.05 | measurability=0.60 | 对应‘小幅’中的心理预期。市场参与者是否普遍预期‘小幅上涨’，决定了行为的理性程度。

## Contract Portfolio 结果
- **名义价格变动幅度** | P=57.5% | final_weight=0.497 | semantic_prior=0.500 | proxy=2028-2030年北京全市二手房实际成交均价年化复合增长率 | proxy_risk=medium
  - 预测题：2028年1月1日至2030年12月31日期间，北京全市二手房实际成交均价的年化复合增长率（CAGR）是否落在 0% 至 5% 之间？
- **核心区名义价格变动幅度** | P=75.0% | final_weight=0.280 | semantic_prior=0.250 | proxy=2028-2030年北京核心区二手房实际成交均价年化复合增长率 | proxy_risk=medium
  - 预测题：2028年1月1日至2030年12月31日期间，北京核心区（东城、西城、海淀、朝阳）二手房实际成交均价的年化复合增长率（CAGR）是否落在 -2% 至 5% 之间？
- **实际购买力/通胀调整后的价值** | P=48.8% | final_weight=0.223 | semantic_prior=0.250 | proxy=2028-2030年北京房价名义涨幅减去同期北京CPI涨幅后的实际年化收益率 | proxy_risk=medium
  - 预测题：2028年1月1日至2030年12月31日期间，北京房价名义涨幅减去同期北京CPI涨幅后的实际年化收益率是否大于 0%？

## 子预测摘要
- **名义价格变动幅度**：57.5% 区间 23.4% - 85.6%
  - contract：2028年1月1日至2030年12月31日期间，北京全市二手房实际成交均价的年化复合增长率（CAGR）是否落在 0% 至 5% 之间？
  - base=55.0%, evidence=55.2%, causal=69.8%, panel=53.8%
- **实际购买力/通胀调整后的价值**：48.8% 区间 14.5% - 84.3%
  - contract：2028年1月1日至2030年12月31日期间，北京房价名义涨幅减去同期北京CPI涨幅后的实际年化收益率是否大于 0%？
  - base=45.0%, evidence=44.5%, causal=59.3%, panel=47.5%
- **核心区名义价格变动幅度**：75.0% 区间 41.4% - 92.7%
  - contract：2028年1月1日至2030年12月31日期间，北京核心区（东城、西城、海淀、朝阳）二手房实际成交均价的年化复合增长率（CAGR）是否落在 -2% 至 5% 之间？
  - base=65.0%, evidence=75.9%, causal=92.1%, panel=68.8%

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- final_weight 由 semantic_prior、measurability、user_intent_preservation_score、proxy_risk、lost_dimension_factor 共同决定；semantic_prior 仅表示拆题阶段语义覆盖先验。
- 子预测 logit 分歧：0.479
- portfolio logit sigma：0.815

## 结论
对原始云状问题，当前综合概率是 **61.0%**。

版本：LLM 结构化先验 + 数学聚合
模型：qwen/qwen3.6-35b-a3b
问题：2028年后北京房价会不会小幅上涨？
结果：
**预测类型**：multi_contract_portfolio
**原始问题**：2028年后北京房价会不会小幅上涨？
**综合概率**：49.1%
**粗略区间**：22.6% - 76.2%
**问题类型**：explicit_binary
**语义坍缩风险**：high
**推荐模式**：multi_contract_portfolio

## 原始语义
用户希望评估在2028年及之后的时间段内，北京房地产市场的价格水平是否会出现幅度有限（温和）的正向名义变动，且该变动需具备市场真实性（非有价无市）和一定的实际购买力支撑。

语义坍缩说明：原始拆解方案存在严重的语义坍缩风险。首先，将多维的‘小幅上涨’强行拆解为独立的二元合约（如C1判断方向，C2判断幅度），导致逻辑漏洞：C2允许价格下跌（违背‘上涨’意图），C1未约束幅度（可能暴涨）。其次，使用了高代理风险的指标：C4用成交量替代价格方向，存在极高的方向冲突（以价换量）；C3用全国CPI代理北京房价通胀，存在区域错配。最后，忽略了北京市场的结构性分化（核心区vs郊区）和新房限价导致的统计失真，若仅依赖单一二手房中位数或均价，将严重扭曲‘北京房价’的真实含义。

如果强行单指标化，会丢失这些维度：
- 价格变动的幅度界定（‘小幅’的具体阈值）
- 实际购买力变化（扣除通胀后的真实增值）
- 区域结构性分化（核心区与郊区的走势差异）
- 新房与二手房的价格联动机制（限价扭曲）
- 市场流动性支撑（有价无市风险）

## 维度展开
- **名义价格水平变动与幅度界定** | weight=0.45 | measurability=0.90 | 直接对应“房价上涨”的字面含义，即货币标价的变化，不考虑通胀因素。这是用户最直观感知的“上涨”。需同时定义“小幅”的数值区间（如0%-5%）。
- **实际价格水平变动** | weight=0.25 | measurability=0.70 | 扣除通货膨胀后的房价变动，反映房价相对于一般商品和服务的真实购买力变化。对应“小幅”中的实际价值判断。
- **市场流动性与交易活跃度** | weight=0.15 | measurability=0.85 | 价格变动需要交易支撑。如果只有挂牌价上涨但无成交，可能是“有价无市”。此维度确保价格上涨是真实的市场行为，而非泡沫或数据操纵。
- **政策约束与行政干预强度** | weight=0.10 | measurability=0.60 | 北京房价受政策影响极大。此维度评估政策环境是否允许或限制价格上涨，特别是限购、限贷、限价等行政手段。
- **区域异质性与结构性分化** | weight=0.05 | measurability=0.75 | 北京房价并非铁板一块。核心区、近郊区、远郊区的房价走势可能完全不同。此维度评估“北京房价”作为一个整体的代表性。

## Contract Portfolio 结果
- **名义价格水平变动与幅度界定** | P=39.4% | final_weight=0.531 | semantic_prior=0.474 | proxy=北京加权房价指数同比/环比增长率 | proxy_risk=low
  - 预测题：2028年1月1日至2029年12月31日期间，北京加权房价指数（核心区权重60%，郊区权重40%）的年均名义涨幅是否严格介于0%（含）至5%（不含）之间？
- **实际价格水平变动** | P=47.8% | final_weight=0.225 | semantic_prior=0.263 | proxy=北京加权房价指数实际增长率 | proxy_risk=medium
  - 预测题：2028年1月1日至2029年12月31日期间，北京加权房价指数实际增长率（名义涨幅减去北京本地居住成本指数涨幅）是否大于0？
- **市场流动性与交易活跃度** | P=63.9% | final_weight=0.142 | semantic_prior=0.158 | proxy=北京二手房月度成交量 | proxy_risk=medium
  - 预测题：2028年全年北京二手房月度成交量是否未出现显著萎缩（即全年总成交量不低于2026年对应月份平均水平的90%）？
- **政策约束与行政干预强度** | P=78.6% | final_weight=0.102 | semantic_prior=0.105 | proxy=北京限购政策松紧程度指数（如社保年限要求、首付比例） | proxy_risk=low
  - 预测题：截至2028年12月31日，北京是否未实施全面取消限购或大幅降低首付比例（首套房首付比例降至20%以下）的政策？

## 子预测摘要
- **名义价格水平变动与幅度界定**：39.4% 区间 11.1% - 77.2%
  - contract：2028年1月1日至2029年12月31日期间，北京加权房价指数（核心区权重60%，郊区权重40%）的年均名义涨幅是否严格介于0%（含）至5%（不含）之间？
  - base=35.0%, evidence=37.2%, causal=41.0%, panel=38.7%
- **实际价格水平变动**：47.8% 区间 13.6% - 84.1%
  - contract：2028年1月1日至2029年12月31日期间，北京加权房价指数实际增长率（名义涨幅减去北京本地居住成本指数涨幅）是否大于0？
  - base=45.0%, evidence=41.5%, causal=56.4%, panel=48.7%
- **市场流动性与交易活跃度**：63.9% 区间 25.4% - 90.2%
  - contract：2028年全年北京二手房月度成交量是否未出现显著萎缩（即全年总成交量不低于2026年对应月份平均水平的90%）？
  - base=65.0%, evidence=62.9%, causal=72.6%, panel=64.3%
- **政策约束与行政干预强度**：78.6% 区间 37.1% - 95.8%
  - contract：截至2028年12月31日，北京是否未实施全面取消限购或大幅降低首付比例（首套房首付比例降至20%以下）的政策？
  - base=75.0%, evidence=90.7%, causal=89.8%, panel=77.3%

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- final_weight 由 semantic_prior、measurability、user_intent_preservation_score、proxy_risk、lost_dimension_factor 共同决定；semantic_prior 仅表示拆题阶段语义覆盖先验。
- 子预测 logit 分歧：0.662
- portfolio logit sigma：1.198

## 结论
对原始云状问题，当前综合概率是 **49.1%**。

模型：google/gemma-4-31b
问题：2028年后北京房价会不会小幅上涨？
结果：
**预测类型**：multi_contract_portfolio
**原始问题**：2028年后北京房价会不会小幅上涨？
**综合概率**：50.9%
**粗略区间**：36.4% - 65.3%
**问题类型**：cloud_judgment
**语义坍缩风险**：low
**推荐模式**：multi_contract_portfolio

## 原始语义
用户关心在2028年之后，北京房地产市场的价格走势是否会呈现出一种温和且正向的增长趋势，而非剧烈波动或持续下跌。

语义坍缩说明：The decomposition resists collapsing 'slight increase' into a simple binary. It separates nominal, real, magnitude, liquidity, and structural dimensions.

如果强行单指标化，会丢失这些维度：
- Inflation adjustment
- Magnitude constraint
- Market liquidity
- Structural divergence

## 维度展开
- **名义价格变动幅度** | weight=0.30 | measurability=0.90 | 市场成交价格在数值上的绝对增长，反映最直观的上涨方向。
- **涨幅量级界定（小幅 vs 剧烈）** | weight=0.20 | measurability=0.80 | 区分温和增长与泡沫式暴涨，覆盖‘小幅’这一限定词。
- **实际价值增长（剔除通胀）** | weight=0.20 | measurability=0.70 | 判断房价涨幅是否跑赢货币贬值，区分‘数字上涨’与‘资产增值’。
- **市场流动性与成交支撑** | weight=0.15 | measurability=0.80 | 确保价格上涨有真实交易支撑，防止‘僵尸价’。
- **结构性分化程度** | weight=0.15 | measurability=0.60 | 识别是普涨还是局部上涨，防止核心区暴涨掩盖整体阴跌。

## Contract Portfolio 结果
- **名义价格变动幅度** | P=62.0% | final_weight=0.297 | semantic_prior=0.300 | proxy=三年平均名义涨幅 | proxy_risk=medium
  - 预测题：2029-2031年期间，北京二手房成交均价的年度平均涨幅是否为正？
- **涨幅量级界定（小幅 vs 剧烈）** | P=36.6% | final_weight=0.245 | semantic_prior=0.200 | proxy=三年平均名义涨幅百分比 | proxy_risk=low
  - 预测题：2029-2031年期间，北京二手房名义房价的年度平均涨幅是否落在 [1%, 5%] 的区间内？
- **实际价值增长（剔除通胀）** | P=43.7% | final_weight=0.177 | semantic_prior=0.200 | proxy=名义涨幅 - CPI涨幅 | proxy_risk=medium
  - 预测题：2029-2031年期间，北京房价的平均名义涨幅是否跑赢了同期的北京市年度平均CPI？
- **市场流动性与成交支撑** | P=48.7% | final_weight=0.145 | semantic_prior=0.150 | proxy=成交量维持率 + 价格底线 | proxy_risk=medium
  - 预测题：2029-2031年期间，北京二手房的月均成交套数是否保持在 2028 年水平的 80% 以上且价格未出现单年跌幅超过 10%？
- **结构性分化程度** | P=63.9% | final_weight=0.137 | semantic_prior=0.150 | proxy=核心区与远郊区涨幅差 | proxy_risk=medium
  - 预测题：2029-2031年期间，北京核心区（东城、西城）的平均年度房价涨幅是否比远郊区（房山、延庆）高出 2% 以上？

## 子预测摘要
- **名义价格变动幅度**：62.0% 区间 27.7% - 87.5%
  - contract：2029-2031年期间，北京二手房成交均价的年度平均涨幅是否为正？
  - base=60.0%, evidence=66.5%, causal=67.9%, panel=58.3%
- **涨幅量级界定（小幅 vs 剧烈）**：36.6% 区间 9.4% - 76.4%
  - contract：2029-2031年期间，北京二手房名义房价的年度平均涨幅是否落在 [1%, 5%] 的区间内？
  - base=30.0%, evidence=31.5%, causal=44.6%, panel=34.8%
- **实际价值增长（剔除通胀）**：43.7% 区间 13.6% - 79.3%
  - contract：2029-2031年期间，北京房价的平均名义涨幅是否跑赢了同期的北京市年度平均CPI？
  - base=40.0%, evidence=37.7%, causal=51.8%, panel=42.9%
- **市场流动性与成交支撑**：48.7% 区间 16.1% - 82.5%
  - contract：2029-2031年期间，北京二手房的月均成交套数是否保持在 2028 年水平的 80% 以上且价格未出现单年跌幅超过 10%？
  - base=40.0%, evidence=45.0%, causal=61.1%, panel=50.6%
- **结构性分化程度**：63.9% 区间 30.8% - 87.6%
  - contract：2029-2031年期间，北京核心区（东城、西城）的平均年度房价涨幅是否比远郊区（房山、延庆）高出 2% 以上？
  - base=65.0%, evidence=68.1%, causal=67.0%, panel=61.5%

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- final_weight 由 semantic_prior、measurability、user_intent_preservation_score、proxy_risk、lost_dimension_factor 共同决定；semantic_prior 仅表示拆题阶段语义覆盖先验。
- 子预测 logit 分歧：0.430
- portfolio logit sigma：0.594

## 结论
对原始云状问题，当前综合概率是 **50.9%**。