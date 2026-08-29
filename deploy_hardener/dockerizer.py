"""一键 Docker 化"""

import os
from typing import Optional

from core.logging.logger import get_logger

logger = get_logger()


class Dockerizer:
    """生成 Dockerfile 并构建镜像"""

    def generate_dockerfile(
        self,
        project_dir: str,
        python_version: str = "3.11-slim",
        port: int = 8100,
        require_gpu: bool = False,
    ) -> str:
        """生成 Dockerfile

        参数:
            project_dir: 项目根目录
            python_version: 基础镜像 Python 版本
            port: 服务端口
            require_gpu: 是否需要 GPU（使用 nvidia/cuda 基础镜像）

        返回:
            Dockerfile 路径
        """
        if require_gpu:
            base_image = "nvidia/cuda:12.4.0-runtime-ubuntu22.04"
            python_install_cmd = "apt-get update && apt-get install -y python3.11 python3-pip"
        else:
            base_image = f"python:{python_version}"
            python_install_cmd = ""

        dockerfile_content = f"""FROM {base_image}

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 非 root 用户（安全基线）
RUN useradd -m -u 1000 toolkit
USER toolkit

EXPOSE {port}

CMD ["python", "-m", "core.main"]
"""

        dockerfile_path = os.path.join(project_dir, "Dockerfile")
        with open(dockerfile_path, "w", encoding="utf-8") as f:
            f.write(dockerfile_content)
        logger.info(f"Dockerfile 已生成: {dockerfile_path}")
        return dockerfile_path

    def build_image(self, project_dir: str, image_name: str, tag: str = "latest") -> bool:
        """构建 Docker 镜像"""
        import subprocess
        dockerfile_path = self.generate_dockerfile(project_dir)
        cmd = ["docker", "build", "-t", f"{image_name}:{tag}", "-f", dockerfile_path, project_dir]
        logger.info(f"构建镜像: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("镜像构建成功")
            return True
        else:
            logger.error(f"镜像构建失败: {result.stderr}")
            return False