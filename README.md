利用Tetlock 的超预测思想，来开发LLM 组织预测流程，概率系统负责计算的大型Agent系统
conda create -n forecasting_os python=3.12
conda activate forecasting_os
pip install -r requirements.txt

```flowchart TD
    A["用户输入问题"] --> B["Cloud-to-Contract 拆解"]
    B --> C{"问题类型"}

    C -->|"明确二元问题"| D["生成单个预测合约"]
    C -->|"云状问题"| E["生成多个子合约 portfolio"]

    D --> F["单合约预测"]
    E --> G["逐个子合约预测"]

    F --> H["概率引擎"]
    G --> H

    H --> I["base rate<br/>历史基准率"]
    H --> J["evidence update<br/>证据更新"]
    H --> K["panel probability<br/>多Agent判断"]
    H --> L["mechanism chain graph<br/>机制链因子图"]

    I --> M["概率融合"]
    J --> M
    K --> M
    L --> M

    M --> N["最终概率"]
    N --> O["Markdown 报告"]
    O --> P["本地 JSON 保存"]
```