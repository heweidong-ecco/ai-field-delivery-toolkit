"""预置降级预案"""

from core.logging.logger import get_logger

logger = get_logger()


class DegradationPreset:
    """预置降级路径"""

    @staticmethod
    def get_default_chain() -> dict:
        """返回默认降级链，供部署配置使用"""
        return {
            "chain": [
                {"level": "model", "action": "call_model"},
                {"level": "cache", "action": "read_cache"},
                {"level": "rule", "action": "rule_fallback"},
                {"level": "manual", "action": "push_manual_queue"},
                {"level": "reject", "action": "return_default_message"},
            ],
            "thresholds": {
                "model_error_rate": 0.05,      # 错误率 >5% 切换备用模型
                "model_timeout_seconds": 30,   # 超时 >30 秒切换
                "fallback_enabled": True,      # 降级链默认启用
            },
        }

    @staticmethod
    def generate_degradation_yaml(output_path: str):
        """生成降级配置 YAML 文件"""
        import yaml
        data = DegradationPreset.get_default_chain()
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
        logger.info(f"降级预案已生成: {output_path}")
        return output_path