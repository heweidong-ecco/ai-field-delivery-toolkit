"""数据准备统一管道入口

用法：
    from data_prep.pipeline import DataPrepPipeline

    pipeline = DataPrepPipeline()
    result = pipeline.run(
        source_type="csv",
        source_path="/path/to/data.csv",
        output_dir="/path/to/output",
        eval_samples=100,
    )
"""

import os
from typing import Dict, Any, Optional, List

from core.logging.logger import get_logger
from core.security.pii import PIIDetector

from data_prep.ingestion.base import DataIngestor
from data_prep.ingestion.csv_loader import CSVLoader
from data_prep.ingestion.json_loader import JSONLoader
from data_prep.ingestion.pdf_loader import PDFLoader
from data_prep.ingestion.db_loader import DBLoader

from data_prep.quality.evaluator import DataQualityEvaluator
from data_prep.quality.report import QualityReport

from data_prep.cleaning.cleaner import DataCleaner

from data_prep.eval_builder.builder import EvalSetBuilder

logger = get_logger()


class DataPrepPipeline:
    """数据准备统一管道"""

    def __init__(self):
        self._ingestors = {
            "csv": CSVLoader(),
            "json": JSONLoader(),
            "pdf": PDFLoader(),
            "db": DBLoader(),
        }
        self._evaluator = DataQualityEvaluator()
        self._cleaner = DataCleaner()
        self._eval_builder = EvalSetBuilder()

    def run(
        self,
        source_type: str,
        source_path: str,
        output_dir: str,
        eval_samples: int = 100,
        db_connection: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行完整数据准备流程

        参数:
            source_type: 数据源类型（csv/json/pdf/db）
            source_path: 数据源路径或标识
            output_dir: 输出目录
            eval_samples: 评测集样本数
            db_connection: 数据库连接串（source_type=db 时使用）

        返回:
            包含各步骤结果的字典
        """
        logger.info(f"开始数据准备：source_type={source_type}, source_path={source_path}")

        # 1. 数据接入
        ingest_result = self._ingest(source_type, source_path, db_connection)
        raw_data = ingest_result["data"]
        logger.info(f"数据接入完成：{len(raw_data)} 条记录")

        # 2. 质量评估
        quality_report = self._evaluator.evaluate(raw_data)
        logger.info(f"质量评估完成：{quality_report.summary}")

        # 3. 数据清洗（v1.2.0 增加语义去重参数）
        cleaned_data, cleaning_stats = self._cleaner.clean(
            raw_data,
            dedup_similarity=None,          # 字符级去重阈值，None 为完全一致
            semantic_dedup=True,            # 启用语义去重
            semantic_threshold=0.85,        # 语义去重阈值
        )

        # 4. 构建评测集
        eval_result = self._eval_builder.build(cleaned_data, num_samples=eval_samples)
        logger.info(f"评测集构建完成：{len(eval_result['eval_set'])} 条样本")

        # 5. 保存结果
        os.makedirs(output_dir, exist_ok=True)
        self._save_results(output_dir, cleaned_data, eval_result, quality_report, cleaning_stats)

        return {
            "raw_count": len(raw_data),
            "cleaned_count": len(cleaned_data),
            "quality_report": quality_report.to_dict(),
            "cleaning_stats": cleaning_stats,
            "eval_set_count": len(eval_result["eval_set"]),
            "output_dir": output_dir,
        }

    def _ingest(self, source_type: str, source_path: str, db_connection: Optional[str]) -> Dict:
        """数据接入"""
        if source_type not in self._ingestors:
            raise ValueError(f"不支持的数据源类型: {source_type}")
        ingestor = self._ingestors[source_type]
        if source_type == "db":
            if not db_connection:
                raise ValueError("数据库接入需要提供 db_connection")
            return ingestor.ingest(db_connection)
        else:
            return ingestor.ingest(source_path)

    def _save_results(self, output_dir, cleaned_data, eval_result, quality_report, cleaning_stats):
        """保存清洗后的数据、评测集、报告"""
        import json

        # 保存清洗后数据
        with open(os.path.join(output_dir, "cleaned_data.json"), "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

        # 保存评测集
        with open(os.path.join(output_dir, "eval_set.json"), "w", encoding="utf-8") as f:
            json.dump(eval_result["eval_set"], f, ensure_ascii=False, indent=2)

        # 保存质量报告
        with open(os.path.join(output_dir, "quality_report.json"), "w", encoding="utf-8") as f:
            json.dump(quality_report.to_dict(), f, ensure_ascii=False, indent=2)

        # 保存清洗统计
        with open(os.path.join(output_dir, "cleaning_stats.json"), "w", encoding="utf-8") as f:
            json.dump(cleaning_stats, f, ensure_ascii=False, indent=2)

        logger.info(f"结果已保存至 {output_dir}")