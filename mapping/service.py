"""字段映射工作台服务：可迭代映射表格 + LLM 初判 + 导入真实样例 + 实跑校验 + 人工修正迭代 + 导出适配器 + 断点档案

映射任务以 run_id 归档（tmp/web/mapping/<run_id>/），可暂停/续接。
v4.0 新增「集成工作台」能力：
  - import_samples：导入真实源样例 CSV（列名=源字段名）→ 存档案 samples（原始行数 + 预览 + 全量行）
  - validate_mapping：把当前 mappings 对真实样例【实跑】transform（与 export 的 adapter 语义一致），
    生成每个目标字段的映射值，再调用「映射校验」LLM 对每条映射判断 pass/warn/fail + 理由，汇总成功率；
    校验结果存档案 validation，可续接。
  - validate_row：单行试运行（前端逐行预览）。
  - 任务创建/更新/校验挂项目档案（project event）。
"""

import csv
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.logging.logger import get_logger

logger = get_logger()

# mapping/ → 项目根（ai-field-delivery-toolkit/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAPPING_ROOT = PROJECT_ROOT / "tmp" / "web" / "mapping"

MAPPING_SYSTEM = (
    "你是数据字段映射助手。给定【源字段】和【目标字段】列表，为每个目标字段建议最匹配的源字段与映射规则。\n"
    "规则类型：direct=直接映射；concat=拼接多个源；split=拆分；lookup=查表；formula=公式；other=其他。\n"
    "source 无法匹配时填 null；confidence=high/medium/low。\n"
    "严格中立，基于字段名与示例值判断，不确定标 low。\n\n"
    '只输出 JSON：{"mappings":[{"target":"目标字段名","source":"源字段名或null","rule":"direct|concat|split|lookup|formula|other",'
    '"expression":"规则表达式或说明","confidence":"high|medium|low"}], "notes":"映射注意事项"}'
)

VALIDATE_SYSTEM = (
    "你是字段映射校验员。给定一个【目标字段】的映射规则，以及真实源样例和映射后的输出值，判断该映射是否正确合理。\n"
    "verdict 取值：pass=映射合理（输出符合目标字段含义）；warn=基本合理但有隐患（空值/格式不统一/边界情况）；fail=映射明显错误（值对不上/含义不符/输出异常）。\n"
    "结合源值含义与目标字段语义判断，不要仅因个别空值就判 fail（可判 warn）。\n"
    '只输出 JSON：{"verdict":"pass|warn|fail","reason":"判断理由"}'
)


def _default_json_call(system: str, user: str) -> Dict:
    from core.llm import chat_json
    return chat_json(system, user, temperature=0.2)


def _run_dir(run_id: str) -> Path:
    return MAPPING_ROOT / run_id


def _archive_path(run_id: str) -> Path:
    return _run_dir(run_id) / "archive.json"


