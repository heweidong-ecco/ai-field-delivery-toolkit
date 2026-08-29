"""数据作战流服务：以项目为单位、可断点续接、产物沉淀复用

六步流水线（每步可单独执行、可续接，产物落盘进档案，刷新/重连不丢）：
  1. import_data      导入数据（csv/json 真实数据；检测源类型、记录行数）
  2. clean            清洗（字符去重 + 语义去重 + 异常过滤 + 归一化 + PII 脱敏）
  3. quality_report   质量报告（DataQualityEvaluator）
  4. annotate         标注（复用 annotation：建任务 + 双人打标签 + 一致性 → 一致样本评测集）
  5. eval_set         评测集（EvalSetBuilder，纯规则，不用 LLM）
  6. knowledge_base   知识库（kb.service 分块 + 质检，纯规则，不用 LLM）

全部步骤纯规则/现成模块，不依赖 LLM。任务创建时挂项目档案（project event）。
产物沉淀：清洗规则说明 / 评测集 / 知识库分块 / 质量报告 → cases/archive 带标签沉淀，search_cases 可检索。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from core.logging.logger import get_logger

from dataprep.archive import (
    STEPS, STEP_NAMES, create_run, done_steps, load_run,
    mark_step, new_run_id, next_step, products_dir, run_dir, update_run,
)

logger = get_logger()


# ---------- 小工具 ----------


def _add_project_event(pid: Optional[str], etype: str, title: str, detail: str = "", ref: str = None) -> None:
    if not pid:
        return
    try:
        from projects.archive import add_event
        add_event(pid, etype, title, detail, ref)
    except Exception as e:  # 项目档案失败不阻断数据流
        logger.warning(f"挂项目档案失败 project_id={pid}: {e}")


def _write_product(run_id: str, key: str, filename: str, payload) -> str:
    """写产物到 products 目录，返回相对文件名；同时登记到档案 products{key: filename}"""
    d = products_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    products = dict(load_run(run_id).get("products", {}))
    products[key] = filename
    update_run(run_id, products=products)
    return filename


def _load_product(run_id: str, key: str):
    """读产物（dict/list/None）"""
    data = load_run(run_id)
    if data is None:
        return None
    filename = (data.get("products") or {}).get(key)
    if not filename:
        return None
    p = products_dir(run_id) / filename
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _detect_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    raise ValueError(f"不支持的文件类型（{suffix or '无扩展名'}），数据作战流支持 csv/json")


# ---------- 1. 导入数据 ----------


def import_data(run_id: str, source_path: str, upload_filename: str = "") -> dict:
    """导入 csv/json 真实数据：检测源类型、记录行数、保存 raw_data.json + source_info"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"数据作战流任务不存在: {run_id}")
    src = Path(source_path)
    source_type = _detect_source(src)

    if source_type == "csv":
        from data_prep.ingestion.csv_loader import CSVLoader
        ingest = CSVLoader().ingest(str(src))["data"]
    else:
        from data_prep.ingestion.json_loader import JSONLoader
        ingest = JSONLoader().ingest(str(src))["data"]

    if not ingest:
        raise ValueError("文件中没有可导入的数据记录（仅表头或空文件）")

    columns = []
    if ingest and isinstance(ingest[0].get("metadata"), dict):
        columns = list(ingest[0]["metadata"].keys())

    source_info = {
        "filename": upload_filename or src.name,
        "source_type": source_type,
        "row_count": len(ingest),
        "columns": columns,
        "sample": ingest[:3],
    }
    _write_product(run_id, "raw_data", "raw_data.json", ingest)
    _write_product(run_id, "source_info", "source_info.json", source_info)
    mark_step(run_id, "import", product="raw_data.json", row_count=len(ingest), source_type=source_type)
    logger.info(f"数据作战流 导入完成 run_id={run_id} 行数={len(ingest)}")
    return {"step": "import", "row_count": len(ingest), "source_type": source_type}


# ---------- 2. 清洗 ----------


