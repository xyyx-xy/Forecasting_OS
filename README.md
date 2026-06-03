利用Tetlock 的超预测思想，来开发LLM 组织预测流程，概率系统负责计算的大型Agent系统
conda create -n forecasting_os python=3.12
conda activate forecasting_os
=================================================
版本：LLM 结构化先验 + bayesian_causal_graph_logistic_cpd_monte_carlo
模型：qwen/qwen3.6-27b
问题：2027年中国ai创业公司的融资环境会不会比2026年更好？
结果：
**预测类型**：multi_contract_portfolio
**原始问题**：2027年中国ai创业公司的融资环境会不会比2026年更好？
**综合概率**：51.1%
**粗略区间**：26.6% - 75.1%
**问题类型**：cloud_judgment
**语义坍缩风险**：high
**推荐模式**：multi_contract_portfolio

## 原始语义
用户希望评估2027年中国AI创业公司在获取外部资本时的综合难易程度、成本及市场情绪，是否相对于2026年有实质性改善。这包括资金可得性、估值合理性、融资效率、退出预期及政策确定性等多个维度。

语义坍缩说明：The original question 'financing environment better' is a multidimensional construct involving liquidity, cost, sentiment, and exit prospects. Reducing it to a single metric (e.g., total funding amount or deal count) creates a high risk of accidental substitution. For instance, total funding could rise due to a few mega-deals while the environment for the majority of startups deteriorates (higher dilution, longer cycles, stricter terms).

如果强行单指标化，会丢失这些维度：
- Valuation multiples and founder dilution rates (Cost of Capital)
- Time-to-close and success rates (Efficiency)
- Prevalence of harsh terms like buybacks or liquidation preferences (Risk Allocation)
- Exit liquidity via M&A or Secondary markets (Confidence)
- Structural divergence between Infrastructure vs. Application layers (Sector Health)

## 维度展开
- **资本供给总量与活跃度（应用层侧重）** | weight=0.28 | measurability=0.85 | 衡量市场上可用于AI创业公司（特别是应用层）的资金池大小及投资机构的出手频率。这是‘融资环境’最基础的流动性指标。
- **融资条款严苛程度（隐性成本）** | weight=0.22 | measurability=0.50 | 衡量创业者在融资过程中承担的非货币风险，如回购条款、对赌协议、清算优先权等。‘更好’意味着条款更宽松，创始人控制权风险更低。
- **融资效率与周期** | weight=0.17 | measurability=0.60 | 衡量从启动融资到资金到账的难易程度和时间成本。‘更好’意味着更容易拿到Term Sheet，且打款速度更快。
- **退出预期与二级市场联动** | weight=0.22 | measurability=0.80 | 衡量一级市场资金退出的通畅程度。‘更好’意味着IPO、并购或老股转让的预期更明确、周期更短。
- **投资者风险偏好与赛道聚焦** | weight=0.11 | measurability=0.60 | 衡量资本对AI不同细分领域及早期项目的态度变化。‘更好’意味着资本不再只追逐热点，而是对更多元、更早期的创新持开放态度。

## Contract Portfolio 结果
- **资本供给总量与活跃度（应用层侧重）** | P=46.5% | weight=0.379 | proxy=2027年中国AI应用层创业公司年度融资总额 | proxy_risk=medium
  - 预测题：2027年中国AI应用层（非大模型基础层）创业公司的年度融资总额是否高于2026年？
- **退出预期与二级市场联动** | P=53.8% | weight=0.278 | proxy=2027年中国AI领域并购交易总金额 | proxy_risk=medium
  - 预测题：2027年中国AI领域并购交易（M&A）总金额是否高于2026年？
- **融资条款严苛程度（隐性成本）** | P=50.4% | weight=0.175 | proxy=2027年中国AI早期项目融资中包含‘回购条款’或‘对赌协议’的交易占比 | proxy_risk=medium
  - 预测题：2027年中国AI早期项目（Seed/A轮）融资中，包含‘回购条款’或‘对赌协议’的交易占比是否低于2026年？
