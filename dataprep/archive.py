"""数据作战流档案：按 run_id 落盘 JSON + 断点续接状态

存储位置：tmp/web/dataprep/<run_id>/archive.json（已 gitignore）
字段：name(人工命名) / project_id / customer / source(文件名) / status
      / steps[]（每步状态与产物） / products{key: 产物文件名} / deposited_assets[]
      / created_at / updated_at

仿 diagnosis.archive 的 create_run/load_run/update_run/rename_run/list_run_ids 模式。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from core.logging.logger import get_logger

logger = get_logger()

# dataprep/ → 项目根（ai-field-delivery-toolkit/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = PROJECT_ROOT / "tmp" / "web" / "dataprep"

# 六步流水线顺序
STEPS = ["import", "clean", "quality", "annotate", "eval_set", "knowledge_base"]
STEP_NAMES = {
    "import": "导入数据",
    "clean": "清洗",
    "quality": "质量报告",
    "annotate": "标注",
    "eval_set": "评测集",
    "knowledge_base": "知识库",
}


def run_dir(run_id: str) -> Path:
    return ARCHIVE_ROOT / run_id


def products_dir(run_id: str) -> Path:
    return run_dir(run_id) / "products"


def archive_path(run_id: str) -> Path:
    return run_dir(run_id) / "archive.json"


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


def create_run(run_id: str, data: Dict) -> Path:
    """创建档案文件（幂等）"""
    run_dir(run_id).mkdir(parents=True, exist_ok=True)
    products_dir(run_id).mkdir(parents=True, exist_ok=True)
    path = archive_path(run_id)
    if not path.exists():
        now = datetime.now().isoformat()
        data.setdefault("name", f"数据任务 {run_id}")
        data.setdefault("status", "created")
        data.setdefault("steps", [])
        data.setdefault("products", {})
        data.setdefault("deposited_assets", [])
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        _write(run_id, data)
    return path


def load_run(run_id: str) -> Optional[Dict]:
    path = archive_path(run_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_run(run_id: str, **fields) -> Dict:
    """读取并更新档案，写回；不存在则报错"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"数据作战流任务不存在: {run_id}")
    data.update(fields)
    data["updated_at"] = datetime.now().isoformat()
    _write(run_id, data)
    return data


def rename_run(run_id: str, name: str) -> Dict:
    """人工命名"""
    return update_run(run_id, name=name.strip())


def _write(run_id: str, data: Dict) -> None:
    path = archive_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_run_ids(limit: int = 20) -> list:
    """列出最近 run_id（按文件 mtime 倒序）"""
    if not ARCHIVE_ROOT.exists():
        return []
    runs = []
    for p in ARCHIVE_ROOT.iterdir():
        if p.is_dir() and (p / "archive.json").exists():
            runs.append((p.name, (p / "archive.json").stat().st_mtime))
    runs.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in runs[:limit]]


def done_steps(run_id: str) -> list:
    """返回已完成步骤名列表（断点续接用）"""
    data = load_run(run_id) or {}
    return [s["step"] for s in data.get("steps", []) if s.get("status") == "done"]


def next_step(run_id: str) -> Optional[str]:
    """返回下一个未完成步骤（全部完成返回 None）"""
    done = set(done_steps(run_id))
    for s in STEPS:
        if s not in done:
            return s
    return None


def mark_step(run_id: str, step: str, **extra) -> Dict:
    """记录某步已完成（可覆盖），并按 STEPS 顺序排 steps[]"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"数据作战流任务不存在: {run_id}")
    entry = {
        "step": step,
        "name": STEP_NAMES.get(step, step),
        "status": "done",
        "at": datetime.now().isoformat(),
        **extra,
    }
    steps = [s for s in data.get("steps", []) if s.get("step") != step] + [entry]
    steps.sort(key=lambda s: STEPS.index(s["step"]) if s["step"] in STEPS else len(STEPS))
    status = "completed" if all(s in {x["step"] for x in steps} for s in STEPS) else "running"
    data.update(steps=steps, status=status, updated_at=datetime.now().isoformat())
    _write(run_id, data)
    return data
