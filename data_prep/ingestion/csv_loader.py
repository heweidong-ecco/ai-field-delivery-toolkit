"""CSV 数据接入"""

import csv
from typing import List, Dict, Any

from data_prep.ingestion.base import DataIngestor
from core.logging.logger import get_logger

logger = get_logger()


class CSVLoader(DataIngestor):
    """从 CSV 文件接入数据"""

    def ingest(self, source_path: str) -> Dict[str, Any]:
        records = []
        with open(source_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 将整行拼成一个字符串作为 content，同时保留原始字段
                content = " ".join(str(v) for v in row.values() if v)
                records.append({
                    "content": content,
                    "metadata": row,
                })
        return {"data": records}