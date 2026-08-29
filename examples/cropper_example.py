import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
五步裁剪引擎使用示例

运行方式：
    python examples/cropper_example.py
"""

from cropper.constraints import (
    CustomerConstraints,
    HardwareConstraints,
    EnvironmentConstraints,
    DataConstraints,
    UserConstraints,
    ComplianceConstraints,
)
from cropper.engine import crop_for_customer
from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 五步裁剪引擎示例 ===")

    # 构造客户约束
    constraints = CustomerConstraints(
        customer_id="customer-001",
        budget=200000,
        hardware=HardwareConstraints(cpu="8核", memory_gb=32, gpu=None, storage_gb=500),
        environment=EnvironmentConstraints(
            os="ubuntu-22.04",
            docker=True,
            network="intranet-isolated",
            external_access=False,
        ),
        data=DataConstraints(
            total_records=300000,
            daily_new=500,
            formats=["csv", "json"],
            quality="dirty",
        ),
        users=UserConstraints(total_users=100, concurrent_peak=20),
        compliance=ComplianceConstraints(data_residency="on-premise", pii_sensitive=True),
        timeline_weeks=2,
    )

    plan = crop_for_customer(constraints)

    logger.info(f"启用模块: {plan.enabled_modules}")
    logger.info(f"删除模块: {plan.deleted_modules}")
    logger.info(f"简化配置: {plan.simplifications}")
    logger.info(f"自动化建议: {plan.automations}")
    logger.info(f"时间线建议: {plan.timeline_suggestion}")

    plan.save("crop_plan.json")
    logger.info("裁剪方案已保存到 crop_plan.json")