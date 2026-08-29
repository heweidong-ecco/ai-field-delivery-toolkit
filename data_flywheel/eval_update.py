"""手动评测集更新：从标注池中选取样本，更新评测集"""

import json
import random
from typing import Dict, Any, List, Optional

from core.logging.logger import get_logger

logger = get_logger()


class EvalSetUpdater:
    """评测集更新器"""

    def update(
        self,
        annotation_pool: List[Dict[str, Any]],
        eval_set_path: str,
        num_samples: int = 20,
        seed: int = 42,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从标注池中抽样，追加到评测集

        参数:
            annotation_pool: 标注池数据（来自 FeedbackCollector.get_pool()）
            eval_set_path: 当前评测集 JSON 文件路径
            num_samples: 本次新增样本数
            seed: 随机种子
            output_path: 输出路径，默认覆盖原评测集文件
        """
        # 加载现有评测集
        with open(eval_set_path, "r", encoding="utf-8") as f:
            eval_set = json.load(f)

        # 从标注池中随机抽样
        random.seed(seed)
        sample_size = min(num_samples, len(annotation_pool))
        sampled = random.sample(annotation_pool, sample_size)

        # 转换为评测集格式（与 data_prep 中的评测集格式一致）
        new_items = []
        for item in sampled:
            new_items.append({
                "instruction": item["user_input"],
                "input": "",
                "output": item["model_output"],   # 人工修改后可覆盖
                "metadata": {
                    "source": "feedback_pool",
                    "feedback_type": item["feedback_type"],
                    "note": item.get("note", ""),
                },
            })

        eval_set.extend(new_items)

        # 保存
        save_path = output_path or eval_set_path
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(eval_set, f, ensure_ascii=False, indent=2)

        logger.info(f"评测集已更新：新增 {len(new_items)} 条，当前总数 {len(eval_set)} 条")
        return {
            "added_count": len(new_items),
            "total_count": len(eval_set),
            "save_path": save_path,
        }