def clean_step(run_id: str) -> dict:
    """清洗：字符去重 + 语义去重 + 异常过滤 + 归一化 + PII 脱敏"""
    raw = _load_product(run_id, "raw_data")
    if raw is None:
        raise ValueError("尚无原始数据，请先执行导入步骤")

    from data_prep.cleaning.cleaner import DataCleaner
    cleaned, stats = DataCleaner().clean(
        raw,
        dedup_similarity=None,   # 字符级：完全一致去重
        semantic_dedup=True,     # 语义去重（本机已缓存嵌入模型）
        semantic_threshold=0.85,
    )
    _write_product(run_id, "cleaned_data", "cleaned_data.json", cleaned)
    _write_product(run_id, "cleaning_stats", "cleaning_stats.json", stats)
    mark_step(run_id, "clean", product="cleaned_data.json", stats=stats)
    logger.info(f"数据作战流 清洗完成 run_id={run_id} 清洗后={len(cleaned)}")
    return {"step": "clean", "cleaned_count": len(cleaned), "stats": stats}


# ---------- 3. 质量报告 ----------


def quality_step(run_id: str) -> dict:
    """质量报告：DataQualityEvaluator"""
    cleaned = _load_product(run_id, "cleaned_data")
    if cleaned is None:
        raise ValueError("尚无清洗后数据，请先执行清洗步骤")

    from data_prep.quality.evaluator import DataQualityEvaluator
    report = DataQualityEvaluator().evaluate(cleaned)
    report_dict = report.to_dict()
    _write_product(run_id, "quality_report", "quality_report.json", report_dict)
    mark_step(run_id, "quality", product="quality_report.json", report=report_dict)
    logger.info(f"数据作战流 质量报告完成 run_id={run_id} 重复率={report_dict['duplicate_rate']}")
    return {"step": "quality", "report": report_dict}


# ---------- 4. 标注（双人打标签 → 一致性 → 一致样本评测集） ----------


def _rule_label(content: str, annotator: str) -> str:
    """确定性规则标注（纯规则，不用 LLM）：按关键词分类；双人用不同长度阈值制造少量分歧以体现一致性统计"""
    c = (content or "").lower()
    if any(k in c for k in ("温度", "temperature", "temp")):
        return "温度记录"
    if any(k in c for k in ("压力", "pressure")):
        return "压力记录"
    if any(k in c for k in ("转速", "speed", "rpm")):
        return "转速记录"
    if any(k in c for k in ("库存", "stock", "仓库", "货架")):
        return "库存记录"
    if any(k in c for k in ("订单", "order", "销售", "sku")):
        return "销售记录"
    # 其余按长度分类（A/B 阈值略不同 → 产生少量分歧样本）
    threshold = 120 if annotator == "A" else 100
    return "正常" if len(c) < threshold else "长文本"


def annotate_step(run_id: str, sample_size: int = 20) -> dict:
    """标注：建任务（复用 annotation.service）→ 双人打标签 → 看一致性 → 一致样本评测集落盘"""
    cleaned = _load_product(run_id, "cleaned_data")
    if cleaned is None:
        raise ValueError("尚无清洗后数据，请先执行清洗步骤")

    import annotation.service as ann

    data = load_run(run_id)
    sample = cleaned[: max(2, int(sample_size))]
    items = [it.get("content", "") for it in sample]
    items = [c for c in items if c.strip()]
    if not items:
        raise ValueError("无可用标注样本")

    task = ann.create_annotation_task(f"数据作战流-标注-{data.get('name', run_id)}", items)
    ann_run = task["run_id"]

    # 双人打标签（规则确定性，一次成对）
    for it in task["items"]:
        ann.add_label(ann_run, it["id"], "A", _rule_label(it["content"], "A"))
        ann.add_label(ann_run, it["id"], "B", _rule_label(it["content"], "B"))

    task_stats = (ann.get_task(ann_run) or {}).get("stats", {})
    eval_result = ann.build_eval_set(ann_run, str(products_dir(run_id) / "annotation_eval_set.json"))

    summary = {
        "annotation_run_id": ann_run,
        "total": task_stats.get("total", 0),
        "agreed": eval_result["agreed"],
        "disagreed": eval_result["disagreements"],
        "product": "annotation_eval_set.json",
    }
    _write_product(run_id, "annotation_eval_set", "annotation_eval_set.json", eval_result)
    mark_step(run_id, "annotate", **summary)
    logger.info(f"数据作战流 标注完成 run_id={run_id} 一致={eval_result['agreed']} 分歧={eval_result['disagreements']}")
    return {"step": "annotate", **summary}


