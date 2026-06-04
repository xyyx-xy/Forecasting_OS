=================================================
版本：LLM 结构化先验 + bayesian_causal_graph_logistic_cpd_monte_carlo
35b-a3
**预测类型**：multi_contract_portfolio
**原始问题**：2028年后北京房价会不会小幅上涨？
**综合概率**：50.3%
**粗略区间**：26.3% - 74.1%
**问题类型**：explicit_binary
**语义坍缩风险**：high
**推荐模式**：multi_contract_portfolio

## 原始语义
用户希望评估在2028年之后的时间段内，北京地区的房地产市场价格是否会出现幅度有限的正向变动（名义或实际价格）。

语义坍缩说明：原始拆解中存在严重的语义坍缩风险。首先，将‘驱动因素’（供需、政策、收入、情绪）直接作为‘结果’（房价涨跌）的结算合约，属于典型的‘意外偷换问题’（Accidental Substitution）。驱动因素的变化并不等价于价格结果，且存在方向冲突（如政策松绑可能导致暴涨而非小幅上涨）。其次，‘2028年后’这一模糊时间窗口被武断地坍缩为‘2029年全年’，忽略了2030年及以后的可能性，导致时间语义丢失。最后，‘北京房价’这一多维概念被坍缩为‘全市二手房均价’，忽略了核心区与郊区、新房与二手房、名义与实际购买力等关键维度，极易因成交结构偏差（如远郊成交占比增加拉低均价）导致结算结果与用户真实意图（通常指核心资产价值或普遍体感）背离。

如果强行单指标化，会丢失这些维度：
- 区域分化维度：核心区（海淀、西城）与远郊区（平谷、密云）的房价逻辑完全独立，全市均价掩盖了结构性分化。
- 实际购买力维度：名义价格上涨若由通胀驱动，实际财富效应可能为负，违背用户隐含的‘价值提升’预期。
- 新房限价扭曲维度：北京新房存在严格限价，其价格不能反映真实市场供需，仅看二手房可能忽略新房市场的真实热度或冷遇。
- 持有成本与预期维度：房产税预期、物业成本等长期持有成本对房价预期的压制作用未纳入结算。
- 时间窗口模糊性：‘2028年后’可能涵盖2029-2030甚至更久，单一时间点结算无法捕捉长期趋势。

## 维度展开
- **名义价格中枢趋势（全市）** | weight=0.44 | measurability=0.95 | 直接对应“房价上涨”的字面含义，即货币计价的市场均价是否上升。这是最核心的语义覆盖，但需排除通胀因素后的实际购买力变化。
- **价格波动幅度界定（“小幅”判定）** | weight=0.22 | measurability=0.90 | 对应“小幅”这一限定词。需要界定涨幅是否处于温和区间，而非暴涨或暴跌。这决定了预测结果的定性分类。
- **区域分化：核心区 vs 郊区** | weight=0.22 | measurability=0.85 | 北京市场高度分化，全市均价可能被结构性变化扭曲。需分别评估核心区（海淀、西城等）和郊区（房山、大兴等）的价格走势，以捕捉真实的市场体感。
- **实际购买力与通胀调整** | weight=0.11 | measurability=0.80 | 名义价格上涨若由通胀驱动，实际购买力可能下降。用户隐含的“房价上涨”通常指实际价值或相对购买力的提升。

## Contract Portfolio 结果
- **名义价格中枢趋势（全市）** | P=54.3% | weight=0.372 | proxy=北京市住建委发布的二手房网签均价同比增速 | proxy_risk=medium
  - 预测题：到2029年12月31日，北京全市二手房成交均价是否高于2028年12月31日的水平？
- **价格波动幅度界定（“小幅”判定）** | P=49.1% | weight=0.297 | proxy=北京二手房成交均价年度涨幅是否落在0%-5%区间 | proxy_risk=low
  - 预测题：到2029年12月31日，北京全市二手房成交均价的年度涨幅是否落在0%至5%的区间内？
- **区域分化：核心区** | P=57.9% | weight=0.145 | proxy=北京核心区二手房中位数价格同比增速 | proxy_risk=medium
  - 预测题：到2029年12月31日，北京核心区（东城、西城、海淀、朝阳）二手房中位数价格是否高于2028年12月31日的水平？
