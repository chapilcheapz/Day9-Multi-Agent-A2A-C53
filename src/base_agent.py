"""
Base Agent - Lớp cơ sở cho tất cả Agent trong hệ thống.
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.data_loader import DataStore
from src.llm_client import LLMClient


class AgentResult:
    """Kết quả phản hồi chuẩn từ mỗi agent."""

    def __init__(self, agent_name: str, data: Dict[str, Any], success: bool = True, error: str = ""):
        self.agent_name = agent_name
        self.data = data
        self.success = success
        self.error = error
        self.timestamp = time.time()


class BaseAgent(ABC):
    """
    Lớp cơ sở định nghĩa Interface chung cho mọi Agent.
    Mỗi Agent được tích hợp sẵn LLMClient model và DataStore.
    """

    def __init__(self, name: str, data_dir: str = "data"):
        self.name = name
        self.data_store = DataStore(data_dir)
        self.llm_client = LLMClient()

    @abstractmethod
    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        """Phương thức xử lý nghiệp vụ chính của từng Agent."""
        pass

    def _safe_round(self, value: Optional[float], decimals: int = 2) -> Optional[float]:
        """Hàm helper làm tròn an toàn 2 chữ số thập phân."""
        if value is None:
            return None
        return round(float(value), decimals)

    def _format_timestamp(self, ts) -> Optional[str]:
        """Format timestamp sang định dạng CSV standard: YYYY-MM-DD HH:MM:SS."""
        if ts is None or (hasattr(ts, "isnull") and ts.isnull()):
            return None
        try:
            import pandas as pd
            if pd.isna(ts):
                return None
            return str(ts).replace("T", " ")[:19]
        except (ValueError, TypeError):
            return None
