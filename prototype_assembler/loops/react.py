"""ReAct 循环：推理 → 行动 → 观察 → 继续（v1.2.0 可注入版）"""

from typing import Any

from core.logging.logger import get_logger

from prototype_assembler.loops.base import BaseLoop

logger = get_logger()


class ReActLoop(BaseLoop):
    """ReAct 循环模式

    流程：
    1. 构建上下文
    2. 调用 LLM 进行推理，决定下一步行动（finish/tool/answer）
    3. 执行行动：
        - finish：结束循环，返回最终答案
        - tool：调用指定工具，将观察结果加入短期记忆，继续循环
        - answer：直接返回答案
    4. 重复直到完成或达到最大迭代次数

    可注入函数（通过 Agent 实例属性注入）：
    - agent.llm_call: 自定义 LLM 调用函数，签名 (agent, context, user_input) -> str
    """

    name = "react"

    def run(self, agent: Any, user_input: str, resume: bool = False) -> str:
        step_count = agent.state.current_step if resume else 0
        final_answer = ""

        for i in range(step_count, agent.max_iterations):
            # 1. 构建上下文
            context = agent.context_builder.build(
                agent.memory_short,
                agent.memory_long,
                agent.tools,
            )
            # 2. 调用 LLM 进行推理 + 行动决策
            llm_result = self._call_llm(agent, context, user_input)
            # 3. 解析 LLM 结果
            action_type, action_content = self._parse_action(llm_result)
            # 4. 执行行动
            if action_type == "finish":
                final_answer = action_content
                agent.state.add_step({"step": i, "action": "finish", "content": action_content})
                break
            elif action_type == "tool":
                tool_name = action_content.get("name", "")
                tool_args = action_content.get("args", {})
                observation = self._execute_tool(agent, tool_name, tool_args)
                agent.state.add_step({
                    "step": i,
                    "action": "tool",
                    "tool": tool_name,
                    "observation": observation,
                })
                agent.memory_short.add("assistant", f"工具 {tool_name} 返回: {observation}")
            elif action_type == "answer":
                final_answer = action_content
                agent.state.add_step({"step": i, "action": "answer", "content": action_content})
                break
            else:
                # 默认作为回答
                final_answer = str(llm_result)
                agent.state.add_step({"step": i, "action": "unknown", "content": str(llm_result)})
                break

        if not final_answer and not agent.state.finished:
            final_answer = "达到最大迭代次数，任务未完成"
            agent.state.add_step({"action": "max_iterations"})

        return final_answer

    def _call_llm(self, agent: Any, context: str, user_input: str) -> str:
        """调用 LLM

        TODO: 实际项目中替换为真实模型 API 调用。
        可通过 agent.llm_call 注入自定义 LLM 调用函数。
        """
        if hasattr(agent, "llm_call") and agent.llm_call:
            result = agent.llm_call(agent, context, user_input)
            if isinstance(result, str):
                return result
            logger.warning("llm_call 返回格式错误，使用默认占位输出")

        # 默认占位实现：返回固定的 finish 指令
        return "finish: 已完成任务"

    def _parse_action(self, llm_result: str):
        """解析 LLM 输出为行动"""
        result_str = str(llm_result).strip()
        if result_str.startswith("finish:"):
            return "finish", result_str[len("finish:"):].strip()
        if result_str.startswith("tool:"):
            # 简单的工具调用格式：tool:工具名
            return "tool", {"name": result_str[5:].strip(), "args": {}}
        return "answer", result_str

    def _execute_tool(self, agent: Any, tool_name: str, tool_args: dict) -> str:
        """执行工具"""
        for tool in agent.tools:
            if tool.name == tool_name:
                return tool.run(tool_args)
        return f"工具 {tool_name} 不存在"