- **融资效率与周期** | P=47.6% | weight=0.093 | proxy=2027年中国AI应用层初创公司获得首轮融资的平均周期 | proxy_risk=medium
  - 预测题：2027年中国AI应用层初创公司获得首轮融资的平均周期是否短于2026年？
- **老股转让市场流动性** | P=69.6% | weight=0.075 | proxy=2027年中国AI领域老股转让交易金额 | proxy_risk=medium
  - 预测题：2027年中国AI领域老股转让（Secondary）的交易金额是否高于2026年？

## 子预测摘要
- **资本供给总量与活跃度（应用层侧重）**：46.5% 区间 16.6% - 79.2%
  - contract：2027年中国AI应用层（非大模型基础层）创业公司的年度融资总额是否高于2026年？
  - base=45.0%, evidence=44.6%, causal=46.4%, panel=49.2%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=0, causal_interval=13.0%-76.5%
  - top causal sensitivity：
    - 宏观流动性与LP资金释放节奏: do_true=56.6%, do_false=32.9%, swing=0.237
    - AI应用层商业化落地速度: do_true=59.9%, do_false=38.3%, swing=0.217
    - 算力成本与API价格下降: do_true=53.4%, do_false=33.9%, swing=0.195
- **融资条款严苛程度（隐性成本）**：50.4% 区间 17.2% - 83.3%
  - contract：2027年中国AI早期项目（Seed/A轮）融资中，包含‘回购条款’或‘对赌协议’的交易占比是否低于2026年？
  - base=45.0%, evidence=51.9%, causal=56.4%, panel=49.2%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=0, causal_interval=26.7%-84.4%
  - top causal sensitivity：
    - 美元基金撤退与人民币基金的风险偏好: do_true=62.6%, do_false=38.2%, swing=0.244
    - LP回报压力与‘耐心资本’的实际落地效果: do_true=49.8%, do_false=67.1%, swing=0.174
    - 监管政策对‘对赌协议’的合规性审查: do_true=45.6%, do_false=61.2%, swing=0.156
- **退出预期与二级市场联动**：53.8% 区间 22.1% - 82.7%
  - contract：2027年中国AI领域并购交易（M&A）总金额是否高于2026年？
  - base=45.0%, evidence=54.2%, causal=60.2%, panel=58.2%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=6, edges=0, causal_interval=25.5%-88.8%
  - top causal sensitivity：
    - IPO退出渠道持续受阻: do_true=66.3%, do_false=41.1%, swing=0.252
    - 大厂产业资本（CVC）整合意愿增强: do_true=67.3%, do_false=48.1%, swing=0.191
    - AI创业公司估值回归理性: do_true=65.7%, do_false=51.1%, swing=0.146
- **老股转让市场流动性**：69.6% 区间 34.2% - 90.9%
  - contract：2027年中国AI领域老股转让（Secondary）的交易金额是否高于2026年？
  - base=65.0%, evidence=76.6%, causal=78.6%, panel=65.2%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=1, causal_interval=53.0%-90.4%
  - top causal sensitivity：
    - 存量AI基金到期清算压力: do_true=81.7%, do_false=60.3%, swing=0.214
    - IPO审核政策对二级市场的挤出效应: do_true=81.7%, do_false=69.7%, swing=0.119
    - S基金买方活跃度与资金供给: do_true=81.3%, do_false=69.6%, swing=0.117
- **融资效率与周期**：47.6% 区间 15.4% - 81.9%
  - contract：2027年中国AI应用层初创公司获得首轮融资的平均周期是否短于2026年？
  - base=45.0%, evidence=44.9%, causal=51.1%, panel=48.7%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=0, causal_interval=17.9%-79.9%
  - top causal sensitivity：
    - LP资金供给与Dry Powder充裕度: do_true=59.8%, do_false=36.2%, swing=0.237
    - 监管合规与数据安全审查强度: do_true=38.6%, do_false=62.0%, swing=0.234
    - AI应用层技术成熟度与标准化: do_true=56.0%, do_false=37.0%, swing=0.190

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- 权重由 semantic_coverage_weight、measurability、user_intent_preservation_score、proxy_risk 共同决定。
- 子预测 logit 分歧：0.352
- portfolio logit sigma：1.058

