"""诊断档案：按 run_id 落盘 JSON + 置信度计算

存储位置：tmp/web/diagnosis/<run_id>/archive.json（已 gitignore）
字段（方案 3.6）：requirement / prompt(+prompt_modified) / rounds[] / scores{generator,critic,reviewer,human}
                 / divergences[] / confidence / versions[] / client_feedback[] / llm_calls / confirmed
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Optional

from core.logging.logger import get_logger

logger = get_logger()

# diagnosis/ → 项目根（ai-field-delivery-toolkit/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = PROJECT_ROOT / "tmp" / "web" / "diagnosis"

BUDGET_MAX_CALLS = 9  # 单次诊断 LLM 调用数上限（方案 3.5）


def run_dir(run_id: str) -> Path:
    return ARCHIVE_ROOT / run_id


def archive_path(run_id: str) -> Path:
    return run_dir(run_id) / "archive.json"


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


def create_run(run_id: str, data: Dict) -> Path:
    """创建档案文件（幂等）"""
    run_dir(run_id).mkdir(parents=True, exist_ok=True)
    path = archive_path(run_id)
    if not path.exists():
        data.setdefault("llm_calls", 0)
        data.setdefault("confirmed", False)
        data.setdefault("rounds", [])
        data.setdefault("client_feedback", [])
        data.setdefault("versions", [])
        data.setdefault("divergences", [])
        data.setdefault("agent_log", [])
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
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")
    data.update(fields)
    _write(run_id, data)
    return data


def rename_run(run_id: str, name: str) -> Dict:
    """给历史诊断设人工名字（默认是需求摘要截断）"""
    data = update_run(run_id, name=name.strip() or None)
    return data


def _write(run_id: str, data: Dict) -> None:
    path = archive_path(run_id)
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


# ---------- 预算计数 ----------


def consume_call(run_id: str) -> int:
    """记录一次 LLM 调用，返回累计次数；超过预算返回 -1 由编排层接管"""
    data = load_run(run_id) or {"llm_calls": 0}
    data["llm_calls"] = data.get("llm_calls", 0) + 1
    _write(run_id, data)
    return -1 if data["llm_calls"] > BUDGET_MAX_CALLS else data["llm_calls"]


def calls_used(run_id: str) -> int:
    data = load_run(run_id) or {}
    return data.get("llm_calls", 0)


# ---------- 置信度（方案 3.4） ----------

CONFIDENCE_THRESHOLDS = {"high": 0.8, "medium": 0.6}  # >=0.8 高 / 0.6-0.8 中 / <0.6 低
LOW_CONFIDENCE_FLOOR = 0.6


def compute_confidence(gen_scores: Dict, crit_scores: Dict) -> Dict:
    """置信度 = Generator 与 Critic 的一致度（各维接近程度）

    每维 agreement = 1 - |Δ|/4；overall = 均值；
    level：>=0.8 high / 0.6-0.8 medium / <0.6 low；
    needs_confirm = agreement < 0.6 的维度（强制进"需确认"清单）。
    """
    dims = ("generation", "reasoning", "uncertainty", "data", "real_time")
    per_dim = {}
    for k in dims:
        delta = abs(int(gen_scores.get(k, 0)) - int(crit_scores.get(k, 0)))
        per_dim[k] = round(1 - delta / 4, 3)
    overall = round(sum(per_dim.values()) / len(per_dim), 3)
    level = "high" if overall >= CONFIDENCE_THRESHOLDS["high"] else (
        "medium" if overall >= CONFIDENCE_THRESHOLDS["medium"] else "low")
    needs_confirm = [k for k, v in per_dim.items() if v < LOW_CONFIDENCE_FLOOR]
    return {
        "overall": overall,
        "level": level,
        "per_dimension": per_dim,
        "needs_confirm": needs_confirm,
    }
