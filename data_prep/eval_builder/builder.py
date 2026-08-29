"""评测集构建器"""

import random
from typing import List, Dict, Any, Optional


class EvalSetBuilder:
    """从清洗后数据构建评测集"""

    def build(
        self,
        data: List[Dict[str, Any]],
        num_samples: int = 100,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """构建评测集

        参数:
            data: 清洗后的数据列表
            num_samples: 评测集样本数
            seed: 随机种子

        返回:
            {
                "eval_set": [{"instruction": "...", "output": "...", "metadata": {...}}, ...],
                "coverage_stats": {...}
            }
        """
        if len(data) == 0:
            return {"eval_set": [], "coverage_stats": {}}

        # 固定随机种子
        random.seed(seed)

        # 分层抽样：按长度简单分桶（短/中/长）
        short, medium, long = [], [], []
        for item in data:
            length = len(item["content"])
            if length < 100:
                short.append(item)
            elif length < 500:
                medium.append(item)
            else:
                long.append(item)

        # 每桶配额（30%/40%/30%）
        short_quota = int(num_samples * 0.3)
        medium_quota = int(num_samples * 0.4)
        long_quota = num_samples - short_quota - medium_quota
        buckets = [("short", short, short_quota), ("medium", medium, medium_quota), ("long", long, long_quota)]

        # 1. 按配额从各桶抽样（桶内样本不足时取全部）
        picked = []
        picked_ids = set()

        for _, pool, quota in buckets:
            if not pool:
                continue
            if len(pool) <= quota:
                chosen = pool
            else:
                chosen = random.sample(pool, quota)
            picked.extend(chosen)
            picked_ids.update(id(x) for x in chosen)

        # 2. 配额未用尽（空桶/不足桶）时，从剩余样本补足到 num_samples
        if len(picked) < num_samples:
            remaining = [item for item in data if id(item) not in picked_ids]
            random.shuffle(remaining)
            picked.extend(remaining[: num_samples - len(picked)])

        random.shuffle(picked)

        # 构造评测集格式：instruction 取自 content，output 留空（或根据场景填充）
        eval_set = []
        for item in picked:
            content = item["content"]
            # 简单截断作为 instruction
            instruction = content[:200]
            eval_set.append({
                "instruction": instruction,
                "input": "",
                "output": "",  # MVP 无标准答案，标注阶段填充
                "metadata": item.get("metadata", {}),
            })

        # 按实际抽样分布统计各桶数量
        short_count = sum(1 for x in picked if len(x["content"]) < 100)
        medium_count = sum(1 for x in picked if 100 <= len(x["content"]) < 500)
        long_count = sum(1 for x in picked if len(x["content"]) >= 500)

        coverage_stats = {
            "总样本数": len(eval_set),
            "短文本": short_count,
            "中文本": medium_count,
            "长文本": long_count,
        }

        return {"eval_set": eval_set, "coverage_stats": coverage_stats}