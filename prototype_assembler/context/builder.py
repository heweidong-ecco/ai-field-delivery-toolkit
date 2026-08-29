"""上下文组装与 token 预算"""

from typing import List, Any

from core.logging.logger import get_logger

logger = get_logger()


class ContextBuilder:
    """上下文组装器"""

    def __init__(self, system_prompt: str, max_tokens: int = 2048):
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens

    def build(self, memory_short, memory_long, tools: list) -> str:
        """构建上下文

        组装顺序：系统提示词 → 工具描述 → 长期记忆 → 短期记忆
        """
        parts = [self.system_prompt]

        # 工具描述
        if tools:
            tool_desc = "\n".join([f"- {t.name}: {t.description}" for t in tools])
            parts.append(f"可用工具：\n{tool_desc}")

        # 长期记忆
        if memory_long:
            facts = memory_long.get_relevant("", top_k=3)
            if facts:
                facts_str = "\n".join([f"- {k}: {v}" for k, v in facts.items()])
                parts.append(f"用户长期记忆：\n{facts_str}")

        # 短期记忆
        messages = memory_short.get_all()
        if messages:
            history = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            parts.append(f"对话历史：\n{history}")

        context = "\n\n".join(parts)

        # Token 预算强制（粗略按字符数估算，1 token ≈ 2 中文字符或 4 英文字符）
        # 简化：按总长度限制
        if len(context) > self.max_tokens * 2:
            logger.warning("上下文超出预算，进行裁剪")
            context = context[: self.max_tokens * 2]
        return context