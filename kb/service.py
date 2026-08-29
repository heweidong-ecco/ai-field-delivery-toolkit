"""知识库构建（最小件）：文档分块 + 质检"""

import re


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """把长文本切成带重叠的分块（滑动窗口，按字符；最小件，后续可接向量化）"""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    chunk_size = max(50, chunk_size)
    overlap = max(0, min(overlap, chunk_size // 2))
    step = max(1, chunk_size - overlap)
    chunks = []
    for i in range(0, len(text), step):
        c = text[i:i + chunk_size].strip()
        if c:
            chunks.append(c)
    return chunks


def quality_check(chunks: list) -> dict:
    """质检：空块 / 重复块 / 过短 / 超长"""
    report = {"total": len(chunks), "empty": 0, "duplicates": 0, "too_short": 0, "too_long": 0, "issues": []}
    seen = set()
    for c in chunks:
        if not c:
            report["empty"] += 1
        if c in seen:
            report["duplicates"] += 1
        seen.add(c)
        if len(c) < 20:
            report["too_short"] += 1
        if len(c) > 2000:
            report["too_long"] += 1
    if report["duplicates"]:
        report["issues"].append("存在重复分块")
    if report["too_short"]:
        report["issues"].append("存在过短分块")
    if report["too_long"]:
        report["issues"].append("存在超长分块")
    if not report["issues"]:
        report["issues"].append("质检通过")
    return report
