"""统一 LLM 客户端（DeepSeek / OpenAI 兼容）

公共底座：诊断、原型、飞轮等模块统一从这里发起模型调用，不再各自 `from openai import OpenAI`。
- 按需懒加载客户端，不污染启动
- 未配置 key / 调用失败 → 抛 LLMError，由调用方降级
- `chat_json` 强制结构化 JSON 输出
"""

import json
import re
import time
from typing import Dict, Optional

from core.config.settings import get_settings
from core.logging.logger import get_logger

logger = get_logger()


class LLMError(RuntimeError):
    """LLM 调用失败（未配置 key / 网络 / 返回异常）"""


# ---------- 计费打点（喂给 monitor 成本看板） ----------

_USAGE = {
    "calls": 0,
    "success_calls": 0,
    "error_calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "total_latency_ms": 0.0,
    "by_model": {},  # model -> {calls, input_tokens, output_tokens, latency_ms_sum}
}


def _record_usage(model: str, input_tokens: int, output_tokens: int, latency_ms: float, success: bool):
    _USAGE["calls"] += 1
    _USAGE["success_calls"] += 1 if success else 0
    _USAGE["error_calls"] += 1 if not success else 0
    _USAGE["input_tokens"] += input_tokens
    _USAGE["output_tokens"] += output_tokens
    _USAGE["total_latency_ms"] += latency_ms
    m = _USAGE["by_model"].setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms_sum": 0.0})
    m["calls"] += 1
    m["input_tokens"] += input_tokens
    m["output_tokens"] += output_tokens
    m["latency_ms_sum"] += latency_ms


def get_llm_usage() -> Dict:
    """返回累计 LLM 使用统计（monitor 成本看板的数据源）"""
    by_model = {m: dict(v) for m, v in _USAGE["by_model"].items()}
    for v in by_model.values():
        v["avg_latency_ms"] = round(v["latency_ms_sum"] / v["calls"], 1) if v["calls"] else 0
        v.pop("latency_ms_sum", None)
    return {
        "calls": _USAGE["calls"],
        "success_calls": _USAGE["success_calls"],
        "error_calls": _USAGE["error_calls"],
        "input_tokens": _USAGE["input_tokens"],
        "output_tokens": _USAGE["output_tokens"],
        "total_tokens": _USAGE["input_tokens"] + _USAGE["output_tokens"],
        "avg_latency_ms": round(_USAGE["total_latency_ms"] / _USAGE["calls"], 1) if _USAGE["calls"] else 0,
        "by_model": by_model,
    }


def reset_llm_usage():
    _USAGE.clear()
    _USAGE.update({
        "calls": 0, "success_calls": 0, "error_calls": 0,
        "input_tokens": 0, "output_tokens": 0, "total_latency_ms": 0.0, "by_model": {},
    })


_llm_client = None


def get_llm_client():
    """懒加载 OpenAI 兼容客户端"""
    global _llm_client
    if _llm_client is None:
        from openai import OpenAI
        settings = get_settings()
        if not settings.deepseek_api_key:
            raise LLMError("未配置 DEEPSEEK_API_KEY")
        _llm_client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _llm_client


def chat(
    system: str,
    user: str = "",
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> str:
    """单次对话，返回文本。失败抛 LLMError。"""
    settings = get_settings()
    client = get_llm_client()
    messages = [{"role": "system", "content": system}]
    if user:
        messages.append({"role": "user", "content": user})
    model_name = model or settings.default_model
    kwargs = {"model": model_name, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    start = time.time()
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        _record_usage(model_name, 0, 0, (time.time() - start) * 1000, success=False)
        raise LLMError(f"LLM 调用失败: {e}") from e
    latency_ms = (time.time() - start) * 1000
    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    _record_usage(model_name, input_tokens, output_tokens, latency_ms, success=True)
    content = resp.choices[0].message.content or ""
    if not content.strip():
        raise LLMError("LLM 返回为空")
    return content


def chat_json(
    system: str,
    user: str = "",
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> Dict:
    """单次对话并要求返回 JSON 对象（容忍 ```json 包裹 / 前后缀文字）"""
    content = chat(system, user, model=model, temperature=temperature, max_tokens=max_tokens)
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        raise LLMError("LLM 未返回 JSON")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM JSON 解析失败: {e}") from e
