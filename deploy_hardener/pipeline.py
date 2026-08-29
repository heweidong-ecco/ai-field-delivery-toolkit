"""部署加固统一入口"""
"""部署加固管道（增加环境变量检查）"""

import os
import subprocess
from typing import Optional

from core.logging.logger import get_logger

from deploy_hardener.dockerizer import Dockerizer
from deploy_hardener.degradation_presets import DegradationPreset
from deploy_hardener.compose_generator import ComposeGenerator
from deploy_hardener.baremetal_generator import BaremetalGenerator

logger = get_logger()


class DeployHardenerPipeline:
    def __init__(self):
        self.dockerizer = Dockerizer()
        self.compose_gen = ComposeGenerator()
        self.baremetal_gen = BaremetalGenerator()

    def run(
        self,
        project_dir: str,
        output_dir: str,
        mode: str = "docker-compose",    # docker-compose / bare-metal
        image_name: str = "toolkit-app",
        app_path: str = "/opt/toolkit",
    ) -> dict:
        """执行部署加固

        返回:
            包含各步骤结果的字典
        """
        # 0. 部署前环境变量检查（项目自带脚本时执行，否则跳过）
        check_script = os.path.join(project_dir, "deploy_hardener", "pre_deploy_check.sh")
        if os.path.exists(check_script):
            logger.info("执行部署前环境变量检查...")
            result = subprocess.run(["bash", check_script], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"环境变量检查失败：\n{result.stdout}")
                raise ValueError("部署前检查未通过")
            logger.info("环境变量检查通过")
        else:
            logger.warning("未找到 pre_deploy_check.sh，跳过环境变量检查")

        os.makedirs(output_dir, exist_ok=True)

        result = {"mode": mode, "output_dir": output_dir}

        # 1. 生成降级预案
        degradation_path = os.path.join(output_dir, "degradation.yaml")
        DegradationPreset.generate_degradation_yaml(degradation_path)
        result["degradation_config"] = degradation_path

        # 2. 按部署模式生成配置
        if mode == "docker-compose":
            compose_path = self.compose_gen.generate(output_dir, app_image=f"{image_name}:latest")
            result["compose_file"] = compose_path
            # 生成 Dockerfile（如不存在）
            self.dockerizer.generate_dockerfile(project_dir)
            result["dockerfile"] = os.path.join(project_dir, "Dockerfile")
        elif mode == "bare-metal":
            service_path = self.baremetal_gen.generate(output_dir, app_path=app_path)
            result["systemd_service"] = service_path
        else:
            raise ValueError(f"不支持的部署模式: {mode}")

        logger.info(f"部署加固完成: {result}")
        return result