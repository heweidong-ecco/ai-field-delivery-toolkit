import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
数据准备器使用示例

运行方式：
    python examples/data_prep_example.py

流程：数据接入 → 质量评估 → 清洗（含语义去重）→ 评测集构建
"""

import csv
import os

from data_prep.pipeline import DataPrepPipeline
from core.logging.logger import get_logger

logger = get_logger()

# 示例数据：真实使用中替换为你的 csv/json/pdf 文件，或 source_type="db" + db_connection
SAMPLE_DOCS = [
    "基于内部知识库搭建智能问答系统",
    "自动对客户工单进行多级分类",
    "从租赁合同中抽取关键条款",
    "对生产设备故障日志做根因分析",
    "将非结构化简历解析为结构化字段",
    "销售话术复盘并生成改进建议",
    "质检报告中的异常数据清洗",
    "对客服对话进行情感分析",
    "跨系统数据一致性自动校验",
    "政策文件要点提取与摘要生成",
    "投标文档自动比对关键差异",
    "用户评论主题聚类分析",
    "电商商品描述自动生成",
    "医疗报告关键指标抽取",
    "财务报表科目异常检测",
    "招聘岗位与简历匹配打分",
    "论文参考文献格式化转换",
    "会议纪要自动生成行动项",
    "代码仓库缺陷标题规范化",
    "城市交通拥堵热点分析",
]


if __name__ == "__main__":
    logger.info("=== 数据准备器示例 ===")

    # 1. 准备一份示例 CSV（真实使用中替换为你的数据文件）
    sample_dir = "output/data_prep"
    os.makedirs(sample_dir, exist_ok=True)
    csv_path = os.path.join(sample_dir, "sample.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["content"])
        writer.writeheader()
        for doc in SAMPLE_DOCS:
            writer.writerow({"content": doc})

    # 2. 执行完整数据准备流程
    pipeline = DataPrepPipeline()
    result = pipeline.run(
        source_type="csv",
        source_path=csv_path,
        output_dir=sample_dir,
        eval_samples=10,
    )

    logger.info(f"原始条数: {result['raw_count']}")
    logger.info(f"清洗后条数: {result['cleaned_count']}")
    logger.info(f"评测集条数: {result['eval_set_count']}")
    logger.info(f"结果输出目录: {result['output_dir']}")
    logger.info("产物文件：cleaned_data.json / eval_set.json / quality_report.json / cleaning_stats.json")