# ---------- 5. 评测集（EvalSetBuilder） ----------


def eval_set_step(run_id: str, num_samples: int = 100) -> dict:
    """评测集：EvalSetBuilder（纯规则，不用 LLM）"""
    cleaned = _load_product(run_id, "cleaned_data")
    if cleaned is None:
        raise ValueError("尚无清洗后数据，请先执行清洗步骤")

    from data_prep.eval_builder.builder import EvalSetBuilder
    result = EvalSetBuilder().build(cleaned, num_samples=num_samples)
    _write_product(run_id, "eval_set", "eval_set.json", result)
    mark_step(run_id, "eval_set", product="eval_set.json", sample_count=len(result["eval_set"]))
    logger.info(f"数据作战流 评测集完成 run_id={run_id} 样本={len(result['eval_set'])}")
    return {"step": "eval_set", "eval_set_count": len(result["eval_set"]), "coverage_stats": result["coverage_stats"]}


# ---------- 6. 知识库（分块 + 质检） ----------


def kb_step(run_id: str, chunk_size: int = 500, overlap: int = 50) -> dict:
    """知识库：kb.service 分块 + 质检（纯规则，不用 LLM）→ 自动索引进检索（RAG 就绪）"""
    cleaned = _load_product(run_id, "cleaned_data")
    if cleaned is None:
        raise ValueError("尚无清洗后数据，请先执行清洗步骤")

    from kb.service import chunk_text, quality_check

    chunks = []
    for it in cleaned:
        chunks.extend(chunk_text(it.get("content", ""), chunk_size=chunk_size, overlap=overlap))
    # 分块去重（同一文本反复出现的段落只保留一份）
    seen, unique = set(), []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    chunks = unique

    quality = quality_check(chunks)

    # 自动建索引（v5.0：数据作战流 → 知识库 → RAG 就绪 闭环）；失败不阻断流程
    indexed = False
    collection = None
    try:
        from retrieval.service import index_knowledge
        idx = index_knowledge(run_id, chunks)
        indexed, collection = True, idx["collection"]
    except Exception as e:
        logger.warning(f"数据作战流 知识库自动索引失败 run_id={run_id}: {e}")

    payload = {
        "chunk_count": len(chunks),
        "chunk_size": chunk_size,
        "overlap": overlap,
        "chunks": chunks,
        "quality": quality,
        "indexed": indexed,
        "collection": collection,
    }
    _write_product(run_id, "chunks", "chunks.json", payload)
    mark_step(run_id, "knowledge_base", product="chunks.json", chunk_count=len(chunks), quality=quality,
              indexed=indexed, collection=collection)
    logger.info(f"数据作战流 知识库分块完成 run_id={run_id} 分块={len(chunks)} indexed={indexed}")
    return {"step": "knowledge_base", "chunk_count": len(chunks), "quality": quality,
            "indexed": indexed, "collection": collection}


def load_kb_chunks(run_id: str) -> Optional[list]:
    """读取数据作战流知识库分块产物（供检索模块索引 / 重建索引使用）；无产物返回 None"""
    payload = _load_product(run_id, "chunks")
    if payload is None:
        return None
    return payload.get("chunks")


STEP_FN = {
    "import": import_data,
    "clean": clean_step,
    "quality": quality_step,
    "annotate": annotate_step,
    "eval_set": eval_set_step,
    "knowledge_base": kb_step,
}


# ---------- 任务生命周期 ----------


