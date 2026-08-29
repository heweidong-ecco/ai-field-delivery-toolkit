"""可复用资产注册/检索/建议/一键接入服务

v6.0 资产复用闭环：
  - register_*：dataprep 沉淀 / mapping 导出 / 诊断定稿时自动把产物注册进资产库
  - suggest：新任务开始时按规则评分自动带出相关资产（确定性、离线、可测）
  - adopt：一键接入历史资产 —— mapping_config 直接预填新映射 run；数据资产复制到目标项目/目标 run
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.logging.logger import get_logger

from assets.archive import get_asset, list_assets, register_asset, search_assets

logger = get_logger()

# ---------- 注册挂接 ----------


def register_from_mapping(run_id: str) -> Optional[dict]:
    """mapping export 成功后把映射配置注册为可复用资产（kind=mapping_config）。

    幂等：同一 run 重复 export 只注册一次。payload_url 指向 adapter/mapping_config.json，
    不复制 payload（复用 /artifacts 静态服务）。
    """
    from mapping.service import get_mapping
    try:
        data = get_mapping(run_id)
    except FileNotFoundError:
        logger.warning(f"mapping 资产注册跳过：run 不存在 {run_id}")
        return None
    name = data.get("name") or run_id
    source_fields = data.get("source_fields", [])
    target_fields = data.get("target_fields", [])
    mappings = data.get("mappings", [])
    project_id = data.get("project_id")
    customer = data.get("customer") or ""

    config_path = Path(__file__).resolve().parent.parent / "tmp" / "web" / "mapping" / run_id / "adapter" / "mapping_config.json"
    adapter_path = Path(__file__).resolve().parent.parent / "tmp" / "web" / "mapping" / run_id / "adapter" / "adapter.py"
    if not config_path.exists():
        logger.warning(f"mapping 资产注册跳过：尚无 adapter/mapping_config.json {run_id}")
        return None

    meta = {
        "source_fields": source_fields,
        "target_fields": target_fields,
        "mapping_count": len(mappings),
        "adapter_path": str(adapter_path),
    }
    return register_asset(
        kind="mapping_config",
        title=f"字段映射配置 · {name}",
        summary=f"源→目标字段映射配置（{len(mappings)} 条），可一键接入预填新映射任务",
        tags=["字段映射", "可复用资产", "集成"],
        origin={"run_id": run_id, "module": "mapping"},
        project_id=project_id,
        customer=customer,
        payload_url=f"/artifacts/mapping/{run_id}/adapter/mapping_config.json",
        payload_path=str(config_path),
        meta=meta,
    )


def register_from_dataprep(run_id: str, asset_type: str, title: str, summary: str,
                           tags: list, payload, payload_url: str, payload_path: str,
                           project_id: str = "", customer: str = "") -> dict:
    """dataprep 沉淀某一类资产后注册进资产库（引用 cases 的 payload_url，不复制 payload）。"""
    meta = {}
    if asset_type == "eval_set":
        if isinstance(payload, dict):
            meta = {
                "sample_count": len(payload.get("eval_set", [])),
                "coverage_stats": payload.get("coverage_stats"),
            }
    elif asset_type == "kb_chunks":
        meta = {
            "chunk_count": payload.get("chunk_count", len(payload.get("chunks", []))) if isinstance(payload, dict) else 0,
        }
    elif asset_type == "quality_report":
        if isinstance(payload, dict):
            meta = {
                "duplicate_rate": payload.get("duplicate_rate"),
                "total": payload.get("total"),
                "unique": payload.get("unique"),
            }
    elif asset_type == "cleaning_rules":
        meta = {"rule_count": len(payload.get("rules", [])) if isinstance(payload, dict) else 0}
    return register_asset(
        kind=asset_type,  # dataprep 的 asset_type 与资产 kind 同名
        title=title,
        summary=summary,
        tags=tags,
        origin={"run_id": run_id, "module": "dataprep"},
        project_id=project_id,
        customer=customer,
        payload_url=payload_url,
        payload_path=payload_path,
        meta=meta,
    )


def register_from_diagnosis(run_id: str, case_id: str, report: dict,
                            customer_name: str = "") -> Optional[dict]:
    """诊断定稿生成交付物后注册 kind=diagnosis_plan（如未注册）。

    复用交付物 HTML 作为可下载 payload，不复制 payload。幂等：同一 run 只注册一次。
    """
    fc = report.get("final_conclusion") or {}
    title = report.get("requirement_summary") or f"需求诊断 {run_id}"
    return register_asset(
        kind="diagnosis_plan",
        title=f"诊断方案 · {report.get('customer_name') or customer_name or '未填写'} · {title}",
        summary=fc.get("conclusion") or "",
        tags=["诊断方案", "可复用资产", "需求诊断"],
        origin={"run_id": run_id, "module": "diagnosis", "case_id": case_id},
        project_id=None,
        customer=customer_name,
        payload_url=f"/api/v1/cases/{case_id}/render.html",
        payload_path="",  # 诊断方案以交付物为准（HTML 可下载）；adopt 时按交付物归档
        meta={
            "version": report.get("version", ""),
            "total_score": fc.get("total_score"),
            "conclusion": fc.get("conclusion", ""),
        },
    )


# ---------- 规则评分建议（自动带出） ----------


def _tokenize(text: str) -> list:
    """把查询文本切成小写关键词：按空白/中英文标点切分 + 去除纯标点片段"""
    text = (text or "").lower()
    parts = re.split(r"[\s,，、;；:：/\\|｜\-—_()（）【】\[\]{}]+", text)
    return [p for p in parts if p and not re.fullmatch(r"[^\w]+", p)]


def _age_days(created_at: str) -> float:
    """资产年龄（天），用于时间衰减；解析失败返回较大值（更旧）"""
    try:
        dt = datetime.fromisoformat(created_at)
    except Exception:
        return 365.0
    return max(0.0, (datetime.now() - dt).total_seconds() / 86400.0)


def _scoring_reason(parts: list, signals: list) -> str:
    """把命中信号拼成人类可读 reason（如「关键词命中2 · 同客户 · 同类资产」）"""
    reason = []
    if parts:
        reason.append(f"关键词命中{len(parts)}处")
    for s in signals:
        reason.append(s)
    return " · ".join(reason) if reason else "最近资产"


def suggest(query: str = "", kinds: List[str] = None, customer: str = "",
            top_k: int = 5) -> list:
    """按规则评分返回相关资产（确定性、可测、离线）。

    候选池：kinds 作为硬过滤（限定资产类型；为空则不过滤）。
    评分构成：
      - 关键词命中：查询分词在 title/summary/tags 的命中次数（+2/词），整串在 title 命中再 +2
      - 标签命中：查询分词与资产标签的重合（+2/标签）
      - 同客户：资产客户与传入 customer 一致 → +3
      - 同类资产：资产 kind 在 kinds 限定内 → +1（叠加在真实相关信号之上）
      - 时间衰减：score *= 1/(1 + 年龄天数/60)（越新分越高）
    仅关键词/标签/同客户信号之一成立才出现（避免纯类型匹配灌水）。
    返回 [{asset, score, reason}]，按 score 降序。
    """
    kinds = kinds or []
    query = (query or "").strip()
    customer = (customer or "").strip()
    tokens = _tokenize(query)
    q_lower = query.lower()

    scored = []
    for it in list_assets(limit=500):
        if kinds and it.get("kind") not in kinds:
            continue  # kinds 硬过滤

        title = it.get("title", "")
        summary = it.get("summary", "")
        tags = it.get("tags", [])
        text = " ".join([title, summary, " ".join(tags)]).lower()

        hits = 0
        matched = set()
        for t in tokens:
            if t in text:
                hits += 2
                matched.add(t)
        if q_lower and q_lower in title.lower():
            hits += 2
        tag_hits = sum(1 for t in tokens if t in [x.lower() for x in tags])
        hits += tag_hits * 2

        base = float(hits)
        signals = []

        if it.get("customer") and it.get("customer") == customer:
            base += 3
            signals.append("同客户")

        # 真实相关信号必须成立（关键词/标签/同客户），否则纯类型匹配不算建议
        if base <= 0:
            continue

        if kinds and it.get("kind") in kinds:
            base += 1
            signals.append("同类资产")

        decay = 1.0 / (1.0 + _age_days(it.get("created_at", "")) / 60.0)
        score = base * decay
        scored.append({
            "asset": it,
            "score": round(score, 4),
            "reason": _scoring_reason(sorted(matched), signals),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ---------- 一键接入 ----------


def _resolve_project(project_id: str, customer: str) -> Optional[str]:
    """显式 project_id 优先；否则按客户名自动建/复用项目（与 mapping/dataprep 约定一致）"""
    if project_id:
        return project_id
    if not customer or customer in ("未填写", ""):
        return None
    from projects.archive import create_project, list_projects
    name = f"{customer} 项目"
    for p in list_projects():
        if p.get("customer") == customer or p.get("name") == name:
            return p["project_id"]
    return create_project(name, customer)["project_id"]


def _add_project_event(pid: Optional[str], etype: str, title: str, detail: str = "", ref: str = None) -> None:
    if not pid:
        return
    try:
        from projects.archive import add_event
        add_event(pid, etype, title, detail, ref)
    except Exception as e:  # 项目档案失败不阻断接入
        logger.warning(f"挂项目档案失败 project_id={pid}: {e}")


def _read_payload(asset: dict):
    """读取资产 payload（mapping_config.json 或数据资产 JSON）；路径缺失返回 None"""
    p = Path(asset.get("payload_path") or "")
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"资产 payload 读取失败 {asset.get('asset_id')}: {e}")
        return None


def adopt_mapping_config(asset: dict, project_id: str = "", customer: str = "") -> dict:
    """旗舰接入：读历史映射配置 → 用其源/目标字段 + 映射预填新映射 run（状态 draft）。

    不复制 payload —— 把历史字段与映射注入新建 run，可继续导入新样例/校验/修正。
    """
    from mapping.service import create_mapping

    config = _read_payload(asset)
    if config is None:
        raise ValueError(f"映射配置资产 payload 缺失：{asset.get('payload_path')}（可先去原 run 导出）")

    meta = asset.get("meta", {}) or {}
    source_fields = list(meta.get("source_fields") or [])
    target_fields = list(meta.get("target_fields") or [])
    mappings = config.get("mappings") or []

    # 兜底：meta 缺字段时从 mappings 反推（targets 必有，sources 尽力）
    if not source_fields:
        seen = set()
        for m in mappings:
            s = m.get("source")
            if s and s not in seen:
                seen.add(s)
                source_fields.append({"name": s, "sample": ""})
    if not target_fields:
        seen = set()
        for m in mappings:
            t = m.get("target")
            if t and t not in seen:
                seen.add(t)
                target_fields.append({"name": t, "sample": ""})

    name = f"{asset.get('title', '历史映射')}（一键接入）"
    run = create_mapping(
        name,
        source_fields,
        target_fields,
        project_id=project_id,
        customer=customer or asset.get("customer", ""),
        prefill_mappings=mappings,
    )
    run_id = run["run_id"]
    pid = run.get("project_id")
    _add_project_event(pid, "asset_reuse", f"一键接入历史映射 · {asset.get('title', '')}",
                       detail=f"{len(mappings)} 条映射已预填 ｜ asset_id={asset.get('asset_id')} ｜ run_id={run_id}",
                       ref=run_id)
    logger.info(f"一键接入 mapping_config asset_id={asset.get('asset_id')} → run_id={run_id}")
    return {
        "run_id": run_id,
        "url": f"/api/v1/mapping/{run_id}",
        "mappings": run.get("mappings", []),
        "prefilled_from_asset": asset.get("asset_id"),
    }


def adopt_data_asset(asset: dict, project_id: str = "", customer: str = "",
                     target_run_id: str = "") -> dict:
    """数据类资产接入：把 payload 复制到目标 dataprep run 的 products（供继续用），并挂项目事件。

    未给 target_run_id 时仅注册为项目下的资产引用（项目事件 asset_reuse），不造假数据。
    """
    from dataprep.archive import load_run, products_dir, update_run

    payload = _read_payload(asset)
    if payload is None:
        raise ValueError(f"数据资产 payload 缺失：{asset.get('payload_path')}")

    pid = _resolve_project(project_id, customer or asset.get("customer", ""))
    written = None

    if target_run_id:
        run = load_run(target_run_id)
        if run is None:
            raise ValueError(f"目标数据作战流任务不存在: {target_run_id}")
        d = products_dir(target_run_id)
        d.mkdir(parents=True, exist_ok=True)
        filename = f"reused_{asset.get('kind')}.json"
        with open(d / filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        products = dict(run.get("products", {}))
        products[f"reused_{asset.get('kind')}"] = filename
        update_run(target_run_id, products=products)
        written = str(d / filename)

    _add_project_event(pid, "asset_reuse", f"接入数据资产 · {asset.get('title', '')}",
                       detail=f"kind={asset.get('kind')} ｜ asset_id={asset.get('asset_id')}"
                              + (f" ｜ 写入 run={target_run_id}" if target_run_id else ""),
                       ref=target_run_id or asset.get("asset_id"))
    logger.info(f"一键接入数据资产 asset_id={asset.get('asset_id')} kind={asset.get('kind')} target_run_id={target_run_id or '无'}")
    return {
        "adopted": True,
        "asset_id": asset.get("asset_id"),
        "kind": asset.get("kind"),
        "project_id": pid,
        "target_run_id": target_run_id or None,
        "written_path": written,
        "note": "payload 已写入目标 run 的 products（可继续使用）" if written else "已登记为项目资产引用（未复制 payload）",
    }


def adopt_reference(asset: dict, project_id: str = "", customer: str = "") -> dict:
    """交付物类资产（诊断方案/文档包）接入：无 JSON payload 可复制，登记为项目资产引用 + 事件。

    交付物 HTML/PDF 通过 payload_url 下载，不造假数据。
    """
    pid = _resolve_project(project_id, customer or asset.get("customer", ""))
    _add_project_event(pid, "asset_reuse", f"接入交付物资产 · {asset.get('title', '')}",
                       detail=f"kind={asset.get('kind')} ｜ asset_id={asset.get('asset_id')}",
                       ref=asset.get("asset_id"))
    logger.info(f"一键接入交付物资产 asset_id={asset.get('asset_id')} kind={asset.get('kind')}")
    return {
        "adopted": True,
        "asset_id": asset.get("asset_id"),
        "kind": asset.get("kind"),
        "project_id": pid,
        "note": "交付物类资产：已登记项目资产引用（payload 经 payload_url 下载）",
    }


def adopt_asset(asset_id: str, project_id: str = "", customer: str = "",
                target_run_id: str = "") -> dict:
    """按 kind 分发一键接入。"""
    asset = get_asset(asset_id)
    if asset.get("kind") == "mapping_config":
        return adopt_mapping_config(asset, project_id=project_id, customer=customer)
    if asset.get("kind") in ("diagnosis_plan", "doc_package"):
        return adopt_reference(asset, project_id=project_id, customer=customer)
    # 其余数据类资产（eval_set / kb_chunks / cleaning_rules / quality_report）
    return adopt_data_asset(asset, project_id=project_id, customer=customer, target_run_id=target_run_id)


__all__ = [
    "adopt_asset",
    "adopt_data_asset",
    "adopt_mapping_config",
    "adopt_reference",
    "register_from_dataprep",
    "register_from_diagnosis",
    "register_from_mapping",
    "search_assets",
    "suggest",
]