## 结论
对原始云状问题，当前综合概率是 **51.1%**。


版本：LLM 结构化先验 + bayesian_causal_graph_logistic_cpd_monte_carlo
模型：qwen/qwen3.6-27b
问题：明年中国鸡肉价格会不会上涨？
结果：
**预测类型**：single_contract
**预测题**：2027年中国鸡肉批发均价是否高于2026年平均水平？
**最终概率**：48.0%
**粗略区间**：17.0% - 80.6%
**截止日期**：2028-02-28
**领域**：business
**可预测性评分**：0.60

## 语义覆盖信息
- 当前维度：终端价格直接锚定
- 代理指标：全国鸡肉批发均价
- proxy_risk：low
- 原意保留分：0.95
- 语义覆盖权重：0.53
- 该子合约未覆盖：未区分白羽和黄羽的具体价格差异，若两者走势背离，综合均价可能掩盖结构性变化

## 判定标准
若2027年1-12月全国鸡肉批发均价（元/公斤，涵盖白羽和黄羽肉鸡的综合加权平均或主要代表性品种）高于2026年1-12月全国鸡肉批发均价，则结果为‘是’；否则为‘否’。数据以农业农村部全国农产品批发市场价格信息系统或国家统计局发布的年度平均数据为准。
判定来源：农业农村部全国农产品批发市场价格信息系统, 国家统计局CPI分项数据, 行业咨询机构（如卓创资讯、新牧网）年度价格回顾

## 概率计算拆解
- Base rate prior：45.0%
- Evidence update 后：53.0%
- Bayesian causal graph / Monte Carlo 后：41.0%
- 多 Agent panel 聚合后：52.8%
- Raw ensemble：47.7%
- Calibrated final：48.0%

## Ensemble 权重
- base: 0.291
- evidence: 0.272
- causal: 0.243
- panel: 0.194

## 参考类 / Base Rate
参考类：中国农产品价格年度同比变动历史（2015-2025）
先验概率：45.0%
置信度：0.60
说明：回顾过去十年中国主要农产品（猪、鸡、蛋、菜）的价格走势，由于周期性波动和均值回归特性，价格上涨与下跌的概率大致相当，略偏向于在经历低谷后反弹或高位回落的对称分布。考虑到鸡肉周期比猪周期短且波动相对平缓，若无极端外部冲击，价格大幅单边上涨的先验概率略低于50%。

## 关键因子
- **2026年供给过剩导致的产能去化**：P=60.0%，effect_log_odds=+0.80，方向=increase。鸡肉价格具有明显的滞后周期。如果2026年（基准年）价格低迷导致养殖户大规模去产能，2027年的供给将收缩，从而推高价格。这是最核心的周期驱动逻辑。
- **饲料成本（玉米/豆粕）上涨**：P=40.0%，effect_log_odds=+0.50，方向=increase。饲料成本占养殖成本的60%-70%。如果全球粮食供应紧张或地缘政治导致原料价格上涨，养殖成本抬升将支撑终端批发价，甚至迫使养殖户挺价。
- **猪肉价格高位带来的替代效应**：P=50.0%，effect_log_odds=+0.60，方向=increase。鸡肉是猪肉的主要替代品。如果2027年猪周期处于上行阶段，猪肉价格高企，消费者和餐饮B端将增加鸡肉消费，拉动鸡价上涨。
- **宏观经济与消费需求疲软**：P=30.0%，effect_log_odds=-0.70，方向=decrease。如果宏观经济承压，居民消费降级，可能减少对高价蛋白或整体肉类消费，导致需求端疲软，压制价格上涨空间。
- **突发禽流感疫情**：P=10.0%，effect_log_odds=+1.20，方向=increase。虽然概率低，但一旦发生大规模疫情，供给瞬间收缩，价格将暴涨。这是一个典型的尾部风险因子。
- **头部企业产能扩张计划执行**：P=70.0%，effect_log_odds=-0.60，方向=decrease。如果2026年并未出现严重去产能，且头部企业按计划扩产，2027年供给可能过剩，导致价格下跌。这与第一个因素存在负相关依赖。

