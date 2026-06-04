from typing import Any, Dict, List, Tuple, Optional
from openai import OpenAI

from app.config import CONFIG
# =============================================================================
# 1. LLM Client
# =============================================================================

client = OpenAI(
    api_key=CONFIG["api_key"],
    base_url=CONFIG["base_url"],
)


def llm_qwen(
    prompt: str,
    config: Dict[str, Any] = CONFIG,
    temperature: float = 0.30,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    system: Optional[str] = None,
) -> str:
    max_tokens = max_tokens or config["llm"]["max_tokens"]
    top_p = top_p if top_p is not None else config["llm"]["top_p"]
    system = system or config["llm"]["system"]

    chat_response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    return chat_response.choices[0].message.content or ""

