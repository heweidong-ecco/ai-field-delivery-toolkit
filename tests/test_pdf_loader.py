"""PDF 解析测试"""

import pytest

from data_prep.ingestion.pdf_loader import PDFLoader


class TestPDFLoader:
    """PDF 解析增强版测试"""

    def test_empty_pdf_skipped(self, tmp_path):
        """空 PDF 应被标记为跳过"""
        # 创建空文本文件（模拟扫描版 PDF 无文本）
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_text("", encoding="utf-8")

        loader = PDFLoader(min_text_length=50)
        result = loader.ingest(str(pdf_path))
        assert len(result["data"]) == 0
        assert len(result["skipped"]) == 1
        assert "长度过短" in result["skipped"][0]["reason"]

    def test_garbled_pdf_skipped(self, tmp_path):
        """乱码 PDF 应被标记为跳过"""
        pdf_path = tmp_path / "garbled.pdf"
        # 模拟乱码：大量不可打印字符
        garbled_text = "".join(chr(0x00 + i % 32) for i in range(200))
        pdf_path.write_text(garbled_text, encoding="utf-8")

        loader = PDFLoader(min_text_length=50, garbled_ratio_threshold=0.3)
        result = loader.ingest(str(pdf_path))
        assert len(result["data"]) == 0
        assert len(result["skipped"]) == 1
        assert "乱码" in result["skipped"][0]["reason"]

    def test_valid_pdf_parsed(self, tmp_path):
        """正常 PDF 应被解析"""
        pdf_path = tmp_path / "valid.pdf"
        # 模拟提取的正常文本（长度需超过 min_text_length=50）
        valid_text = (
            "这是第一段内容，用于测试 PDF 正常解析。\n\n"
            "这是第二段内容，这段文本足够长，能够满足最小文本长度的要求。\n\n"
            "这是第三段内容，同样是正常的中文文本。"
        )
        pdf_path.write_text(valid_text, encoding="utf-8")

        loader = PDFLoader(min_text_length=50)
        result = loader.ingest(str(pdf_path))
        assert len(result["data"]) > 0
        assert len(result["skipped"]) == 0
        assert all("type" in item["metadata"] for item in result["data"])