## Bayesian Causal Graph
- method：bayesian_causal_graph_logistic_cpd_monte_carlo
- Monte Carlo samples：12000
- causal credible interval：12.1% - 74.6%
- node_count：6, edge_count：1
- target_evidence_update：+0.000
- 关键节点：
  - 2026年供给过剩导致的产能去化 | prior=60.0%, adjusted=66.8%, target_weight=+0.560
  - 突发禽流感疫情 | prior=10.0%, adjusted=10.5%, target_weight=+0.480
  - 头部企业产能扩张计划执行 | prior=70.0%, adjusted=66.1%, target_weight=-0.480
  - 猪肉价格高位带来的替代效应 | prior=50.0%, adjusted=52.6%, target_weight=+0.360
  - 宏观经济与消费需求疲软 | prior=30.0%, adjusted=29.0%, target_weight=-0.350
  - 饲料成本（玉米/豆粕）上涨 | prior=40.0%, adjusted=42.3%, target_weight=+0.250
- do-intervention sensitivity：
  - 2026年供给过剩导致的产能去化: do_true=48.4%, do_false=26.9%, swing=0.216
  - 头部企业产能扩张计划执行: do_true=34.2%, do_false=55.0%, swing=0.208
  - 突发禽流感疫情: do_true=59.3%, do_false=38.6%, swing=0.207
  - 猪肉价格高位带来的替代效应: do_true=48.2%, do_false=32.9%, swing=0.152
  - 宏观经济与消费需求疲软: do_true=30.9%, do_false=44.3%, swing=0.134

## 最有诊断价值的证据
- [increase] 鸡肉价格具有明显的周期性波动特征，通常滞后于产能变化。若2026年行业处于亏损或低利润状态，将触发父母代种鸡的淘汰和产能去化，从而在2027年导致供给收缩并推高价格。 | weighted_log_odds=+0.242 | quality_weight=0.403 | source=background/background_prior
  - 这是农产品价格预测的核心逻辑。虽然无法确认2026年具体亏损程度，但基于周期性规律，产能去化是价格上涨的最强前置指标。
- [decrease] 头部养殖企业（如圣农、温氏等）的产能扩张计划若如期执行，且2026年未出现严重去产能，2027年市场供给可能过剩，导致价格下跌。 | weighted_log_odds=-0.179 | quality_weight=0.358 | source=background/background_prior
  - 规模化养殖企业的产能投放具有计划性和刚性。若行业整体产能未有效出清，新增产能将加剧供过于求，压制价格。
- [increase] 鸡肉与猪肉存在显著的替代效应。若2027年中国猪肉价格处于高位（例如猪周期上行阶段），消费者和餐饮B端将增加鸡肉消费，拉动鸡价上涨。 | weighted_log_odds=+0.103 | quality_weight=0.206 | source=background/background_prior
  - 中国肉类消费结构中，猪鸡替代关系明确。猪周期与鸡周期往往不同步，猪价高企是鸡价上涨的重要外部需求驱动力。
- [increase] 饲料成本（玉米、豆粕）占肉鸡养殖成本的60%-70%。若2027年全球粮食供应紧张或地缘政治导致原料价格显著上涨，将抬升养殖成本底线，支撑终端批发价上涨。 | weighted_log_odds=+0.094 | quality_weight=0.235 | source=background/background_prior
  - 成本推动型通胀在农产品中常见。虽然需求端可能抑制高价，但成本刚性会限制价格下跌空间，并可能在供给偏紧时转化为价格上涨动力。
