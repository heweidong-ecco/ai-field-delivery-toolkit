"""看板数据生成器（v1.2.0：增加成本趋势）"""

from typing import Dict, Any
from datetime import datetime

from core.logging.logger import get_logger

logger = get_logger()


class DashboardGenerator:
    """生成基础看板数据"""

    def generate(self, metrics: Dict[str, Any], alerts: list) -> Dict[str, Any]:
        """生成看板数据（含成本趋势）"""
        # 计算成本趋势
        cost_trend = self._build_cost_trend(metrics.get("calls_by_hour", {}), metrics.get("cost_by_model", {}))

        dashboard = {
            "summary": {
                "success_rate": metrics.get("success_rate"),
                "p99_latency_ms": metrics.get("p99_latency_ms"),
                "total_tokens": metrics.get("total_tokens"),
                "total_input_tokens": metrics.get("total_input_tokens"),
                "total_output_tokens": metrics.get("total_output_tokens"),
                "total_cost": metrics.get("total_cost"),
                "total_requests": metrics.get("total_requests"),
                "degradation_count": metrics.get("degradation_count"),
            },
            "cost": {
                "total_cost": metrics.get("total_cost"),
                "cost_by_model": metrics.get("cost_by_model", {}),
                "cost_trend": cost_trend,
            },
            "alerts": alerts,
            "error_by_model": metrics.get("error_by_model", {}),
            "calls_by_hour": metrics.get("calls_by_hour", {}),
            "updated_at": datetime.now().isoformat(),
        }
        logger.info("看板数据已生成")
        return dashboard

    def _build_cost_trend(self, calls_by_hour: Dict[str, int], cost_by_model: Dict[str, float]) -> Dict[str, Any]:
        """构建成本趋势数据

        MVP 简化实现：根据每小时调用量和平均成本估算每小时成本趋势。
        实际生产环境可接入完整的时间序列分析。
        """
        if not calls_by_hour:
            return {"hourly": [], "average_cost_per_call": 0.0}

        total_calls = sum(calls_by_hour.values())
        total_cost = sum(cost_by_model.values()) if cost_by_model else 0.0
        avg_cost = total_cost / total_calls if total_calls > 0 else 0.0

        hourly_trend = []
        for hour, count in sorted(calls_by_hour.items()):
            hourly_trend.append({
                "hour": hour,
                "calls": count,
                "estimated_cost": round(count * avg_cost, 4),
            })

        return {
            "hourly": hourly_trend,
            "average_cost_per_call": round(avg_cost, 6),
        }

    def save_dashboard(self, dashboard: Dict[str, Any], output_path: str):
        """保存看板数据为 JSON"""
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, ensure_ascii=False, indent=2)
        logger.info(f"看板数据已保存: {output_path}")
        return output_path