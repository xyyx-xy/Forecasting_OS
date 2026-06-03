=================================================
版本：LLM 结构化先验 + 数学聚合
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