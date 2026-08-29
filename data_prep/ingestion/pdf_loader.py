"""PDF 数据接入（增强版：文字版正常提取，扫描版检测并标记）"""

from typing import Dict, Any, List, Optional
import re

from core.logging.logger import get_logger

logger = get_logger()


class PDFLoader:
    """从 PDF 文件提取文本，区分文字版与扫描版"""

    def __init__(self, min_text_length: int = 50, garbled_ratio_threshold: float = 0.3):
        self.min_text_length = min_text_length
        self.garbled_ratio_threshold = garbled_ratio_threshold

    def ingest(self, source_path: str) -> Dict[str, Any]:
        """接入 PDF 文档

        返回:
            {
                "data": [{"content": "...", "metadata": {...}}, ...],
                "skipped": [{"file": "...", "reason": "..."}, ...]
            }
        """
        text = self._extract_text(source_path)

        # 检测文字版还是扫描版
        quality = self._check_text_quality(text)
        if not quality["valid"]:
            logger.warning(f"PDF 文本质量不佳，文件跳过: {source_path}, 原因: {quality['reason']}")
            return {
                "data": [],
                "skipped": [{"file": source_path, "reason": quality["reason"]}],
            }

        # 切分为段落
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        records = [{"content": p, "metadata": {"source": source_path, "type": "pdf"}} for p in paragraphs]
        return {"data": records, "skipped": []}

    def _extract_text(self, source_path: str) -> str:
        """提取 PDF 文本"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            try:
                from pypdf import PdfReader
                reader = PdfReader(source_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
            except ImportError:
                logger.error("未安装 PDF 解析依赖（pymupdf 或 pypdf）")
                return ""
        else:
            try:
                doc = fitz.open(source_path)
            except Exception as e:
                logger.warning(f"无法按 PDF 解析 {source_path}（{e}），回退为纯文本读取")
                return self._read_as_text(source_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text

    def _read_as_text(self, source_path: str) -> str:
        """按纯文本读取文件（用于非 PDF 文件或提取好的文本）"""
        try:
            with open(source_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return ""

    def _check_text_quality(self, text: str) -> Dict[str, Any]:
        """检测文本质量

        判断标准：
        1. 总文本长度是否小于阈值（可能无文本或提取失败）
        2. 非 ASCII 字符中不可打印字符的比例是否过高（乱码检测）
        """
        if len(text.strip()) < self.min_text_length:
            return {"valid": False, "reason": "文本长度过短，可能是扫描版或无文字 PDF"}

        # 统计不可打印字符比例
        total_chars = len(text)
        unprintable = sum(1 for c in text if ord(c) < 32 and c not in "\n\t")
        ratio = unprintable / total_chars if total_chars > 0 else 0

        if ratio > self.garbled_ratio_threshold:
            return {"valid": False, "reason": f"乱码比例过高（{ratio:.2%}），可能是扫描版 PDF"}

        return {"valid": True, "reason": ""}