- [increase] 突发高致病性禽流感疫情若发生，将导致区域性扑杀和供给瞬间收缩，引发价格短期暴涨。 | weighted_log_odds=+0.056 | quality_weight=0.080 | source=background/background_prior
  - 虽然发生概率低（尾部风险），但一旦发生对价格的冲击极大。作为背景先验，需考虑其不对称的影响。
- [neutral] 2026年作为基准年，若其全年平均价格因前期产能过剩而处于历史低位，则2027年价格即使仅小幅反弹或持平，也可能在同比上表现为‘高于’，但这更多是基数效应而非强劲上涨。 | weighted_log_odds=+0.054 | quality_weight=0.269 | source=background/background_prior
  - 合约比较的是绝对值。低基数会增加‘高于’的概率，但这属于统计偏差，需结合2027年实际供需判断趋势强度。

## 多 Agent 分歧
- **outside_view**：48.0%，confidence=0.65。基于2015-2025年中国鸡肉价格年度同比变动的历史基准，价格上涨与下跌的概率大致均衡。考虑到均值回归特性，若无极端外部冲击，先验概率略低于50%，反映市场常态下的对称波动。
  - 更新触发器：2026年全年的实际平均鸡肉价格数据（确定基准高低）以及2026年底父母代种鸡存栏量的显著变化数据。
- **inside_view**：62.0%，confidence=0.70。核心逻辑在于产能周期。若2026年因价格低迷导致行业去产能（概率0.6），2027年供给将收缩。同时，若2027年猪周期上行带动替代需求，将进一步推高鸡价。供给侧的滞后效应是主要驱动因素。
  - 更新触发器：2026年Q4至2027年Q1的父母代种鸡淘汰率数据，以及2027年玉米豆粕饲料成本的季度走势。
- **skeptic**：42.0%，confidence=0.60。头部养殖企业（如圣农、温氏）的产能扩张计划具有刚性，若2026年未出现严重去产能，2027年新增产能投放将导致供给过剩。此外，宏观经济疲软可能抑制整体肉类消费需求，压制价格上涨空间。
  - 更新触发器：主要养殖企业2027年实际出栏量数据超预期增长，或宏观经济数据显示居民肉类消费支出显著萎缩。
- **optimist**：68.0%，confidence=0.65。看好成本推动和需求替代的双重利好。若2027年饲料成本上涨抬升价格底线，且猪肉价格处于高位引发强劲替代效应，鸡肉价格有望显著上涨。此外，低基数效应（若2026年价格较低）也增加了同比上涨的概率。
  - 更新触发器：2027年猪肉批发均价大幅高于2026年，或发生区域性高致病性禽流感导致供给瞬间收缩。
- **base_rate_guardian**：46.0%，confidence=0.75。严格锚定历史基准率0.45。虽然内部观点提示周期上行可能，但考虑到预测的不确定性和均值回归的强大力量，不应过度偏离历史平均水平。小幅上调以反映潜在的周期反弹预期，但保持保守。
  - 更新触发器：长期历史数据显示鸡肉价格周期趋势发生结构性改变（如持续单边上涨或下跌），而非周期性波动。
- **domain_generalist**：55.0%，confidence=0.70。综合供需、成本和替代品因素。供给端去产能预期（+10%）和猪周期替代效应（+5%）略占上风，但被头部企业扩产风险（-5%）和宏观需求疲软（-5%）部分抵消。考虑到尾部风险（禽流感）的不对称正向影响，整体概率略高于50%。
  - 更新触发器：2027年Q1-Q2的全国鸡肉批发均价实际走势，以及农业农村部发布的2026年全年产能去化确认报告。

