"""统一底座入口：FastAPI 应用"""

from contextlib import asynccontextmanager
from pathlib import Path
import tomllib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.config.settings import get_settings
from core.logging.logger import get_logger
from core.registry import get_registry
from core.db.session import close_engine, get_engine
from core.db.init_db import init_db
from core import api

logger = get_logger()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _package_version() -> str:
    """读取包版本（pyproject.toml [project].version），读不到时回退 "0.0.0" 诚实标注"""
    try:
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("统一底座启动中...")
    # 初始化数据库（可选，生产环境可预先执行 init_db 命令）
    # await init_db()
    yield
    logger.info("统一底座关闭中...")
    await close_engine()


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    settings = get_settings()
    version = _package_version()
    app = FastAPI(
        title="AI 项目现场交付工具包 - 统一底座",
        version=version,
        description="统一底座：配置、安全、日志、版本、降级管理",
        lifespan=lifespan,
    )

    registry = get_registry()

    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {"status": "ok", "version": version, "modules": registry.get_all_modules()}

    @app.post("/api/v1/registry/register")
    async def register_module(name: str):
        """手动注册模块（测试用）"""
        registry.register(name)
        return {"status": "ok", "module": name}

    # 注册功能模块（供 /health 展示）
    for module_name in (
        "diagnosis", "data_prep", "prototype_assembler", "deploy_hardener",
        "monitor", "data_flywheel", "cropper", "retrieval",
    ):
        registry.register(module_name, dependencies=["core"])

    # FDE 操作台：API 路由 + 产物下载 + 前端静态页
    # 注意挂载顺序：/api/v1 路由优先，其次 /artifacts，最后 / 兜底前端
    api.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    Path("web").mkdir(exist_ok=True)
    app.include_router(api.router)
    app.mount("/artifacts", StaticFiles(directory=str(api.ARTIFACT_ROOT)), name="artifacts")
    app.mount("/", StaticFiles(directory="web", html=True), name="web")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)