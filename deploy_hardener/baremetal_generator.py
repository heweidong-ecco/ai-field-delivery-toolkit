"""生成裸机 systemd 服务文件"""

from core.logging.logger import get_logger

logger = get_logger()


class BaremetalGenerator:
    """生成 systemd 服务文件（无 Docker 场景）"""

    def generate(self, output_dir: str, app_path: str = "/opt/toolkit") -> str:
        """生成 systemd 服务文件"""
        service_content = f"""[Unit]
Description=AI Field Delivery Toolkit
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=toolkit
WorkingDirectory={app_path}
ExecStart={app_path}/venv/bin/python -m core.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""

        path = f"{output_dir}/toolkit.service"
        with open(path, "w", encoding="utf-8") as f:
            f.write(service_content)
        logger.info(f"systemd 服务文件已生成: {path}")
        return path