import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
知识库构建示例（最小件）：长文本分块 + 质检

运行方式：
    python examples/kb_example.py
"""

from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 知识库分块/质检示例 ===")

    from kb.service import chunk_text, quality_check

    # 模拟一段长文档（运维手册片段重复）
    doc = (
        "设备启动前请检查电源连接，确认指示灯为绿色。"
        "若指示灯为红色，请检查保险丝并联系维护工程师。"
        "维护工程师电话：400-XXX-XXXX。" * 20
    )

    chunks = chunk_text(doc, chunk_size=80, overlap=20)
    logger.info(f"分块完成: {len(chunks)} 块（大小 80，重叠 20）")

    quality = quality_check(chunks)
    logger.info(f"质检: 空块 {quality['empty']} / 重复 {quality['duplicates']} / 过短 {quality['too_short']} / 超长 {quality['too_long']}")
    logger.info(f"质检结论: {'；'.join(quality['issues'])}")

    logger.info("前 3 块预览：")
    for c in chunks[:3]:
        logger.info(f"  - {c[:40]}…")