def start_task(
    name: str = "",
    source_path: str = "",
    project_id: Optional[str] = None,
    customer: str = "",
    upload_filename: str = "",
    auto_first_three: bool = True,
) -> dict:
    """新建数据作战流任务：建档案 → 导入 → （自动）清洗 + 质量，返回可恢复状态"""
    run_id = new_run_id()
    src = Path(source_path)
    display_name = (name or upload_filename or src.name or f"数据任务 {run_id}").strip()
    create_run(run_id, {
        "name": display_name,
        "project_id": project_id,
        "customer": customer,
        "source": upload_filename or src.name,
        "status": "created",
    })

    # 挂项目档案
    if project_id:
        _add_project_event(project_id, "dataprep",
                           f"数据作战流 · {display_name}",
                           detail=f"数据源：{upload_filename or src.name} ｜ run_id={run_id}", ref=run_id)

    import_data(run_id, source_path, upload_filename=upload_filename)
    if auto_first_three:
        clean_step(run_id)
        quality_step(run_id)
    return get_state(run_id)


def continue_step(run_id: str, step: Optional[str] = None, **kwargs) -> dict:
    """断点续接：执行指定步骤（或 run_next 顺序推进下一步），返回最新状态；已完成步骤跳过不重跑"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"数据作战流任务不存在: {run_id}")
    done = set(done_steps(run_id))

    if step is None:
        step = next_step(run_id)
        if step is None:
            return get_state(run_id)  # 全部完成
    if step not in STEP_FN:
        raise ValueError(f"未知步骤: {step}，可选：{'/'.join(STEPS)}")
    if step in done:
        return get_state(run_id)  # 该步已完成，直接返回状态

    STEP_FN[step](run_id, **kwargs)
    return get_state(run_id)


def get_state(run_id: str) -> dict:
    """返回可恢复的数据作战流状态（断点续接入口）"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"数据作战流任务不存在: {run_id}")
    steps = data.get("steps", [])
    done = [s["step"] for s in steps if s.get("status") == "done"]

    products = {}
    for key, filename in (data.get("products") or {}).items():
        rel = Path(filename).name
        products[key] = {
            "filename": rel,
            "path": str(products_dir(run_id) / rel),
            "url": f"/artifacts/dataprep/{run_id}/products/{rel}",
            "exists": (products_dir(run_id) / rel).exists(),
        }

    return {
        "run_id": run_id,
        "name": data.get("name", ""),
        "project_id": data.get("project_id"),
        "customer": data.get("customer", ""),
        "source": data.get("source", ""),
        "status": data.get("status", "created"),
        "steps": steps,
        "done_steps": done,
        "progress": len(done),
        "progress_total": len(STEPS),
        "next_step": next_step(run_id),
        "products": products,
        "deposited_assets": data.get("deposited_assets", []),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
    }


def rename_task(run_id: str, name: str) -> dict:
    """人工命名"""
    from dataprep.archive import rename_run
    rename_run(run_id, name)
    return get_state(run_id)


def list_tasks(limit: int = 20) -> list:
    """列出最近任务（含名字/状态/进度/可恢复状态）"""
    from dataprep.archive import list_run_ids
    runs = []
    for rid in list_run_ids(limit):
        try:
            runs.append(get_state(rid))
        except FileNotFoundError:
            continue
    return runs


# ---------- 资产沉淀（可复用资产，search_cases 可检索） ----------