## 关键未知项
- 2026年全年的实际平均鸡肉价格水平（作为分母，若2026年价格极低，2027年即使持平也可能被视为‘高于’，但合约比较的是绝对值）
- 2027年具体的父母代种鸡存栏量数据（需等到2027年底或2028年初才能确认）
- 2027年国际地缘政治对饲料进口成本的具体影响幅度
- 2027年国内餐饮行业复苏的具体程度

## 模糊点与假设
- 模糊点：需明确‘鸡肉’的具体统计口径，建议采用农业农村部发布的‘鸡肉’大类平均价
- 假设：假设用户关心的‘鸡肉价格’主要指市场流通的批发价格，而非养殖端成本或零售端最终售价

## 校准信息
- calibration_mode：cold_start_conservative_shrinkage
- temperature：1.160
- domain_history_n：0
- domain_avg_brier：None

## 结论
当前给出的概率是 **48.0%**。这个数字由 base rate、证据 log-odds、Bayesian causal graph / Monte Carlo、多 Agent panel 和本地校准共同计算得到。



版本：LLM 结构化先验 + bayesian_causal_graph_logistic_cpd_monte_carlo
模型：qwen/qwen3.6-27b
问题：2028年后北京房价会不会小幅上涨？
结果：
预测类型：multi_contract_portfolio原始问题：2028年后北京房价会不会小幅上涨？综合概率：46.4%粗略区间：21.7% - 73.1%问题类型：cloud_judgment语义坍缩风险：high推荐模式：multi_contract_portfolio

原始语义

用户希望了解在2028年之后的时间段内，北京住宅房地产市场价格是否会出现温和的、非剧烈的正向增长趋势，且这种增长具有真实购买力支撑而非单纯通胀或统计噪音。

语义坍缩说明：将‘2028年后’这一长期、开放的时间范围坍缩为‘2029年同比2028年’的单年短期波动；将‘小幅上涨’这一主观、多维的感知坍缩为固定的‘0-5%名义涨幅’，忽略了通胀背景下的实际购买力变化、市场流动性健康度以及区域分化带来的结构性风险。单一指标无法捕捉‘温和且可持续’的市场状态。

如果强行单指标化，会丢失这些维度：

实际购买力变化（剔除通胀后的真实增值）

市场流动性与成交量支撑（排除有价无市的虚假上涨）

区域分化程度（核心区与郊区的结构性差异）

时间维度的长期趋势（2028年后的持续状态而非单年快照）

政策与宏观环境的稳定性（上涨的可持续性）

维度展开

名义价格变动幅度 | weight=0.40 | measurability=0.95 | 覆盖‘上涨’的方向性和‘小幅’的数值定义。这是用户最核心的关注点，即价格是否正向增长且幅度有限。

实际购买力变化（剔除通胀） | weight=0.25 | measurability=0.90 | 覆盖‘上涨’的真实经济含义。如果名义价格上涨但通胀更高，实际购买力下降，这不符合‘变好’或‘温和上涨’的直觉预期。

市场流动性与成交量 | weight=0.15 | measurability=0.95 | 覆盖‘上涨’的健康程度。有价无市的上涨（成交量极低）与有量有价的上涨（成交量活跃）意义不同。‘小幅上涨’通常暗示市场平稳而非僵死。

区域分化程度 | weight=0.10 | measurability=0.85 | 覆盖‘北京房价’的空间异质性。‘小幅上涨’是全市普遍现象，还是仅核心区上涨、郊区下跌后的平均结果？

政策与预期稳定性 | weight=0.10 | measurability=0.70 | 覆盖‘2028年后’这一时间背景下的宏观环境。房价走势受政策影响极大，‘小幅上涨’往往对应政策宽松但不过热的状态。

Contract Portfolio 结果

名义价格变动幅度 | P=37.5% | weight=0.466 | proxy=2029年北京全市二手房成交均价同比2028年的增长率 | proxy_risk=medium

预测题：2029年北京全市二手房成交均价同比2028年是否上涨且涨幅在0%至5%之间？

