"""Agent 状态保存与恢复"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    """Agent 运行状态"""
    agent_id: str
    loop_name: str = "react"
    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    finished: bool = False
    result: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "loop_name": self.loop_name,
            "steps": self.steps,
            "current_step": self.current_step,
            "finished": self.finished,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        return cls(
            agent_id=data["agent_id"],
            loop_name=data.get("loop_name", "react"),
            steps=data.get("steps", []),
            current_step=data.get("current_step", 0),
            finished=data.get("finished", False),
            result=data.get("result"),
        )

    def add_step(self, step_data: Dict[str, Any]):
        self.steps.append(step_data)
        self.current_step += 1