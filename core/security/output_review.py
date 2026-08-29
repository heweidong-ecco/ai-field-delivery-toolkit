"""输出内容审核（占位实现，后续接入完整审核规则）"""


class OutputReviewer:
    """输出内容审核器"""

    BANNED_WORDS = []  # TODO: 从安全基线配置加载

    @classmethod
    def review(cls, text: str) -> dict:
        # TODO: 接入完整审核规则（色情、暴力、政治敏感、歧视等）
        # TODO: 支持第三方审核服务
        return {
            "passed": True,
            "reason": "",
            "masked_text": text,
        }