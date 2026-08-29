"""版本管理器"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class VersionInfo:
    """版本信息"""
    version: str
    updated_at: str
    updated_by: str
    changelog: str


class VersionManager:
    """版本管理器

    管理三类版本：代码版本、提示词版本、模板版本。
    """

    def __init__(self):
        self._code_versions: list[VersionInfo] = []
        self._prompt_versions: list[VersionInfo] = []
        self._template_versions: list[VersionInfo] = []

    def record_code_version(self, version: str, author: str, changelog: str):
        self._code_versions.append(VersionInfo(
            version=version,
            updated_at=datetime.now().isoformat(),
            updated_by=author,
            changelog=changelog,
        ))

    def record_prompt_version(self, version: str, author: str, changelog: str):
        self._prompt_versions.append(VersionInfo(
            version=version,
            updated_at=datetime.now().isoformat(),
            updated_by=author,
            changelog=changelog,
        ))

    def record_template_version(self, version: str, author: str, changelog: str):
        self._template_versions.append(VersionInfo(
            version=version,
            updated_at=datetime.now().isoformat(),
            updated_by=author,
            changelog=changelog,
        ))

    def get_code_versions(self) -> list[VersionInfo]:
        return self._code_versions

    def get_prompt_versions(self) -> list[VersionInfo]:
        return self._prompt_versions

    def get_template_versions(self) -> list[VersionInfo]:
        return self._template_versions