"""生成 Docker Compose 配置"""

from core.logging.logger import get_logger

logger = get_logger()


class ComposeGenerator:
    """生成 docker-compose.yml"""

    def generate(self, output_dir: str, app_image: str = "toolkit-app:latest") -> str:
        """生成 docker-compose.yml"""
        import yaml
        compose = {
            "version": "3.8",
            "services": {
                "app": {
                    "image": app_image,
                    "ports": ["8100:8100"],
                    "environment": [
                        "POSTGRES_HOST=postgres",
                        "REDIS_URL=redis://redis:6379/0",
                    ],
                    "depends_on": ["postgres", "redis"],
                    "restart": "unless-stopped",
                },
                "postgres": {
                    "image": "postgres:16-alpine",
                    "environment": [
                        "POSTGRES_USER=toolkit",
                        "POSTGRES_PASSWORD=change_me",
                        "POSTGRES_DB=toolkit",
                    ],
                    "volumes": ["postgres_data:/var/lib/postgresql/data"],
                    "restart": "unless-stopped",
                },
                "redis": {
                    "image": "redis:7-alpine",
                    "restart": "unless-stopped",
                },
            },
            "volumes": {
                "postgres_data": None,
            },
        }

        path = f"{output_dir}/docker-compose.yml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(compose, f, allow_unicode=True)
        logger.info(f"docker-compose.yml 已生成: {path}")
        return path