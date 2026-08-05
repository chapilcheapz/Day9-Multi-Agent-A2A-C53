"""
Delivery Agent - Phân tích các mốc thời gian giao nhận.
Truy cập: olist_orders_dataset.
Output: delivery_analysis (delivered_at, estimated_delivery_at, delivery_variance_hours...).
"""

from typing import Any, Dict

import pandas as pd

from src.base_agent import AgentResult, BaseAgent


class DeliveryAgent(BaseAgent):
    """Agent tính delivery_variance_hours và phát hiện giao trễ theo estimated date."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("DeliveryAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(
                    self.name,
                    self._result(
                        delivered_at=None,
                        estimated_at=None,
                        carrier_at=None,
                        variance_hours=None,
                        is_late=False,
                    ),
                )

            delivered_at = order.get("order_delivered_customer_date")
            estimated_at = order.get("order_estimated_delivery_date")
            carrier_at = order.get("order_delivered_carrier_date")

            variance_hours = None
            is_late = False
            if pd.notna(delivered_at) and pd.notna(estimated_at):
                variance_hours = self._safe_round(
                    (delivered_at - estimated_at).total_seconds() / 3600.0
                )
                is_late = variance_hours > 0

            return AgentResult(
                self.name,
                self._result(delivered_at, estimated_at, carrier_at, variance_hours, is_late),
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    def _result(self, delivered_at, estimated_at, carrier_at, variance_hours, is_late) -> Dict[str, Any]:
        return {
            "delivered_at": self._format_timestamp(delivered_at),
            "estimated_delivery_at": self._format_timestamp(estimated_at),
            "carrier_handoff_at": self._format_timestamp(carrier_at),
            "delivery_variance_hours": variance_hours,
            "is_late_delivery": is_late,
        }