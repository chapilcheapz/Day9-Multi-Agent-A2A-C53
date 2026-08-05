"""
Base Agent - Lớp cơ sở cho tất cả Agent trong hệ thống.
Mỗi agent có quyền truy cập DataStore và LLMClient riêng,
trả về AgentResult chuẩn để Coordinator handoff.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd

from src.data_loader import DataStore
from src.llm_client import LLMClient


class AgentResult:
    """Kết quả phản hồi chuẩn từ mỗi agent."""

    def __init__(
        self,
        agent_name: str,
        data: Dict[str, Any],
        success: bool = True,
        error: str = "",
        llm_used: bool = False,
        llm_notes: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.data = data
        self.success = success
        self.error = error
        self.llm_used = llm_used
        self.llm_notes = llm_notes
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent_name,
            "timestamp": self.timestamp,
            "success": self.success,
            "error": self.error if not self.success else "",
            "llm_used": self.llm_used,
        }


class BaseAgent(ABC):
    """Interface chung cho mọi agent: tích hợp sẵn DataStore + LLMClient."""

    def __init__(self, name: str, data_dir: str = "data"):
        self.name = name
        self.data_store = DataStore(data_dir)
        self.llm_client = LLMClient()

    @abstractmethod
    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        """Phương thức xử lý nghiệp vụ chính của từng Agent."""
        raise NotImplementedError

    # ------------------------------------------------------------- helpers
    def _safe_round(self, value: Optional[float], decimals: int = 2) -> Optional[float]:
        if value is None:
            return None
        try:
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return None

    def _format_timestamp(self, ts) -> Optional[str]:
        """Chuẩn hoá timestamp về định dạng CSV: YYYY-MM-DD HH:MM:SS."""
        if ts is None:
            return None
        try:
            if pd.isna(ts):
                return None
            return str(ts).replace("T", " ")[:19]
        except (TypeError, ValueError):
            return None

    def _is_empty_frame(self, df: pd.DataFrame) -> bool:
        return df is None or df.empty
