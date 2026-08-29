import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
部署加固器使用示例

运行方式：
    python examples/deploy_example.py
"""

from dotenv import load_dotenv

from deploy_hardener.pipeline import DeployHardenerPipeline
from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 部署加固器示例 ===")

    # 加载 .env 到环境变量，供部署前环境检查使用（真实部署需先配置好这些变量）
    load_dotenv()

    pipeline = DeployHardenerPipeline()

    # Docker Compose 部署
    result = pipeline.run(
        project_dir=".",               # 当前项目目录
        output_dir="output/deploy",     # 输出目录
        mode="docker-compose",
    )
    logger.info(f"部署模式: {result['mode']}")
    logger.info(f"降级配置: {result['degradation_config']}")
    logger.info(f"Compose 配置: {result.get('compose_file')}")

    # 裸机部署
    result2 = pipeline.run(
        project_dir=".",
        output_dir="output/deploy_bare",
        mode="bare-metal",
    )
    logger.info(f"systemd 服务文件: {result2.get('systemd_service')}")