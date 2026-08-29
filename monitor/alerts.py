"""告警规则定义与检查"""

from typing import Dict, Any, List

from core.logging.logger import get_logger

logger = get_logger()


class AlertRule:
    """告警规则定义"""

    def __init__(self, name: str, metric: str, operator: str, threshold: float, severity: str = "warning"):
        self.name = name
        self.metric = metric
        self.operator = operator  # >, <, >=, <=
        self.threshold = threshold
        self.severity = severity  # info, warning, critical

    def check(self, metrics: Dict[str, Any]) -> bool:
        """检查指标是否触发告警"""
        value = metrics.get(self.metric)
        if value is None:
            return False
        if self.operator == ">":
            return value > self.threshold
        elif self.operator == "<":
            return value < self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        return False


class AlertManager:
    """告警管理器：定义默认规则并检查触发"""

    def __init__(self):
        # 默认三条告警规则
        self.rules = [
            AlertRule("错误率超限", "success_rate", "<", 0.95, "critical"),
            AlertRule("P99 延迟超限", "p99_latency_ms", ">", 3000, "warning"),
            AlertRule("降级触发", "degradation_count", ">", 0, "warning"),
        ]

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def check_all(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查所有规则，返回已触发的告警列表"""
        triggered = []
        for rule in self.rules:
            if rule.check(metrics):
                triggered.append({
                    "rule_name": rule.name,
                    "severity": rule.severity,
                    "metric": rule.metric,
                    "threshold": rule.threshold,
                    "current_value": metrics.get(rule.metric),
                })
        if triggered:
            logger.warning(f"触发 {len(triggered)} 条告警")
        return triggered