实际购买力变化（剔除通胀） | P=46.5% | weight=0.347 | proxy=2029年北京房价名义同比涨幅减去北京CPI同比涨幅后的差值 | proxy_risk=medium

预测题：2029年北京房价实际涨幅（名义涨幅减去CPI涨幅）是否在0%至3%之间？

市场流动性与成交量 | P=68.3% | weight=0.186 | proxy=2029年北京二手房月均成交量同比2028年的变化率 | proxy_risk=low

预测题：2029年北京二手房月均成交量是否高于2028年，且价格未出现大幅下跌（跌幅<5%）？

子预测摘要

名义价格变动幅度：37.5% 区间 11.9% - 72.8%

contract：2029年北京全市二手房成交均价同比2028年是否上涨且涨幅在0%至5%之间？

base=35.0%, evidence=31.5%, causal=40.3%, panel=37.4%

causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=6, edges=0, causal_interval=10.8%-79.1%

top causal sensitivity：

存量房供给压力: do_true=29.9%, do_false=56.8%, swing=0.268

人口净流入与刚需支撑: do_true=48.5%, do_false=26.4%, swing=0.221

货币政策与利率环境: do_true=45.2%, do_false=27.6%, swing=0.176

实际购买力变化（剔除通胀）：46.5% 区间 16.9% - 78.8%

contract：2029年北京房价实际涨幅（名义涨幅减去CPI涨幅）是否在0%至3%之间？

base=45.0%, evidence=39.0%, causal=53.4%, panel=48.0%

causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=1, causal_interval=21.5%-83.8%

top causal sensitivity：

货币政策宽松程度: do_true=61.0%, do_false=34.0%, swing=0.270

房地产政策稳定性: do_true=60.1%, do_false=40.0%, swing=0.201

北京人口净流入与结构: do_true=62.5%, do_false=46.6%, swing=0.160

市场流动性与成交量：68.3% 区间 34.1% - 90.0%

contract：2029年北京二手房月均成交量是否高于2028年，且价格未出现大幅下跌（跌幅<5%）？

base=65.0%, evidence=71.5%, causal=79.0%, panel=63.8%

causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=6, edges=2, causal_interval=55.4%-92.2%

top causal sensitivity：

货币政策宽松程度: do_true=82.3%, do_false=63.2%, swing=0.192

政策调控稳定性: do_true=81.7%, do_false=70.3%, swing=0.114

法拍房与急售房源冲击: do_true=71.8%, do_false=82.1%, swing=0.102

聚合方法

使用 weighted logit portfolio，不是简单平均概率。

权重由 semantic_coverage_weight、measurability、user_intent_preservation_score、proxy_risk 共同决定。

子预测 logit 分歧：0.537

portfolio logit sigma：1.142

结论

对原始云状问题，当前综合概率是 46.4%。


问题：2030年中美会不会发生军事冲突？
结果：
**预测类型**：multi_contract_portfolio
**原始问题**：2030年中美会不会发生军事冲突？
**综合概率**：9.1%
**粗略区间**：5.9% - 13.8%
**问题类型**：explicit_binary
**语义坍缩风险**：low
**推荐模式**：multi_contract_portfolio

## 原始语义
用户旨在评估在2030年12月31日之前，中华人民共和国与美利坚合众国之间是否会发生任何形式的、可被国际公认定义的直接军事对抗、武装冲突或重大代理人战争事件。

语义坍缩说明：分解避免了将‘军事冲突’简化为单一指标（如GDP或军费），而是涵盖了直接、间接和新维度冲突。

如果强行单指标化，会丢失这些维度：
- 代理人战争。
- 准军事力量冲突。
- 网络/太空物理攻击。

