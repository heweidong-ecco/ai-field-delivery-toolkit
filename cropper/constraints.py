"""客户约束输入模型（v1.2.0：增加网络带宽和合规等级）"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class HardwareConstraints:
    """硬件约束"""
    cpu: str = "4核"
    memory_gb: int = 16
    gpu: Optional[str] = None
    storage_gb: int = 100


@dataclass
class EnvironmentConstraints:
    """环境约束"""
    os: str = "ubuntu-22.04"
    docker: bool = True
    network: str = "internet"
    external_access: bool = True
    network_bandwidth_mbps: int = 100    # v1.2.0 新增


@dataclass
class DataConstraints:
    """数据约束"""
    total_records: int = 0
    daily_new: int = 0
    formats: List[str] = field(default_factory=list)
    quality: str = "medium"


@dataclass
class UserConstraints:
    """用户约束"""
    total_users: int = 10
    concurrent_peak: int = 5


@dataclass
class ComplianceConstraints:
    """合规约束（v1.2.0 增加合规等级）"""
    data_residency: str = "on-premise"
    pii_sensitive: bool = True
    compliance_level: str = "standard"   # standard / strict / critical


@dataclass
class CustomerConstraints:
    """客户全部约束"""
    customer_id: str
    budget: int = 100000
    hardware: HardwareConstraints = field(default_factory=HardwareConstraints)
    environment: EnvironmentConstraints = field(default_factory=EnvironmentConstraints)
    data: DataConstraints = field(default_factory=DataConstraints)
    users: UserConstraints = field(default_factory=UserConstraints)
    compliance: ComplianceConstraints = field(default_factory=ComplianceConstraints)
    timeline_weeks: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "budget": self.budget,
            "hardware": {
                "cpu": self.hardware.cpu,
                "memory_gb": self.hardware.memory_gb,
                "gpu": self.hardware.gpu,
                "storage_gb": self.hardware.storage_gb,
            },
            "environment": {
                "os": self.environment.os,
                "docker": self.environment.docker,
                "network": self.environment.network,
                "external_access": self.environment.external_access,
                "network_bandwidth_mbps": self.environment.network_bandwidth_mbps,
            },
            "data": {
                "total_records": self.data.total_records,
                "daily_new": self.data.daily_new,
                "formats": self.data.formats,
                "quality": self.data.quality,
            },
            "users": {
                "total_users": self.users.total_users,
                "concurrent_peak": self.users.concurrent_peak,
            },
            "compliance": {
                "data_residency": self.compliance.data_residency,
                "pii_sensitive": self.compliance.pii_sensitive,
                "compliance_level": self.compliance.compliance_level,
            },
            "timeline_weeks": self.timeline_weeks,
        }