- **区域分化：郊区** | P=36.3% | weight=0.132 | proxy=北京远郊区二手房中位数价格同比增速 | proxy_risk=medium
  - 预测题：到2029年12月31日，北京远郊区（房山、大兴、通州部分等）二手房中位数价格是否高于2028年12月31日的水平？
- **实际购买力与通胀调整** | P=43.8% | weight=0.055 | proxy=实际房价指数（扣除CPI） | proxy_risk=medium
  - 预测题：到2029年12月31日，北京全市二手房中位数价格（扣除同期CPI）是否高于2028年12月31日的水平？

## 子预测摘要
- **名义价格中枢趋势（全市）**：54.3% 区间 20.1% - 84.9%
  - contract：到2029年12月31日，北京全市二手房成交均价是否高于2028年12月31日的水平？
  - base=55.0%, evidence=54.9%, causal=57.7%, panel=51.3%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=4, causal_interval=36.5%-77.8%
  - top causal sensitivity：
    - 郊区库存压力与成交结构稀释: do_true=49.7%, do_false=69.1%, swing=0.194
    - 宏观流动性与通胀传导: do_true=62.0%, do_false=46.2%, swing=0.158
    - 核心区土地稀缺性与改善型需求: do_true=62.1%, do_false=48.7%, swing=0.134
- **价格波动幅度界定（“小幅”判定）**：49.1% 区间 19.0% - 79.9%
  - contract：到2029年12月31日，北京全市二手房成交均价的年度涨幅是否落在0%至5%的区间内？
  - base=45.0%, evidence=48.9%, causal=54.9%, panel=47.5%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=3, causal_interval=39.6%-64.1%
  - top causal sensitivity：
    - 宏观政策托底力度: do_true=56.7%, do_false=42.5%, swing=0.142
    - 居民收入与预期修复: do_true=58.4%, do_false=48.8%, swing=0.096
    - 通胀传导效应: do_true=57.0%, do_false=50.2%, swing=0.068
- **区域分化：核心区**：57.9% 区间 24.4% - 85.4%
  - contract：到2029年12月31日，北京核心区（东城、西城、海淀、朝阳）二手房中位数价格是否高于2028年12月31日的水平？
  - base=55.0%, evidence=58.8%, causal=64.6%, panel=58.8%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=2, causal_interval=49.9%-75.3%
  - top causal sensitivity：
    - 货币宽松与通胀传导: do_true=68.0%, do_false=55.8%, swing=0.122
    - 核心区土地供应稀缺性: do_true=65.9%, do_false=54.9%, swing=0.109
    - 人口结构与购买力约束: do_true=60.0%, do_false=67.6%, swing=0.076
- **区域分化：郊区**：36.3% 区间 9.3% - 76.0%
  - contract：到2029年12月31日，北京远郊区（房山、大兴、通州部分等）二手房中位数价格是否高于2028年12月31日的水平？
  - base=35.0%, evidence=30.9%, causal=32.4%, panel=39.4%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=2, causal_interval=15.6%-57.2%
  - top causal sensitivity：
    - 远郊区库存去化压力: do_true=25.4%, do_false=43.6%, swing=0.182
    - 人口与产业导入实效: do_true=41.1%, do_false=28.2%, swing=0.129
    - 宏观政策宽松与利率下行: do_true=35.8%, do_false=24.5%, swing=0.112
- **实际购买力与通胀调整**：43.8% 区间 14.3% - 78.4%
  - contract：到2029年12月31日，北京全市二手房中位数价格（扣除同期CPI）是否高于2028年12月31日的水平？
  - base=45.0%, evidence=37.6%, causal=43.7%, panel=45.2%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=4, causal_interval=24.5%-65.9%
  - top causal sensitivity：
    - 郊区供应过剩与价格下行压力: do_true=37.7%, do_false=55.8%, swing=0.181
    - 核心资产稀缺性与改善型需求支撑: do_true=47.4%, do_false=36.1%, swing=0.113
    - 宏观通胀水平（CPI）: do_true=47.5%, do_false=37.8%, swing=0.097

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- 权重由 semantic_coverage_weight、measurability、user_intent_preservation_score、proxy_risk 共同决定。
- 子预测 logit 分歧：0.312
- portfolio logit sigma：1.040