## 维度展开
- **Direct Military Engagement (Kinetic & Paramilitary)** | weight=0.60 | measurability=0.90 | 中美双方军事或准军事力量之间的直接武力接触，包括正规军交火、导弹发射、舰机碰撞导致的战斗行为，以及海警/民兵在争议区域的致命武力使用。
- **Proxy Military Conflict** | weight=0.25 | measurability=0.70 | 中美在第三国或地区支持对立双方，并导致双方军事力量（或由其直接指挥/武装的力量）发生直接战斗或重大军事对抗。
- **Cyber/Space Kinetic Equivalent** | weight=0.15 | measurability=0.40 | 网络或太空攻击造成物理破坏、人员伤亡或关键基础设施瘫痪，且被归因于对方，并引发军事层面的回应或被视为战争行为。

## Contract Portfolio 结果
- **Direct Military Engagement** | P=9.5% | weight=0.847 | proxy=官方确认的军事人员伤亡或动能武器发射。 | proxy_risk=low
  - 预测题：在2026年6月2日至2030年12月31日期间，中美双方是否会发生直接军事交战（包括正规军及执行军事任务的准军事力量）？
- **Proxy Military Conflict** | P=6.9% | weight=0.141 | proxy=中美军队在第三国的直接交战记录。 | proxy_risk=medium
  - 预测题：在2026年6月2日至2030年12月31日期间，中美是否在第三国发生直接军事对抗或重大代理人战争？
- **Cyber/Space Kinetic Equivalent** | P=7.6% | weight=0.013 | proxy=造成物理后果的归因网络/太空攻击。 | proxy_risk=high
  - 预测题：在2026年6月2日至2030年12月31日期间，中美是否发生造成物理破坏或人员伤亡的网络/太空攻击，并被认定为军事冲突？

## 子预测摘要
- **Direct Military Engagement**：9.5% 区间 1.5% - 42.2%
  - contract：在2026年6月2日至2030年12月31日期间，中美双方是否会发生直接军事交战（包括正规军及执行军事任务的准军事力量）？
  - base=5.0%, evidence=7.0%, causal=5.5%, panel=9.3%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=6, edges=0, causal_interval=1.6%-15.8%
  - top causal sensitivity：
    - Taiwan Crisis Escalation: do_true=11.9%, do_false=3.4%, swing=0.085
    - Accidental Skirmish in South China Sea: do_true=10.4%, do_false=4.5%, swing=0.059
    - Crisis Communication Mechanisms: do_true=4.5%, do_false=7.1%, swing=0.027
- **Proxy Military Conflict**：6.9% 区间 1.1% - 32.1%
  - contract：在2026年6月2日至2030年12月31日期间，中美是否在第三国发生直接军事对抗或重大代理人战争？
  - base=5.0%, evidence=3.3%, causal=1.9%, panel=9.9%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=0, causal_interval=1.0%-4.9%
  - top causal sensitivity：
    - Escalation in South China Sea: do_true=4.1%, do_false=1.5%, swing=0.026
    - Effectiveness of Crisis Communication Channels: do_true=1.4%, do_false=3.0%, swing=0.016
    - Conflict in Middle East or Africa involving both powers: do_true=3.0%, do_false=1.7%, swing=0.013
- **Cyber/Space Kinetic Equivalent**：7.6% 区间 1.1% - 37.8%
  - contract：在2026年6月2日至2030年12月31日期间，中美是否发生造成物理破坏或人员伤亡的网络/太空攻击，并被认定为军事冲突？
  - base=5.0%, evidence=2.8%, causal=3.1%, panel=7.2%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=1, causal_interval=1.0%-11.7%
  - top causal sensitivity：
    - 常规军事冲突升级: do_true=8.2%, do_false=2.3%, swing=0.060
    - 太空军事化与反卫星武器部署: do_true=6.6%, do_false=1.7%, swing=0.049
    - 危机管控机制的有效性: do_true=2.1%, do_false=4.5%, swing=0.023

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- 权重由 semantic_coverage_weight、measurability、user_intent_preservation_score、proxy_risk 共同决定。
- 子预测 logit 分歧：0.149
- portfolio logit sigma：0.467

## 结论
对原始云状问题，当前综合概率是 **9.1%**。


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