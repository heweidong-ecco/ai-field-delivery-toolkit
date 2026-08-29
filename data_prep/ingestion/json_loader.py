"""JSON 数据接入"""

import json
from typing import List, Dict, Any

from data_prep.ingestion.base import DataIngestor


class JSONLoader(DataIngestor):
    """从 JSON 文件接入数据"""

    def ingest(self, source_path: str) -> Dict[str, Any]:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = []
        # 支持 JSON 数组或对象
        if isinstance(data, list):
            for item in data:
                content = item.get("content", item.get("text", str(item)))
                records.append({"content": content, "metadata": item})
        elif isinstance(data, dict):
            # 如果是单个对象，取所有字段拼接
            content = " ".join(str(v) for v in data.values())
            records.append({"content": content, "metadata": data})

        return {"data": records}