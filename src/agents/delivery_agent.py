"""
Delivery Agent - Phân tích mốc thời gian giao hàng.
Output: delivery_analysis
"""

from typing import Dict, Any
import pandas as pd
from src.base_agent import BaseAgent, AgentResult


class DeliveryAgent(BaseAgent):
    """Agent tính delivery_variance_hours và phát hiện trễ giao hàng."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("DeliveryAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            customer_msg = case_data.get("customer_request", {}).get("message", "")
            if customer_msg and self.llm_client.api_key:
                prompt = f"DeliveryAgent analyzing delivery variance for order: {order_id}"
                _delivery_reasoning = self.llm_client.chat_completion(prompt, max_tokens=50)

            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(
                    self.name,
                    {
                        "delivered_at": None,
                        "estimated_delivery_at": None,
                        "carrier_handoff_at": None,
                        "delivery_variance_hours": None,
                        "is_late_delivery": False,
                    },
                    success=True,
                )

            delivered_at = order.get("order_delivered_customer_date")
            estimated_at = order.get("order_estimated_delivery_date")
            carrier_at = order.get("order_delivered_carrier_date")

            if pd.notna(delivered_at) and pd.notna(estimated_at):
                variance_seconds = (delivered_at - estimated_at).total_seconds()
                delivery_variance_hours = self._safe_round(variance_seconds / 3600.0)
                is_late_delivery = delivery_variance_hours > 0
            else:
                delivery_variance_hours = None
                is_late_delivery = False

            return AgentResult(
                self.name,
                {
                    "delivered_at": self._format_timestamp(delivered_at),
                    "estimated_delivery_at": self._format_timestamp(estimated_at),
                    "carrier_handoff_at": self._format_timestamp(carrier_at),
                    "delivery_variance_hours": delivery_variance_hours,
                    "is_late_delivery": is_late_delivery,
                },
                success=True,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))
