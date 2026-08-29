import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
监控开箱器使用示例

运行方式：
    python examples/monitor_example.py
"""

from monitor.metrics import MetricsCollector
from monitor.alerts import AlertManager
from monitor.dashboard import DashboardGenerator
from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 监控开箱器示例 ===")

    # 收集指标（v1.2.0 起 token 拆分 input/output）
    collector = MetricsCollector()
    collector.record_request(success=True, latency_ms=120, input_tokens=350, output_tokens=150, model="deepseek-chat")
    collector.record_request(success=True, latency_ms=200, input_tokens=420, output_tokens=180, model="deepseek-chat")
    collector.record_request(success=False, latency_ms=3500, input_tokens=0, output_tokens=0, model="deepseek-chat")
    collector.record_degradation()

    metrics = collector.get_metrics()
    logger.info(f"请求总数: {metrics['total_requests']}")
    logger.info(f"成功率: {metrics['success_rate']}")
    logger.info(f"P99 延迟: {metrics['p99_latency_ms']}ms")

    # 检查告警
    alert_mgr = AlertManager()
    triggered = alert_mgr.check_all(metrics)
    logger.info(f"触发告警: {len(triggered)} 条")
    for alert in triggered:
        logger.info(f"  - {alert['rule_name']}: 当前值 {alert['current_value']}")

    # 生成看板
    dashboard_gen = DashboardGenerator()
    dashboard = dashboard_gen.generate(metrics, triggered)
    dashboard_gen.save_dashboard(dashboard, "dashboard.json")
    logger.info("看板数据已保存到 dashboard.json")