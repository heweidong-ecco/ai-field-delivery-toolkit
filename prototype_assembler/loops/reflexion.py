"""Reflexion 循环：执行 → 反思 → 改进 → 重试"""

from typing import Any

from core.logging.logger import get_logger

from prototype_assembler.loops.base import BaseLoop

logger = get_logger()


class ReflexionLoop(BaseLoop):
    """Reflexion 循环模式

    流程：
    1. 执行任务，得到初始结果
    2. 评估结果质量（通过评估函数）
    3. 如果未通过，反思失败原因
    4. 带着反思内容重新执行
    5. 重复直到通过或达到最大重试次数
    """

    name = "reflexion"

    def __init__(self, max_reflections: int = 3, evaluator=None):
        self.max_reflections = max_reflections
        self.evaluator = evaluator  # 评估函数，返回 (passed: bool, feedback: str)

    def run(self, agent: Any, user_input: str, resume: bool = False) -> str:
        step_count = agent.state.current_step if resume else 0
        final_answer = ""
        reflection_history = []

        for i in range(step_count, agent.max_iterations):
            context = agent.context_builder.build(agent.memory_short, agent.memory_long, agent.tools)

            # 1. 执行任务
            result = self._call_llm(agent, context, user_input, reflection_history)
            agent.state.add_step({"step": i, "action": "execute", "content": result})

            # 2. 评估结果
            if self.evaluator:
                passed, feedback = self.evaluator(result)
            else:
                # 没有评估器时，默认通过
                passed, feedback = True, ""

            if passed:
                final_answer = result
                agent.state.add_step({"step": i, "action": "finish", "content": result})
                break
            else:
                # 3. 反思失败原因
                reflection = f"上次结果未通过评估：{feedback}"
                reflection_history.append(reflection)
                agent.state.add_step({"step": i, "action": "reflect", "content": reflection})
                agent.memory_short.add("assistant", reflection)
                logger.info(f"Reflexion 第 {i+1} 次反思：{feedback}")

            # 4. 检查是否达到最大反思次数
            if len(reflection_history) >= self.max_reflections:
                final_answer = result  # 返回最后一次结果
                agent.state.add_step({"step": i, "action": "max_reflections"})
                break

        if not final_answer:
            final_answer = "达到最大迭代次数，任务未完成"
            agent.state.add_step({"action": "max_iterations"})

        return final_answer

    def _call_llm(self, agent, context, user_input, reflection_history):
        """调用 LLM 执行任务（带反思历史）

        可注入函数（通过 Agent 实例属性注入，v8.0）：
        - agent.llm_call: 自定义 LLM 调用函数，签名 (agent, context, user_input) -> str，
          返回 `finish:<最终答案>`；本循环会去掉 `finish:` 前缀再作为作答结果（供评估器与最终答案使用）。
          反思历史通过 agent._reflection_history 传给 llm_call。
        未注入时回退到占位实现（兼容旧行为）。
        """
        if hasattr(agent, "llm_call") and agent.llm_call:
            agent._reflection_history = reflection_history
            result = agent.llm_call(agent, context, user_input)
            if isinstance(result, str):
                result = result.strip()
                if result.startswith("finish:"):
                    result = result[len("finish:"):].strip()
                return result
            logger.warning("llm_call 返回格式错误，使用默认占位输出")
        # 占位实现：简单拼接上下文和反思历史
        reflection_text = "\n".join(reflection_history) if reflection_history else "无"
        return f"执行结果（反思历史：{reflection_text}）"