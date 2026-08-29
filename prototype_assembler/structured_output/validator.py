"""结构化输出验证与重试"""

from typing import Any, Callable, Dict

from core.logging.logger import get_logger

logger = get_logger()


class StructuredOutputValidator:
    """结构化输出验证器"""

    def __init__(self, schema: Dict[str, Any], max_retries: int = 3):
        self.schema = schema
        self.max_retries = max_retries

    def validate_and_retry(self, llm_call: Callable, prompt: str) -> Dict[str, Any]:
        """调用 LLM 并验证输出，非法时重试

        参数:
            llm_call: LLM 调用函数，返回字符串
            prompt: 提示词
        """
        for attempt in range(1, self.max_retries + 1):
            raw_output = llm_call(prompt)
            # 简单验证：JSON 可解析，且包含 schema 中定义的字段
            import json
            try:
                data = json.loads(raw_output)
                # 检查必填字段
                required = self.schema.get("required", [])
                missing = [f for f in required if f not in data]
                if not missing:
                    return data
                logger.warning(f"结构化输出缺少字段 {missing}，第 {attempt} 次重试")
            except json.JSONDecodeError:
                logger.warning(f"输出不是合法 JSON，第 {attempt} 次重试")
            # 重试时在 prompt 中追加错误提示
            prompt += f"\n上次输出无效：{raw_output[:200]}"

        # 全部重试失败，降级返回默认结构
        default_data = {k: "" for k in self.schema.get("required", [])}
        logger.error("结构化输出验证失败，降级为默认值")
        return default_data