## 结论
对原始云状问题，当前综合概率是 **50.3%**。



**预测类型**：multi_contract_portfolio
**原始问题**：2027年中国ai创业公司的融资环境会不会比2026年更好？
**综合概率**：46.3%
**粗略区间**：25.4% - 68.7%
**问题类型**：cloud_judgment
**语义坍缩风险**：high
**推荐模式**：multi_contract_portfolio

## 原始语义
用户希望评估2027年中国AI创业生态在资本获取的难易程度、充裕度、估值理性及政策友好度上，相较于2026年是否呈现整体改善趋势。

语义坍缩说明：原始问题'融资环境更好'是一个典型的多维云状判断，涉及资金总量、可得性（早期vs后期）、估值理性、政策结构（国资vs市场化）、退出通道及资本信心等多个相互冲突或独立的维度。若仅使用单一指标（如融资总额、IPO过会率或国资占比）进行结算，将导致严重的语义坍缩。例如，融资总额增加可能掩盖长尾公司融资难（头部效应）；国资占比上升可能伴随决策僵化和市场化活力下降；IPO过会率仅反映单一退出渠道。这些单一指标均存在方向冲突风险，无法等价代表整体'环境'的改善。

如果强行单指标化，会丢失这些维度：
- 早期/长尾初创公司的实际融资可得性与成功率
- 估值泡沫程度与条款严苛度（创业者实际体验）
- 资本结构的多元化与市场化活力（国资主导的负面外部性）
- 非IPO退出渠道（并购、S基金）的活跃度
- LP/GP层面的资本信心源头

## 维度展开
- **资本供给总量与活跃度** | weight=0.20 | measurability=0.90 | 衡量2027年进入中国AI初创领域的资金绝对规模及交易频率，反映市场的整体充裕度。
- **早期融资可得性与普惠性** | weight=0.25 | measurability=0.50 | 衡量初创公司（特别是Seed/A轮早期项目）获得融资的难易程度，包括从接触投资人到最终交割的时间周期及被拒率。
- **估值理性与条款健康度** | weight=0.20 | measurability=0.70 | 评估融资价格是否反映真实商业价值，还是存在非理性溢价，以及融资条款对创业者的友好程度。
- **资金方结构与政策导向匹配度** | weight=0.15 | measurability=0.60 | 分析资金来源中政府引导基金、国资与市场化VC/PE的比例，以及政策鼓励方向与资本投向的一致性。
- **退出通道预期与流动性** | weight=0.10 | measurability=0.60 | 评估IPO、并购等退出渠道的畅通程度，这直接决定资本进入一级市场的意愿。
- **地缘政治与合规风险溢价** | weight=0.10 | measurability=0.40 | 评估国际制裁、出口管制、数据安全法规等外部约束对融资环境的负面影响程度。

## Contract Portfolio 结果
- **估值理性与条款健康度** | P=46.8% | weight=0.387 | proxy=2027年AI领域Down-round（估值下调）案例数占所有融资案例的比例 | proxy_risk=low
  - 预测题：2027年AI领域Down-round（估值下调）案例数占所有融资案例的比例是否低于2026年？
- **退出通道预期与流动性** | P=47.0% | weight=0.278 | proxy=2027年AI公司IPO过会率同比2026年变化 | proxy_risk=low
  - 预测题：2027年中国AI公司IPO过会率是否高于2026年？
- **早期融资可得性与普惠性** | P=47.3% | weight=0.171 | proxy=2027年AI初创公司从首次路演到获得TS（投资意向书）的平均天数变化 | proxy_risk=medium
  - 预测题：2027年AI初创公司从首次路演到获得TS（投资意向书）的平均天数是否短于2026年？
- **资金方结构与政策导向匹配度** | P=43.1% | weight=0.163 | proxy=2027年市场化VC新设AI主题基金规模同比2026年变化 | proxy_risk=medium
  - 预测题：2027年AI融资中市场化VC新设基金规模是否高于2026年？

