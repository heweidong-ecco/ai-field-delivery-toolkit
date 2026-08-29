"""反馈回流：将用户点踩和人工审核失败数据收集到标注池"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.logging.logger import get_logger

logger = get_logger()


class FeedbackCollector:
    """反馈收集器

    MVP 版本使用内存标注池 + JSON 文件持久化。
    后续可替换为数据库存储。
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self.annotation_pool: List[Dict[str, Any]] = []
        if storage_path and os.path.exists(storage_path):
            self._load(storage_path)

    def add_feedback(
        self,
        request_id: str,
        user_input: str,
        model_output: str,
        feedback_type: str = "dislike",   # dislike / audit_fail / low_confidence
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """添加一条反馈到标注池

        参数:
            request_id: 请求标识，用于全链路追踪
            user_input: 用户原始输入
            model_output: 模型输出
            feedback_type: 反馈类型
            note: 备注（如人工审核的错误原因）
        """
        item = {
            "id": len(self.annotation_pool) + 1,
            "request_id": request_id,
            "user_input": user_input,
            "model_output": model_output,
            "feedback_type": feedback_type,
            "note": note or "",
            "created_at": datetime.now().isoformat(),
        }
        self.annotation_pool.append(item)
        logger.info(f"反馈已进入标注池: {feedback_type}, request_id={request_id}")
        return item

    def get_pool(self) -> List[Dict[str, Any]]:
        """获取当前标注池全部数据"""
        return self.annotation_pool

    def clear_pool(self):
        """清空标注池"""
        self.annotation_pool = []
        logger.info("标注池已清空")

    def save(self, path: Optional[str] = None):
        """保存标注池到 JSON 文件"""
        save_path = path or self.storage_path
        if not save_path:
            raise ValueError("未指定保存路径")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.annotation_pool, f, ensure_ascii=False, indent=2)
        logger.info(f"标注池已保存: {save_path}")

    def _load(self, path: str):
        """从 JSON 文件加载标注池"""
        with open(path, "r", encoding="utf-8") as f:
            self.annotation_pool = json.load(f)
        logger.info(f"标注池已加载: {path}，共 {len(self.annotation_pool)} 条")