"""可复用资产注册表持久化：tmp/web/assets/registry.json

注册表是「项目越多、工具越强」的复利底座：dataprep 沉淀的评测集/知识库分块/清洗规则/质量报告、
mapping 导出的映射配置、诊断定稿的诊断方案，都作为可复用资产注册到这里，
下次交付通过 search/suggest 自动带出，一键接入（adopt）到新项目。

条目 schema（只增不改）：
  asset_id      uuid8
  kind          mapping_config | eval_set | kb_chunks | cleaning_rules
                | quality_report | diagnosis_plan | doc_package
  title         展示标题
  summary       一句话说明（可检索）
  tags          [str]
  origin        {run_id, module, case_id?}
  project_id    来源项目
  customer      来源客户
  payload_url   可下载地址（复用 /artifacts 或 /api/v1 路径，不复制 payload）
  payload_path  本机 payload 绝对路径（adopt 时据此读取/复制）
  meta          kind 相关元信息（mapping 的 source/target 字段、eval_set 样本数等）
  created_at    ISO 时间
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# assets/ → 项目根（ai-field-delivery-toolkit/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = PROJECT_ROOT / "tmp" / "web" / "assets"
REGISTRY_PATH = ASSETS_ROOT / "registry.json"

# 合法的 kind 集合（校验注册用）
ALLOWED_KINDS = {
    "mapping_config", "eval_set", "kb_chunks", "cleaning_rules",
    "quality_report", "diagnosis_plan", "doc_package",
}


def new_asset_id() -> str:
    return uuid.uuid4().hex[:8]


def _load_registry() -> list:
    """读取全部资产条目（注册表文件不存在/损坏 → 空列表）"""
    if not REGISTRY_PATH.exists():
        return []
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_registry(items: list) -> None:
    ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def register_asset(
    kind: str,
    title: str,
    summary: str,
    tags: list,
    origin: dict,
    project_id: str = "",
    customer: str = "",
    payload_url: str = "",
    payload_path: str = "",
    meta: dict = None,
) -> dict:
    """注册一条可复用资产；按 (kind, origin.run_id) 幂等去重（重复注册返回既有条目）。

    origin.run_id 为必填业务键（同一 run 的同一类资产只注册一次）。
    """
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"未知资产 kind: {kind}，可选：{'/'.join(sorted(ALLOWED_KINDS))}")
    run_id = (origin or {}).get("run_id")
    if not run_id:
        raise ValueError("注册资产必须提供 origin.run_id（幂等去重键）")

    items = _load_registry()
    for it in items:
        if it.get("kind") == kind and (it.get("origin") or {}).get("run_id") == run_id:
            return it  # 已注册，幂等返回

    entry = {
        "asset_id": new_asset_id(),
        "kind": kind,
        "title": title,
        "summary": summary,
        "tags": list(tags or []),
        "origin": {
            "run_id": run_id,
            "module": (origin or {}).get("module", ""),
            "case_id": (origin or {}).get("case_id"),
        },
        "project_id": project_id or None,
        "customer": customer or "",
        "payload_url": payload_url,
        "payload_path": payload_path,
        "meta": meta or {},
        "created_at": datetime.now().isoformat(),
    }
    items.append(entry)
    _save_registry(items)
    return entry


def list_assets(kind: str = None, limit: int = 50) -> list:
    """列出最近资产（按注册时间倒序）；kind 为空则全部"""
    items = _load_registry()
    if kind:
        items = [it for it in items if it.get("kind") == kind]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def get_asset(asset_id: str) -> dict:
    for it in _load_registry():
        if it.get("asset_id") == asset_id:
            return it
    raise FileNotFoundError(f"资产不存在: {asset_id}")


def search_assets(
    q: str = "",
    kinds: list = None,
    tags: list = None,
    customer: str = "",
    limit: int = 20,
) -> list:
    """按关键词/资产类型/标签/客户过滤资产。

    - q：title/summary/tags 子串匹配（大小写不敏感）
    - kinds：限定 kind 集合（任一命中即可）
    - tags：全部标签须同时命中（与 cases.search_cases 约定一致）
    - customer：客户名精确匹配
    """
    kinds = kinds or []
    tags = tags or []
    q = (q or "").strip().lower()
    customer = (customer or "").strip()
    results = []
    for it in _load_registry():
        if kinds and it.get("kind") not in kinds:
            continue
        if tags and not all(t in it.get("tags", []) for t in tags):
            continue
        if customer and it.get("customer") != customer:
            continue
        if q:
            text = " ".join([
                it.get("title", ""), it.get("summary", ""),
                " ".join(it.get("tags", [])),
            ]).lower()
            if q not in text:
                continue
        results.append(it)
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results[:limit]
