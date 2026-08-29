"""数据标注与评测集管理：标注池 + 双人标注 + 一致性 + 评测集构建/更新

任务以 run_id 归档（tmp/web/annotation/<run_id>/），可断点续接。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from core.logging.logger import get_logger

logger = get_logger()

# annotation/ → 项目根（ai-field-delivery-toolkit/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANN_ROOT = PROJECT_ROOT / "tmp" / "web" / "annotation"


def _run_dir(run_id: str) -> Path:
    return ANN_ROOT / run_id


def _path(run_id: str) -> Path:
    return _run_dir(run_id) / "archive.json"


def _save(run_id: str, data: dict) -> None:
    _run_dir(run_id).mkdir(parents=True, exist_ok=True)
    with open(_path(run_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load(run_id: str) -> dict:
    p = _path(run_id)
    if not p.exists():
        raise FileNotFoundError(f"标注任务不存在: {run_id}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def create_annotation_task(name: str, items: list) -> dict:
    """创建标注任务：items 为字符串列表（待标注样本）"""
    run_id = uuid.uuid4().hex[:8]
    data = {
        "run_id": run_id,
        "name": name,
        "items": [{"id": i + 1, "content": c, "labels": {}} for i, c in enumerate(items)],
        "created_at": datetime.now().isoformat(),
    }
    _save(run_id, data)
    logger.info(f"标注任务创建 run_id={run_id} 样本={len(items)}")
    return data


def add_label(run_id: str, item_id: int, annotator: str, label: str) -> dict:
    """给某条样本打标签（同一人可覆盖，双人标注用于一致性）"""
    data = _load(run_id)
    for it in data["items"]:
        if it["id"] == item_id:
            it["labels"][annotator] = label
    _save(run_id, data)
    return data


def _item_consistency(labels: dict) -> str:
    """单条样本标注状态（v9.0 每样本一致性明细，供前端逐条展示）

    取值：unlabeled（未标） / only_a（仅 A 标） / only_b（仅 B 标） / only_one（仅一人标，非 A/B）
          / agreed（一致） / disagreed（分歧）。空字符串标签视为未标。
    """
    values = [v for v in (labels or {}).values() if v]
    if not values:
        return "unlabeled"
    if len(values) < 2:
        keys = [k for k, v in (labels or {}).items() if v]
        if keys and keys[0] in ("A", "a"):
            return "only_a"
        if keys and keys[0] in ("B", "b"):
            return "only_b"
        return "only_one"
    if len(set(values)) == 1:
        return "agreed"
    return "disagreed"


def get_task(run_id: str) -> dict:
    """返回任务与一致性状态（stats + 每样本 consistency 明细）"""
    data = _load(run_id)
    agreed = disagreed = unlabeled = 0
    for it in data["items"]:
        st = _item_consistency(it.get("labels") or {})
        it["consistency"] = st
        if st == "agreed":
            agreed += 1
        elif st == "disagreed":
            disagreed += 1
        else:
            unlabeled += 1
    data["stats"] = {"agreed": agreed, "disagreed": disagreed, "unlabeled": unlabeled,
                     "total": len(data["items"])}
    return data


def build_eval_set(run_id: str, output_path: str = None) -> dict:
    """从双人一致标注构建评测集（写入 output_path JSON）"""
    data = get_task(run_id)
    eval_set = []
    disagreements = []
    for it in data["items"]:
        labels = it["labels"]
        if len(labels) >= 2 and len(set(labels.values())) == 1:
            eval_set.append({
                "instruction": it["content"], "input": "", "output": next(iter(labels.values())),
                "metadata": {"annotators": list(labels.keys()), "consistency": "agreed"},
            })
        elif len(set(labels.values())) > 1:
            disagreements.append({"id": it["id"], "content": it["content"], "labels": labels})

    result = {
        "run_id": run_id,
        "total": data["stats"]["total"],
        "agreed": len(eval_set),
        "disagreements": len(disagreements),
        "disagreement_items": disagreements,
        "eval_set": eval_set,
    }
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["output_path"] = str(out)
    logger.info(f"评测集构建 run_id={run_id} 一致={len(eval_set)} 分歧={len(disagreements)}")
    return result


def list_tasks(limit: int = 50) -> list:
    """列出最近标注任务（按 mtime 倒序）：run_id / name / 样本数 / 一致性统计"""
    if not ANN_ROOT.exists():
        return []
    runs = []
    for p in ANN_ROOT.iterdir():
        if p.is_dir() and (p / "archive.json").exists():
            runs.append((p.name, (p / "archive.json").stat().st_mtime))
    runs.sort(key=lambda x: x[1], reverse=True)
    tasks = []
    for run_id, _m in runs[:limit]:
        try:
            data = get_task(run_id)
        except Exception as e:  # noqa: BLE001 单条损坏不阻断列表
            logger.warning(f"标注任务读取失败 run_id={run_id}: {e}")
            continue
        tasks.append({
            "run_id": run_id,
            "name": data.get("name", ""),
            "total": data["stats"]["total"],
            "stats": data["stats"],
        })
    return tasks


def create_annotation_task_from_dataprep(dataprep_run_id: str, sample_size: int = 20, name: str = None) -> dict:
    """从数据作战流 cleaned_data 产物取前 N 条作为待标注样本，建人工标注任务。

    样例来源诚实标注：任务档案增加 source 字段
    {type: "dataprep", dataprep_run_id, dataprep_name, sample_size}（只增字段，不破坏既有任务）。
    """
    from dataprep.archive import load_run, products_dir

    dp = load_run(dataprep_run_id)
    if dp is None:
        raise FileNotFoundError(f"数据作战流任务不存在: {dataprep_run_id}")
    cleaned_filename = (dp.get("products") or {}).get("cleaned_data")
    if not cleaned_filename:
        raise ValueError(f"数据作战流任务 {dataprep_run_id} 尚无清洗后数据（cleaned_data）产物，请先执行清洗步骤")
    cleaned_path = products_dir(dataprep_run_id) / cleaned_filename
    if not cleaned_path.exists():
        raise ValueError(f"cleaned_data 产物文件缺失: {cleaned_path}")
    with open(cleaned_path, "r", encoding="utf-8") as f:
        cleaned = json.load(f)

    items = [it.get("content", "") for it in cleaned[: max(1, int(sample_size))]]
    items = [c for c in items if c and c.strip()]
    if not items:
        raise ValueError("cleaned_data 产物中无可用样本内容")

    task_name = name or f"数据作战流-人工标注-{dp.get('name', dataprep_run_id)}"
    task = create_annotation_task(task_name, items)
    data = _load(task["run_id"])
    data["source"] = {
        "type": "dataprep",
        "dataprep_run_id": dataprep_run_id,
        "dataprep_name": dp.get("name", dataprep_run_id),
        "sample_size": len(items),
    }
    _save(task["run_id"], data)
    logger.info(f"从数据作战流建人工标注任务 run_id={data['run_id']} 样本={len(items)} "
                f"dataprep_run={dataprep_run_id}")
    return data