## 子预测摘要
- **早期融资可得性与普惠性**：47.3% 区间 14.2% - 83.0%
  - contract：2027年AI初创公司从首次路演到获得TS（投资意向书）的平均天数是否短于2026年？
  - base=45.0%, evidence=49.7%, causal=52.2%, panel=40.4%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=1, causal_interval=27.7%-71.5%
  - top causal sensitivity：
    - 国资主导下的决策流程僵化: do_true=57.2%, do_false=34.5%, swing=0.227
    - 地缘政治与合规风险溢价: do_true=57.3%, do_false=44.0%, swing=0.133
    - AI技术成熟度与商业化清晰度: do_true=47.1%, do_false=59.3%, swing=0.122
- **估值理性与条款健康度**：46.8% 区间 14.2% - 82.4%
  - contract：2027年AI领域Down-round（估值下调）案例数占所有融资案例的比例是否低于2026年？
  - base=45.0%, evidence=53.0%, causal=40.0%, panel=47.0%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=0, causal_interval=25.5%-54.8%
  - top causal sensitivity：
    - 地缘政治制裁升级: do_true=47.6%, do_false=36.3%, swing=0.114
    - AI技术商业化落地速度超预期: do_true=36.1%, do_false=45.5%, swing=0.095
    - 宏观流动性持续宽松: do_true=36.8%, do_false=45.4%, swing=0.085
- **退出通道预期与流动性**：47.0% 区间 15.5% - 81.1%
  - contract：2027年中国AI公司IPO过会率是否高于2026年？
  - base=45.0%, evidence=44.2%, causal=48.2%, panel=50.0%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=4, edges=2, causal_interval=26.8%-67.1%
  - top causal sensitivity：
    - IPO政策宽松周期: do_true=55.2%, do_false=36.4%, swing=0.188
    - AI行业合规与盈利门槛: do_true=39.4%, do_false=53.5%, swing=0.141
    - 二级市场估值支撑: do_true=51.7%, do_false=44.3%, swing=0.074
- **资金方结构与政策导向匹配度**：43.1% 区间 14.5% - 77.2%
  - contract：2027年AI融资中市场化VC新设基金规模是否高于2026年？
  - base=45.0%, evidence=33.3%, causal=46.1%, panel=45.2%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=2, causal_interval=25.3%-69.8%
  - top causal sensitivity：
    - 国资与市场化资本的替代/挤出效应: do_true=38.3%, do_false=56.4%, swing=0.181
    - AI商业化闭环的验证程度: do_true=51.9%, do_false=39.9%, swing=0.119
    - 宏观流动性与LP出资意愿: do_true=50.1%, do_false=39.5%, swing=0.106

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- 权重由 semantic_coverage_weight、measurability、user_intent_preservation_score、proxy_risk 共同决定。
- 子预测 logit 分歧：0.070
- portfolio logit sigma：0.931

## 结论
对原始云状问题，当前综合概率是 **46.3%**。




**预测类型**：multi_contract_portfolio
**原始问题**：预测万物的世界模型在2027年是否会实现
**综合概率**：14.0%
**粗略区间**：4.4% - 36.4%
**问题类型**：cloud_judgment
**语义坍缩风险**：high
**推荐模式**：multi_contract_portfolio

## 原始语义
用户希望评估在2027年6月3日之前，AI系统是否具备了对物理世界和数字世界中所有实体及其相互关系的统一、高精度且通用的建模与推理能力，即是否达到了具备因果理解、跨模态泛化和鲁棒交互的‘通用世界模型’状态。

语义坍缩说明：原始问题'万物世界模型'是一个高度多维、云状且缺乏明确验收标准的评价性问题。原始拆解方案虽然识别了类型，但在合约设计中存在严重的语义坍缩风险：1. 将'世界模型'的技术本质（内部表征与因果推理）偷换为工程落地指标（如机器人商业化部署、边缘计算延迟）；2. 将'万物'的完整性简化为单一维度的数字知识检索或基准测试得分，忽略了物理规律、社会关系和动态系统的建模；3. 使用了带有商业色彩或特定硬件限制的指标（如'大规模部署'、'100ms延迟'），这些是约束条件而非智能实现的定义。这种拆解方式极易导致预测者关注容易量化的代理指标（如论文数量、基准分数），而忽略了对'通用智能'和'世界理解'本质的评估，从而产生方向冲突或伪精确。

