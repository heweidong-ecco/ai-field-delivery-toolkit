"""客户反馈解析：上传评估文件（文本/PDF）→ LLM 提炼客户意见条目

客户意见条目结构：{"item": "意见", "dimension": 五维之一或 null, "intent": "raise|lower|clarify|other"}
- dimension 用于增量重评：只对客户意见触及的维度重跑 Generator/Critic
- intent：raise=应上调该维度分，lower=应下调，clarify=补充信息，other=其他
"""

from pathlib import Path
from typing import Callable, Dict, Optional

from core.logging.logger import get_logger

logger = get_logger()

FEEDBACK_SYSTEM = (
    "你是需求诊断的「客户反馈解析」。把客户返回的评估意见提炼为结构化条目。\n"
    "要求：\n"
    "1. 每条意见 20-50 字，尽量保留客户原意。\n"
    "2. 尽量把意见映射到五个维度之一；无法映射则为 null。\n"
    "3. intent：raise=应上调该维度分，lower=应下调，clarify=补充信息/澄清，other=其他。\n"
    "4. 严格中立，不自行判断对错，只如实提炼。\n\n"
    "只输出 JSON，格式：\n"
    '{"items": [{"item": "客户意见", "dimension": "generation|reasoning|uncertainty|data|real_time|null", '
    '"intent": "raise|lower|clarify|other"}], "summary": "客户反馈总体倾向（100字内）"}'
)


def _default_json_call(system: str, user: str) -> Dict:
    from core.llm import chat_json
    return chat_json(system, user, temperature=0.2)


def read_feedback_file(path: str) -> str:
    """读取反馈文件为文本：.pdf 用 pymupdf 提取，其余按 UTF-8 文本读取"""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        text = "".join(page.get_text() for page in doc)
        if not text.strip():
            raise ValueError("PDF 未提取到文本（可能为扫描版），请改用文本粘贴或上传带文字的 PDF")
        return text.strip()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read().strip()
    if not text:
        raise ValueError("反馈文件内容为空")
    return text


def extract_feedback_items(
    feedback_text: str,
    requirement: str,
    current_scores: Optional[Dict] = None,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """LLM 提炼客户意见条目；返回 {items, summary}"""
    current = current_scores or {}
    user = (
        "【当前 AI 评估的五维分数（供判断意图参考）】\n"
        f"{current}\n\n"
        "【需求文本】\n" + requirement + "\n\n【客户反馈原文】\n" + feedback_text
    )
    call = llm_call or _default_json_call
    data = call(FEEDBACK_SYSTEM, user)
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("客户意见条目解析失败")
    return {"items": items, "summary": data.get("summary", "")}


def touched_dimensions(items: list) -> list:
    """从客户意见条目中提取被触及的维度（去重、去 null）"""
    dims = []
    for it in items or []:
        d = it.get("dimension")
        if d and d in ("generation", "reasoning", "uncertainty", "data", "real_time") and d not in dims:
            dims.append(d)
    return dims


def categorize_feedback_items(items: list) -> dict:
    """把客户意见条目归类到需求文档章节，供报告织入对应章节。

    返回：{"functional": [], "non_functional": [], "open": [], "acceptance": []}
    - clarify / 含问句 → 开放问题
    - 触及 uncertainty / data / real_time → 非功能需求
    - raise / lower（明确要求调整口径）→ 验收标准
    - 其余 → 功能需求
    """
    sections = {"functional": [], "non_functional": [], "open": [], "acceptance": []}
    for it in items or []:
        text = (it.get("item") or "").strip()
        if not text:
            continue
        intent = it.get("intent")
        dim = it.get("dimension")
        if intent == "clarify" or "?" in text or "请问" in text or "是否" in text:
            sections["open"].append(text)
        elif dim in ("uncertainty", "data", "real_time"):
            sections["non_functional"].append(text)
        elif intent in ("raise", "lower"):
            sections["acceptance"].append(text)
        else:
            sections["functional"].append(text)
    return sections
