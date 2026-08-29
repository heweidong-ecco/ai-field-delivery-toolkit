import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
原型组装器使用示例

运行方式：
    python examples/prototype_example.py
"""

from prototype_assembler.assembler import PrototypeAssembler
from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 原型组装器示例 ===")

    assembler = PrototypeAssembler()

    # 列出可用模板
    logger.info(f"可用模板: {list(assembler.TEMPLATE_MAP.keys())}")

    # 创建知识问答 Agent
    logger.info("创建知识问答 Agent 原型...")
    agent = assembler.create("knowledge_qa")
    logger.info(f"Agent ID: {agent.agent_id}, 循环模式: {agent.loop.name}")

    # 运行原型
    result = agent.run("什么是RAG？")
    logger.info(f"运行结果: {result}")