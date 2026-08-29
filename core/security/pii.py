"""PII 检测与脱敏"""

import re


class PIIDetector:
    """PII 检测器"""

    PATTERNS = {
        "phone": re.compile(r"1[3-9]\d{9}"),
        "id_card": re.compile(r"\d{17}[\dXx]"),
        "email": re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"),
        "bank_card": re.compile(r"\d{16,19}"),
    }

    @classmethod
    def detect(cls, text: str) -> list[str]:
        """检测文本中包含的 PII 类型"""
        found = []
        for pii_type, pattern in cls.PATTERNS.items():
            if pattern.search(text):
                found.append(pii_type)
        return found

    @classmethod
    def mask(cls, text: str) -> str:
        """对文本中的 PII 进行脱敏"""
        # 手机号：保留前3后4
        text = re.sub(r"(1[3-9]\d)\d{4}(\d{4})", r"\1****\2", text)
        # 身份证号：保留前3后4
        text = re.sub(r"(\d{3})\d{10}(\d{4})", r"\1**********\2", text)
        # 邮箱：用户名掩码
        text = re.sub(r"([\w\.-]+)@([\w\.-]+\.\w+)", r"***@\2", text)
        return text