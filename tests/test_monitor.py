"""监控开箱器测试（v1.2.0）"""

from monitor.metrics import MetricsCollector
from monitor.alerts import AlertManager
from monitor.dashboard import DashboardGenerator


class TestMetricsCollectorV2:
    """指标收集测试（含成本）"""

    def test_cost_tracking(self):
        collector = MetricsCollector()
        collector.record_request(
            success=True,
            latency_ms=100,
            input_tokens=500,
            output_tokens=200,
            model="deepseek-chat",
        )
        metrics = collector.get_metrics()
        assert metrics["total_input_tokens"] == 500
        assert metrics["total_output_tokens"] == 200
        # deepseek-chat: input 1元/百万, output 2元/百万
        # cost = 500/1e6 * 1 + 200/1e6 * 2 = 0.0005 + 0.0004 = 0.0009
        assert metrics["total_cost"] > 0
        assert "deepseek-chat" in metrics["cost_by_model"]

    def test_calls_by_hour(self):
        collector = MetricsCollector()
        collector.record_request(True, 100, 10, 10, "deepseek-chat", hour="2026-08-28 14:00")
        collector.record_request(True, 100, 10, 10, "deepseek-chat", hour="2026-08-28 14:00")
        collector.record_request(True, 100, 10, 10, "deepseek-chat", hour="2026-08-28 15:00")
        metrics = collector.get_metrics()
        assert "2026-08-28 14:00" in metrics["calls_by_hour"]
        assert metrics["calls_by_hour"]["2026-08-28 14:00"] == 2


class TestDashboardV2:
    """看板测试（含成本趋势）"""

    def test_cost_trend(self):
        collector = MetricsCollector()
        collector.record_request(True, 100, 100, 50, "deepseek-chat", hour="14:00")
        collector.record_request(True, 120, 150, 80, "deepseek-chat", hour="15:00")
        metrics = collector.get_metrics()
        gen = DashboardGenerator()
        dashboard = gen.generate(metrics, [])
        assert "cost" in dashboard
        assert dashboard["cost"]["total_cost"] > 0
        assert len(dashboard["cost"]["cost_trend"]["hourly"]) == 2