如果强行单指标化，会丢失这些维度：
- 内部表征的一致性：模型是否在内部构建了一个连贯的、符合物理和社会规律的世界表示
- 因果推理与反事实思维能力：模型能否理解因果关系并进行反事实推理，而非仅拟合统计关联
- 跨模态深层语义对齐：模型是否真正理解不同模态（视觉、语言、触觉等）之间的深层语义联系
- 动态系统长期预测能力：模型对复杂动态系统（如气候、经济）的长期、稳定预测能力
- 物理世界交互的泛化能力：在非结构化环境中的零样本泛化和Sim2Real迁移能力
- 鲁棒性与安全性：模型在面对对抗性攻击、偏见和有害内容时的表现

## 维度展开
- **物理世界交互与具身智能能力** | weight=0.26 | measurability=0.60 | 覆盖“万物”中的物理实体部分，以及“世界模型”在真实物理环境中的因果推理和操作能力。这是区分“数据拟合”与“世界理解”的核心维度。
- **跨模态与跨领域泛化能力** | weight=0.21 | measurability=0.80 | 覆盖“世界模型”的通用性，即模型是否能将不同模态（文本、图像、视频、传感器数据）和不同领域（科学、工程、艺术）的知识进行统一表征和推理。
- **因果推理与反事实思维能力** | weight=0.26 | measurability=0.50 | 覆盖“世界模型”的核心认知机制，即模型是否具备理解因果关系、进行反事实推理和预测干预效果的能力。
- **数字世界与知识图谱的完整性** | weight=0.16 | measurability=0.90 | 覆盖“万物”中的数字实体部分，包括互联网上的文本、代码、数据库、社交关系等结构化与非结构化信息。
- **鲁棒性、安全性与伦理对齐** | weight=0.11 | measurability=0.70 | 覆盖“实现”的社会接受度和可持续性，即模型在面对对抗性攻击、偏见、有害内容时的表现，以及是否符合人类价值观。

## Contract Portfolio 结果
- **数字世界与知识图谱的完整性** | P=37.5% | weight=0.257 | proxy=大规模知识库事实性检索准确率及幻觉率（Hallucination Rate） | proxy_risk=low
  - 预测题：到2027年6月3日，是否出现AI模型在回答涉及最新、冷门事实的问题时，幻觉率低于5%，且能自动构建和更新大规模动态知识图谱？
- **跨模态与跨领域泛化能力** | P=6.8% | weight=0.235 | proxy=在未见过的学科或任务上的Few-shot/Zero-shot学习性能保持率（相对于该领域专家基线） | proxy_risk=medium
  - 预测题：到2027年6月3日，是否出现单一AI模型在多个完全无关的学科领域（如量子物理、分子生物学、高级编程）的零样本或极少样本任务中，同时达到人类专家水平？
- **物理世界交互与具身智能能力** | P=6.6% | weight=0.222 | proxy=在标准具身智能基准测试（如ALFRED, Habitat, BridgeData V2）中的零样本/少样本任务成功率 | proxy_risk=medium
  - 预测题：到2027年6月3日，是否已有具身智能系统（机器人或仿真代理）在非结构化物理环境中，实现零样本任务成功率超过80%且故障率低于人类平均水平的大规模部署或高保真仿真验证？
- **因果推理与反事实思维能力** | P=15.8% | weight=0.213 | proxy=在因果推断基准测试（如CausalBench）及反事实问题回答中的准确性 | proxy_risk=medium
  - 预测题：到2027年6月3日，是否出现AI模型在未见过的复杂动态系统（如宏观经济、流行病传播）中，仅基于观测数据自动学习因果图，并准确预测新干预措施的效果，误差范围在可接受范围内？
- **鲁棒性、安全性与伦理对齐** | P=16.5% | weight=0.073 | proxy=对抗性攻击下的性能下降幅度及新型攻击的自动检测率 | proxy_risk=medium
  - 预测题：到2027年6月3日，是否出现能够自动检测和缓解新型对抗性攻击的通用安全框架，且模型在跨文化场景中表现出一致的伦理行为？