def _deposit_one(run_id: str, asset_type: str, title: str, conclusion: str,
                 summary: str, tags: list, payload) -> dict:
    from cases.archive import case_dir, new_case_id, save_case

    case_id = new_case_id()
    d = case_dir(case_id)
    d.mkdir(parents=True, exist_ok=True)
    asset_path = d / "asset.json"
    with open(asset_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    data = load_run(run_id) or {}
    meta = {
        "case_id": case_id,
        "source_type": "dataprep_asset",
        "asset_type": asset_type,
        "run_id": run_id,
        "project_id": data.get("project_id"),
        "title": title,
        "conclusion": conclusion,
        "summary": summary,
        "tags": tags,
        "payload_path": str(asset_path),
        "payload_url": f"/artifacts/cases/{case_id}/asset.json",
        "created_at": datetime.now().isoformat(),
    }
    save_case(case_id, meta)
    # v6.0：沉淀后同步注册进可复用资产库（引用 cases 的 payload_url，不复制 payload）；失败不阻断沉淀
    try:
        from assets.service import register_from_dataprep
        register_from_dataprep(
            run_id, asset_type, title, summary, tags, payload,
            payload_url=meta["payload_url"], payload_path=meta["payload_path"],
            project_id=data.get("project_id"), customer=data.get("customer") or "",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"数据资产注册失败 run_id={run_id} type={asset_type}: {e}")
    return meta


def deposit(run_id: str) -> dict:
    """把评测集 / 知识库分块 / 清洗规则说明 / 质量报告 沉淀为带标签可复用资产（cases/archive），可被 search_cases 检索"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"数据作战流任务不存在: {run_id}")
    name = data.get("name") or run_id
    project_id = data.get("project_id")
    deposited = list(data.get("deposited_assets", []))
    existing_types = {a["asset_type"] for a in deposited}
    results = []

    # 1. 评测集（EvalSetBuilder 产物）
    eval_set = _load_product(run_id, "eval_set")
    if eval_set is not None and "eval_set" not in existing_types:
        count = len(eval_set.get("eval_set", [])) if isinstance(eval_set, dict) else len(eval_set)
        m = _deposit_one(
            run_id, "eval_set", f"评测集 · {name}",
            f"评测集 {count} 条",
            "数据作战流清洗后构建的可复用评测集（instruction/output 结构，可喂模型微调/评测）",
            ["数据准备", "评测集", "可复用资产"], eval_set)
        results.append(m); deposited.append(m)

    # 2. 知识库分块（kb.service 分块 + 质检）
    chunks = _load_product(run_id, "chunks")
    if chunks is not None and "kb_chunks" not in existing_types:
        count = chunks.get("chunk_count", len(chunks.get("chunks", [])))
        m = _deposit_one(
            run_id, "kb_chunks", f"知识库分块 · {name}",
            f"分块 {count} 块",
            "数据作战流产出的可复用知识库分块（含质检报告），下次同类数据直接复用分块方案",
            ["数据准备", "知识库分块", "可复用资产"], chunks)
        results.append(m); deposited.append(m)

    # 3. 清洗规则说明（清洗统计 + 源信息）
    if "cleaning_rules" not in existing_types:
        stats = _load_product(run_id, "cleaning_stats") or {}
        source_info = _load_product(run_id, "source_info") or {}
        rules_payload = {
            "run_id": run_id,
            "rules": [
                "字符级去重（完全一致）",
                "语义去重（向量相似度，阈值 0.85）",
                "格式归一化（压缩空白）",
                "异常过滤（过短/过长/乱码）",
                "PII 脱敏（手机号/身份证/邮箱/银行卡）",
            ],
            "source": source_info,
            "cleaning_stats": stats,
        }
        m = _deposit_one(
            run_id, "cleaning_rules", f"清洗规则说明 · {name}",
            f"清洗后 {stats.get('脱敏后条数', stats.get('原始条数', 0))} 条",
            "数据作战流清洗规则与统计说明（可复用：同类数据的清洗方案与预期去重率）",
            ["数据准备", "清洗规则", "可复用资产"], rules_payload)
        results.append(m); deposited.append(m)

    # 4. 质量报告
    qr = _load_product(run_id, "quality_report")
    if qr is not None and "quality_report" not in existing_types:
        m = _deposit_one(
            run_id, "quality_report", f"数据质量报告 · {name}",
            f"重复率 {qr.get('duplicate_rate', 0)}",
            "数据作战流质量评估报告（重复率/PII 类型/覆盖度），沉淀供同类数据质量基线比对",
            ["数据准备", "质量报告", "可复用资产"], qr)
        results.append(m); deposited.append(m)

    if results:
        update_run(run_id, deposited_assets=deposited)
        if project_id:
            _add_project_event(project_id, "dataprep_asset",
                               f"数据资产沉淀 · {name}",
                               detail=f"沉淀 {len(results)} 项可复用资产：{'、'.join(a['asset_type'] for a in results)}",
                               ref=run_id)
    return {
        "run_id": run_id,
        "deposited": results,
        "count": len(results),
        "assets": deposited,
    }
