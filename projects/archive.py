"""项目档案存储：tmp/web/projects/<project_id>/archive.json

项目 = 完整操作流程与过程记录的「去处」：诊断/会议/现场问题/迭代/交付物都作为事件挂到项目时间线。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# projects/ → 项目根（ai-field-delivery-toolkit/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = PROJECT_ROOT / "tmp" / "web" / "projects"


def new_project_id() -> str:
    return uuid.uuid4().hex[:8]


def project_dir(pid: str) -> Path:
    return PROJECTS_ROOT / pid


def archive_path(pid: str) -> Path:
    return project_dir(pid) / "archive.json"


def _write(pid: str, data: dict) -> None:
    project_dir(pid).mkdir(parents=True, exist_ok=True)
    with open(archive_path(pid), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_project(name: str, customer: str = "") -> dict:
    pid = new_project_id()
    proj = {
        "project_id": pid,
        "name": name,
        "customer": customer,
        "events": [],
        "created_at": datetime.now().isoformat(),
    }
    _write(pid, proj)
    return proj


def get_project(pid: str) -> dict:
    p = archive_path(pid)
    if not p.exists():
        raise FileNotFoundError(f"项目不存在: {pid}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def add_event(pid: str, etype: str, title: str, detail: str = "", ref: str = None) -> dict:
    proj = get_project(pid)
    ev = {
        "id": len(proj.get("events", [])) + 1,
        "type": etype,           # diagnosis / case / meeting / issue / iteration / note
        "title": title,
        "detail": detail,
        "ref": ref,
        "created_at": datetime.now().isoformat(),
    }
    proj["events"].append(ev)
    _write(pid, proj)
    return ev


def list_projects(limit: int = 50) -> list:
    if not PROJECTS_ROOT.exists():
        return []
    projects = []
    for p in PROJECTS_ROOT.iterdir():
        if p.is_dir() and (p / "archive.json").exists():
            try:
                with open(p / "archive.json", "r", encoding="utf-8") as f:
                    proj = json.load(f)
                projects.append((p.name, (p / "archive.json").stat().st_mtime, proj))
            except Exception:
                continue
    projects.sort(key=lambda x: x[1], reverse=True)
    return [p[2] for p in projects[:limit]]