## 子预测摘要
- **物理世界交互与具身智能能力**：6.6% 区间 1.0% - 32.3%
  - contract：到2027年6月3日，是否已有具身智能系统（机器人或仿真代理）在非结构化物理环境中，实现零样本任务成功率超过80%且故障率低于人类平均水平的大规模部署或高保真仿真验证？
  - base=5.0%, evidence=2.3%, causal=2.4%, panel=8.9%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=4, causal_interval=1.0%-6.1%
  - top causal sensitivity：
    - 长尾场景（Corner Cases）的覆盖度: do_true=8.1%, do_false=1.9%, swing=0.062
    - Sim2Real迁移的保真度突破: do_true=3.9%, do_false=1.8%, swing=0.022
    - 硬件执行器与传感器的成熟度: do_true=3.8%, do_false=2.1%, swing=0.018
- **跨模态与跨领域泛化能力**：6.8% 区间 1.3% - 29.2%
  - contract：到2027年6月3日，是否出现单一AI模型在多个完全无关的学科领域（如量子物理、分子生物学、高级编程）的零样本或极少样本任务中，同时达到人类专家水平？
  - base=5.0%, evidence=1.5%, causal=6.0%, panel=9.3%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=3, causal_interval=1.0%-19.2%
  - top causal sensitivity：
    - 基础模型架构的通用表征能力: do_true=11.5%, do_false=3.9%, swing=0.076
    - 推理与验证机制的引入: do_true=9.0%, do_false=2.1%, swing=0.069
    - 计算资源与训练范式的突破: do_true=10.5%, do_false=4.2%, swing=0.063
- **因果推理与反事实思维能力**：15.8% 区间 3.0% - 53.4%
  - contract：到2027年6月3日，是否出现AI模型在未见过的复杂动态系统（如宏观经济、流行病传播）中，仅基于观测数据自动学习因果图，并准确预测新干预措施的效果，误差范围在可接受范围内？
  - base=15.0%, evidence=5.0%, causal=13.3%, panel=14.6%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=1, causal_interval=4.4%-27.7%
  - top causal sensitivity：
    - 验证基准的缺失: do_true=9.7%, do_false=21.5%, swing=0.117
    - 算法架构突破: do_true=19.7%, do_false=10.6%, swing=0.091
    - 数据质量与可用性: do_true=16.1%, do_false=10.0%, swing=0.061
- **数字世界与知识图谱的完整性**：37.5% 区间 11.0% - 74.5%
  - contract：到2027年6月3日，是否出现AI模型在回答涉及最新、冷门事实的问题时，幻觉率低于5%，且能自动构建和更新大规模动态知识图谱？
  - base=35.0%, evidence=29.1%, causal=42.6%, panel=37.4%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=4, causal_interval=8.6%-80.9%
  - top causal sensitivity：
    - 检索增强生成（RAG）与实时搜索引擎的集成成熟度: do_true=48.9%, do_false=22.7%, swing=0.262
    - 自动化信息抽取与知识图谱构建算法的鲁棒性: do_true=56.6%, do_false=30.7%, swing=0.259
    - 冷门事实的覆盖度与长尾数据获取能力: do_true=53.1%, do_false=35.8%, swing=0.173
- **鲁棒性、安全性与伦理对齐**：16.5% 区间 3.7% - 50.8%
  - contract：到2027年6月3日，是否出现能够自动检测和缓解新型对抗性攻击的通用安全框架，且模型在跨文化场景中表现出一致的伦理行为？
  - base=15.0%, evidence=4.6%, causal=26.5%, panel=14.6%
  - causal_graph：method=bayesian_causal_graph_logistic_cpd_monte_carlo, samples=12000, nodes=5, edges=3, causal_interval=2.0%-67.4%
  - top causal sensitivity：
    - 新型对抗性攻击的演化速度: do_true=18.1%, do_false=52.7%, swing=0.347
    - 跨文化伦理标准的统一性: do_true=4.2%, do_false=30.4%, swing=0.261
    - 自动化安全框架的技术成熟度: do_true=36.2%, do_false=22.5%, swing=0.138

## 聚合方法
- 使用 weighted logit portfolio，不是简单平均概率。
- 权重由 semantic_coverage_weight、measurability、user_intent_preservation_score、proxy_risk 共同决定。
- 子预测 logit 分歧：0.790
- portfolio logit sigma：1.255

## 结论
对原始云状问题，当前综合概率是 **14.0%**。


=================================================
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