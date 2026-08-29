"""案例档案存储：tmp/web/cases/<case_id>/

- deliverable.html / deliverable.pdf：可打印交付物
- archive.json：结构化案例元数据（供检索/回溯）
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# cases/ → 项目根（ai-field-delivery-toolkit/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_ROOT = PROJECT_ROOT / "tmp" / "web" / "cases"


def new_case_id() -> str:
    return uuid.uuid4().hex[:8]


def case_dir(case_id: str) -> Path:
    return CASES_ROOT / case_id


def archive_path(case_id: str) -> Path:
    return case_dir(case_id) / "archive.json"


def save_case(case_id: str, metadata: dict, html: str = None, pdf: bytes = None) -> Path:
    d = case_dir(case_id)
    d.mkdir(parents=True, exist_ok=True)
    if html:
        (d / "deliverable.html").write_text(html, encoding="utf-8")
    if pdf:
        (d / "deliverable.pdf").write_bytes(pdf)
    with open(archive_path(case_id), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return archive_path(case_id)


def load_case(case_id: str) -> dict:
    p = archive_path(case_id)
    if not p.exists():
        raise FileNotFoundError(f"案例不存在: {case_id}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def list_cases(limit: int = 50) -> list:
    """列出最近案例（含元数据，供三期检索）"""
    if not CASES_ROOT.exists():
        return []
    cases = []
    for p in CASES_ROOT.iterdir():
        if p.is_dir() and (p / "archive.json").exists():
            try:
                meta = load_case(p.name)
                meta["case_id"] = p.name
                cases.append((p.name, (p / "archive.json").stat().st_mtime, meta))
            except Exception:
                continue
    cases.sort(key=lambda x: x[1], reverse=True)
    return [c[2] for c in cases[:limit]]


def search_cases(query: str = "", tags: list = None, limit: int = 20) -> list:
    """按关键词/标签检索案例（三期 Agent 记忆的基础）"""
    tags = tags or []
    results = []
    for meta in list_cases(limit=500):
        text = " ".join([
            meta.get("title", ""), meta.get("conclusion", ""),
            meta.get("summary", ""), " ".join(meta.get("tags", [])),
        ]).lower()
        if query and query.lower() not in text:
            continue
        if tags and not all(t in meta.get("tags", []) for t in tags):
            continue
        results.append(meta)
    return results[:limit]