def _save(run_id: str, data: dict) -> None:
    _run_dir(run_id).mkdir(parents=True, exist_ok=True)
    with open(_archive_path(run_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load(run_id: str) -> dict:
    p = _archive_path(run_id)
    if not p.exists():
        raise FileNotFoundError(f"映射任务不存在: {run_id}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- 挂项目档案（参考 dataprep） ----------


def _resolve_project(project_id: str, customer: str) -> Optional[str]:
    """显式 project_id 优先；否则按客户名自动建/复用项目。返回 project_id 或 None。"""
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
    except Exception as e:  # 项目档案失败不阻断映射流程
        logger.warning(f"挂项目档案失败 project_id={pid}: {e}")


# ---------- 生命周期 ----------


def create_mapping(
    name: str,
    source_fields: List[dict],
    target_fields: List[dict],
    llm_call: Optional[Callable[[str, str], Dict]] = None,
    project_id: str = "",
    customer: str = "",
    prefill_mappings: Optional[List[dict]] = None,
) -> dict:
    """创建映射任务，LLM 初判映射建议；任务挂项目档案（project event）

    v6.0：prefill_mappings 提供时跳过 LLM 初判，直接用历史映射配置预填（一键接入复用）。
    """
    run_id = uuid.uuid4().hex[:8]
    if prefill_mappings is not None:
        # 一键接入：直接用历史映射预填，不调 LLM
        suggested = {"mappings": prefill_mappings, "notes": "已从历史映射配置一键接入，可继续导入样例/校验/修正"}
    else:
        user = (
            "【源字段】\n" + "\n".join(f"- {f.get('name')} (示例: {f.get('sample','')})" for f in source_fields)
            + "\n\n【目标字段】\n" + "\n".join(f"- {f.get('name')} (示例: {f.get('sample','')})" for f in target_fields)
        )
        call = llm_call or _default_json_call
        suggested = call(MAPPING_SYSTEM, user)

    pid = _resolve_project(project_id, customer)
    data = {
        "run_id": run_id,
        "name": name,
        "source_fields": source_fields,
        "target_fields": target_fields,
        "mappings": suggested.get("mappings", []),
        "notes": suggested.get("notes", ""),
        "status": "draft",
        "project_id": pid,
        "customer": customer or "",
        "created_at": datetime.now().isoformat(),
    }
    _save(run_id, data)
    _add_project_event(pid, "mapping", f"字段映射任务 · {name}",
                       detail=f"初判 {len(data['mappings'])} 条映射 ｜ run_id={run_id}", ref=run_id)
    logger.info(f"映射任务创建 run_id={run_id} 建议 {len(data['mappings'])} 条 project_id={pid}")
    return data


def update_mapping(run_id: str, mappings: List[dict]) -> dict:
    """人工调整映射（可迭代）；更新挂项目档案"""
    data = _load(run_id)
    data["mappings"] = mappings
    data["updated_at"] = datetime.now().isoformat()
    _save(run_id, data)
    _add_project_event(data.get("project_id"), "mapping", f"映射调整 · {data.get('name', run_id)}",
                       detail=f"{len(mappings)} 条映射已更新 ｜ run_id={run_id}", ref=run_id)
    return data


def get_mapping(run_id: str) -> dict:
    return _load(run_id)


def list_mapping_runs(limit: int = 20) -> list:
    """列出最近映射任务（断点续接入口）"""
    if not MAPPING_ROOT.exists():
        return []
    runs = []
    for p in MAPPING_ROOT.iterdir():
        if p.is_dir() and (p / "archive.json").exists():
            try:
                with open(p / "archive.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            validation = data.get("validation") or {}
            runs.append({
                "run_id": data.get("run_id", p.name),
                "name": data.get("name", ""),
                "status": data.get("status", ""),
                "project_id": data.get("project_id"),
                "mapping_count": len(data.get("mappings", [])),
                "has_samples": bool(data.get("samples")),
                "has_validation": bool(validation),
                "success_rate": validation.get("success_rate"),
                "no_fail_rate": validation.get("no_fail_rate"),
                "created_at": data.get("created_at", ""),
            })
    runs.sort(key=lambda x: x["created_at"], reverse=True)
    return runs[:limit]


# ---------- 1. 导入真实样例数据 ----------


def import_samples(run_id: str, csv_bytes: bytes, filename: str = "sample.csv", max_rows: int = 200) -> dict:
    """导入真实源样例 CSV（列名=源字段名）→ 存档案 samples（原始行数 + 预览 + 全量行）"""
    data = _load(run_id)
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 无表头（列名应为源字段名）")
    rows = []
    for row in reader:
        rows.append({k: (v or "") for k, v in row.items()})
        if len(rows) >= max_rows:
            break
    if not rows:
        raise ValueError("CSV 中没有数据行")
    columns = list(rows[0].keys())
    samples = {
        "filename": filename,
        "original_row_count": len(rows),  # 原始行数（含截断上限内）
        "columns": columns,
        "rows": rows,
        "preview": rows[:5],
        "imported_at": datetime.now().isoformat(),
    }
    data["samples"] = samples
    data["status"] = "sample_loaded"
    data["updated_at"] = datetime.now().isoformat()
    _save(run_id, data)
    logger.info(f"映射任务导入样例 run_id={run_id} 行数={len(rows)} 列={columns}")
    return {
        "run_id": run_id,
        "filename": filename,
        "row_count": len(rows),
        "columns": columns,
        "preview": rows[:5],
    }


# ---------- 2. 实跑 transform（与 export 生成的 adapter 语义一致） ----------


def _apply_transform(mapping: dict, row: dict) -> tuple:
    """对单行执行一条映射，返回 (value, ok, note)。

    语义与 export_mapping 生成的 adapter.py 保持一致：
    direct→row.get(source)；concat→表达式用「+」分隔源字段、str 拼接；
    formula→以 row 为命名空间 eval 表达式；split→「源字段|分隔符|序号」；
    lookup/other 无法自动执行 → 判定失败并提示需人工实现（诚实校验，非糊弄）。
    """
    rule = mapping.get("rule") or "direct"
    source = mapping.get("source")
    expr = mapping.get("expression") or ""
    try:
        if rule == "direct":
            if not source:
                return None, False, "未指定源字段"
            if source not in row:
                return None, False, f"源字段 {source} 不存在"
            return row.get(source), True, ""
        if rule == "concat":
            parts = [s.strip() for s in expr.split("+") if s.strip()]
            if not parts:
                return None, False, "concat 表达式为空（用「+」分隔源字段名）"
            vals = []
            for p in parts:
                if p not in row:
                    return None, False, f"源字段 {p} 不存在"
                vals.append(str(row.get(p) or ""))
            return "".join(vals), True, ""
        if rule == "formula":
            if not expr:
                return None, False, "公式为空"
            val = eval(expr, {"row": row, "__builtins__": {}}, {})
            return val, True, ""
        if rule == "split":
            # 表达式：「源字段|分隔符|序号」，如 full_name|,|0
            segs = [s.strip() for s in expr.split("|")]
            src = segs[0]
            if not src:
                return None, False, "split 表达式需指定源字段"
            if src not in row:
                return None, False, f"源字段 {src} 不存在"
            delim = segs[1] if len(segs) > 1 else ","
            idx = int(segs[2]) if len(segs) > 2 else 0
            raw = str(row.get(src) or "")
            pieces = [s.strip() for s in raw.split(delim)]
            if idx >= len(pieces):
                return None, False, f"拆分越界：第 {idx} 段不存在"
            return pieces[idx], True, ""
        if rule == "lookup":
            return None, False, "查表规则需人工实现（暂不能实跑）"
        if rule == "other":
            return None, False, "其他规则需人工实现（暂不能实跑）"
    except Exception as e:  # noqa: BLE001
        return None, False, f"执行异常: {e}"
    return None, False, "未知规则"


def _transform_row(mappings: list, row: dict) -> dict:
    """对一行数据跑全部映射，返回 {target: (value, ok, note)}"""
    out = {}
    for m in mappings:
        target = m.get("target")
        if not target:
            continue
        val, ok, note = _apply_transform(m, row)
        out[target] = {"value": val, "ok": ok, "note": note}
    return out


def validate_row(run_id: str, row: dict) -> dict:
    """单行试运行：对给定一行源数据执行全部映射，返回每个目标字段的映射值 + 执行状态"""
    data = _load(run_id)
    mappings = data.get("mappings", [])
    if not mappings:
        raise ValueError("尚无映射，请先创建/保存映射")
    transformed = _transform_row(mappings, row)
    per_field = []
    for m in mappings:
        t = m.get("target")
        if t not in transformed:
            continue
        res = transformed[t]
        per_field.append({
            "target": t,
            "source": m.get("source"),
            "rule": m.get("rule", "direct"),
            "expression": m.get("expression", ""),
            "value": res["value"],
            "ok": res["ok"],
            "note": res["note"],
        })
    return {"run_id": run_id, "row": row, "per_field": per_field}


# ---------- 3. 试运行 + 实跑校验 ----------


def _llm_judge_field(llm_call, mapping: dict, results: list) -> dict:
    """对一条映射（已实跑出样例结果）调用「映射校验」LLM，返回 {verdict, reason}"""
    target = mapping.get("target")
    user = (
        f"目标字段：{target}\n"
        f"规则：{mapping.get('rule', 'direct')}\n"
        f"源字段：{mapping.get('source') or '无'}\n"
        f"表达式：{mapping.get('expression') or ''}\n"
        "样例（源值 → 映射输出）：\n" +
        "\n".join(
            f"- {str(r['source_value']) if r['source_value'] is not None else '(无)'} "
            f"→ {str(r['output']) if r['output'] is not None else 'None'}"
            for r in results[:10]
        )
    )
    judge = llm_call(VALIDATE_SYSTEM, user)
    verdict = judge.get("verdict")
    if verdict not in ("pass", "warn", "fail"):
        verdict = "warn"
    reason = judge.get("reason", "") or ""
    return {"verdict": verdict, "reason": reason}


def validate_mapping(run_id: str, llm_call: Optional[Callable[[str, str], Dict]] = None,
                     max_rows: int = 20) -> dict:
    """把当前 mappings 对真实样例数据实跑，生成每个目标字段的映射值 + LLM 校验判定，汇总成功率。

    校验结果存档案 validation（断点续接）。max_rows 控制参与实跑/抽样的行数。
    """
    data = _load(run_id)
    samples = data.get("samples") or {}
    rows = samples.get("rows") or []
    if not rows:
        raise ValueError("尚无样例数据，请先导入真实样例（POST /mapping/{run_id}/samples）")
    mappings = data.get("mappings", [])
    if not mappings:
        raise ValueError("尚无映射，请先创建/保存映射")
    call = llm_call or _default_json_call

    sample_rows = rows[:max(max_rows, 1)]
    per_field = []
    for m in mappings:
        target = m.get("target")
        if not target:
            continue
        source = m.get("source")
        results = []
        for row in sample_rows:
            val, ok, note = _apply_transform(m, row)
            results.append({
                "source_value": row.get(source) if source else None,
                "output": val,
                "ok": ok,
                "note": note,
            })
        ok_rows = [r for r in results if r["ok"]]
        fail_rows = [r for r in results if not r["ok"]]

        # 执行失败占比过高 → 直接判 fail；否则交 LLM 校验
        if fail_rows:
            ratio = len(fail_rows) / len(results)
            if ratio > 0.3:
                verdict, reason = "fail", f"{len(fail_rows)}/{len(results)} 行执行失败：" + "；".join(
                    dict.fromkeys(r["note"] for r in fail_rows))[:200]
            else:
                judge = _llm_judge_field(call, m, results)
                verdict, reason = judge["verdict"], judge["reason"] + f"（{len(fail_rows)}/{len(results)} 行执行失败）"
        else:
            judge = _llm_judge_field(call, m, results)
            verdict, reason = judge["verdict"], judge["reason"]

        per_field.append({
            "target": target,
            "source": source,
            "rule": m.get("rule", "direct"),
            "expression": m.get("expression", ""),
            "verdict": verdict,
            "reason": reason,
            "pass": len(ok_rows),
            "warn": 0,
            "fail": len(fail_rows),
            "sampled_rows": len(results),
            "examples": results[:5],
        })

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for f in per_field:
        counts[f["verdict"]] += 1
    total_fields = len(per_field)
    success_rate = round(counts["pass"] / total_fields, 4) if total_fields else 0.0
    no_fail_rate = round((counts["pass"] + counts["warn"]) / total_fields, 4) if total_fields else 0.0

    result = {
        "run_id": run_id,
        "total_rows": len(rows),
        "mapped_rows": len(sample_rows),
        "sampled_rows": len(sample_rows),
        "per_field": per_field,
        "counts": counts,
        "success_rate": success_rate,   # 严格通过率：pass / 字段数
        "no_fail_rate": no_fail_rate,   # 无硬失败率：(pass+warn) / 字段数（修正迭代用「打到 no_fail 即达标」更直观）
        "validated_at": datetime.now().isoformat(),
    }
    data["validation"] = result
    data["status"] = "validated"
    data["updated_at"] = datetime.now().isoformat()
    _save(run_id, data)
    _add_project_event(data.get("project_id"), "mapping", f"映射校验 · {data.get('name', run_id)}",
                       detail=f"成功率 {success_rate * 100:.0f}% / 无失败率 {no_fail_rate * 100:.0f}%（pass {counts['pass']}/warn {counts['warn']}/fail {counts['fail']}）｜ run_id={run_id}",
                       ref=run_id)
    logger.info(f"映射校验完成 run_id={run_id} 成功率={success_rate} counts={counts}")
    return result


# ---------- 4. 导出适配器 ----------


def export_mapping(run_id: str) -> dict:
    """导出适配器配置：JSON 映射 + Python 适配器骨架"""
    data = _load(run_id)
    config = {
        "task_name": data["name"],
        "version": "1.0",
        "mappings": [
            {
                "target": m.get("target"),
                "source": m.get("source"),
                "rule": m.get("rule", "direct"),
                "expression": m.get("expression", ""),
            }
            for m in data.get("mappings", [])
        ],
    }
    py_lines = [
        "def transform(row: dict) -> dict:",
        "    out = {}",
    ]
    for m in config["mappings"]:
        t = m["target"]
        if m["rule"] == "direct" and m["source"]:
            py_lines.append(f"    out['{t}'] = row.get('{m['source']}')")
        elif m["rule"] == "concat":
            parts = [s.strip() for s in (m["expression"] or "").split("+") if s.strip()]
            expr = " + ".join(f"str(row.get('{p}') or '')" for p in parts)
            py_lines.append(f"    out['{t}'] = {expr}")
        elif m["rule"] == "formula" and m["expression"]:
            py_lines.append(f"    out['{t}'] = {m['expression']}")
        else:
            py_lines.append(f"    out['{t}'] = None  # 需人工实现: {m.get('expression','')}")
    py_lines += ["    return out", ""]
    adapter_py = "\n".join(py_lines)

    out_dir = _run_dir(run_id) / "adapter"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "mapping_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    with open(out_dir / "adapter.py", "w", encoding="utf-8") as f:
        f.write(adapter_py)
    result = {
        "run_id": run_id,
        "config_path": str(out_dir / "mapping_config.json"),
        "adapter_path": str(out_dir / "adapter.py"),
        "adapter_code": adapter_py,
        "mapping_count": len(config["mappings"]),
    }
    # v6.0：导出成功 → 注册为可复用资产（kind=mapping_config，幂等）；失败不阻断导出
    try:
        from assets.service import register_from_mapping
        asset = register_from_mapping(run_id)
        if asset:
            result["asset"] = {
                "asset_id": asset["asset_id"],
                "kind": asset["kind"],
                "url": f"/api/v1/assets/{asset['asset_id']}",
            }
    except Exception as e:  # noqa: BLE001
        logger.warning(f"映射导出后注册资产失败 run_id={run_id}: {e}")
    return result
