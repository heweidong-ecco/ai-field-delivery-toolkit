"""格式归一"""

import re
from typing import List, Dict, Any


def normalize(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对 content 进行基础归一化：统一空白符、去除首尾空格"""
    for item in data:
        content = item.get("content", "")
        # 多个空格/换行/制表符压缩为单个空格
        content = re.sub(r"\s+", " ", content).strip()
        item["content"] = content
    return data