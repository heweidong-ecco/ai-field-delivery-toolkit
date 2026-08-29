"""基础指标收集器（v1.2.0：增加成本追踪）"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.logging.logger import get_logger

logger = get_logger()


class MetricsCollector:
    """基础指标收集器（内存存储）

    v1.2.0 新增：
    - 成本追踪：按模型记录 token 消耗，结合单价估算成本
    - 按小时分桶的调用统计，用于趋势图
    """

    # 模型单价（元/百万 token），可根据实际调整
    MODEL_PRICES = {
        "deepseek-chat": {"input": 1.0, "output": 2.0},
        "deepseek-reasoner": {"input": 4.0, "output": 16.0},
        "qwen-turbo": {"input": 3.0, "output": 9.0},
        "qwen-plus": {"input": 2.5, "output": 10.0},
        "unknown": {"input": 5.0, "output": 10.0},
    }

    def __init__(self):
        self.total_requests = 0
        self.success_requests = 0
        self.failure_requests = 0
        self.latencies: List[float] = []
        self.token_usage_input: List[int] = []
        self.token_usage_output: List[int] = []
        self.degradation_count = 0
        self.error_by_model: Dict[str, int] = defaultdict(int)
        self.calls_by_hour: Dict[str, int] = defaultdict(int)
        self.cost_by_model: Dict[str, float] = defaultdict(float)

    def record_request(
        self,
        success: bool,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "unknown",
        hour: Optional[str] = None,
    ):
        """记录一次请求（v1.2.0 增加 input/output token 拆分和小时分桶）"""
        self.total_requests += 1
        if success:
            self.success_requests += 1
        else:
            self.failure_requests += 1
            self.error_by_model[model] += 1
        self.latencies.append(latency_ms)
        self.token_usage_input.append(input_tokens)
        self.token_usage_output.append(output_tokens)

        # 按小时统计调用次数
        if hour is None:
            hour = datetime.now().strftime("%Y-%m-%d %H:00")
        self.calls_by_hour[hour] += 1

        # 成本估算
        price = self.MODEL_PRICES.get(model, self.MODEL_PRICES["unknown"])
        cost = (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"]
        self.cost_by_model[model] += cost

    def record_degradation(self):
        """记录一次降级"""
        self.degradation_count += 1

    def get_metrics(self) -> Dict[str, Any]:
        """获取当前指标汇总"""
        success_rate = self.success_requests / self.total_requests if self.total_requests > 0 else 1.0
        p99_latency = self._calc_p99(self.latencies)
        total_input_tokens = sum(self.token_usage_input)
        total_output_tokens = sum(self.token_usage_output)
        total_cost = sum(self.cost_by_model.values())

        return {
            "total_requests": self.total_requests,
            "success_requests": self.success_requests,
            "failure_requests": self.failure_requests,
            "success_rate": round(success_rate, 4),
            "p99_latency_ms": p99_latency,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "total_cost": round(total_cost, 4),
            "degradation_count": self.degradation_count,
            "error_by_model": dict(self.error_by_model),
            "cost_by_model": {k: round(v, 4) for k, v in self.cost_by_model.items()},
            "calls_by_hour": dict(sorted(self.calls_by_hour.items())),
        }

    def _calc_p99(self, values: List[float]) -> float:
        """计算 P99 延迟"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        idx = int(len(sorted_values) * 0.99)
        return sorted_values[min(idx, len(sorted_values) - 1)]