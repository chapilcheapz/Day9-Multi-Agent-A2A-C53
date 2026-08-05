"""
Delivery Agent - Phân tích mốc thời gian giao nhận và seller handoff.
Truy cập: olist_orders_dataset, olist_order_items_dataset.
Output: delivery_analysis (delivered_at, estimated, delivery_variance, seller_handoff).
"""

from typing import Any, Dict, List

import pandas as pd

from src.base_agent import AgentResult, BaseAgent


class DeliveryAgent(BaseAgent):
    """Agent tính delivery_variance_hours và seller handoff variance."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("DeliveryAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(self.name, self._base_result(), success=True)

            delivered_at = order.get("order_delivered_customer_date")
            estimated_at = order.get("order_estimated_delivery_date")
            carrier_at = order.get("order_delivered_carrier_date")

            variance_hours = None
            if pd.notna(delivered_at) and pd.notna(estimated_at):
                variance_hours = self._safe_round(
                    (delivered_at - estimated_at).total_seconds() / 3600.0
                )

            items = self.data_store.get_order_items(order_id)
            seller_handoff_analysis = []
            if items is not None and not items.empty and pd.notna(carrier_at):
                seller_handoff_analysis = self._analyze_seller_handoff(items, order_id, carrier_at)

            late_sellers = [
                s["seller_id"] for s in seller_handoff_analysis if s["late_handoff"]
            ][:3]

            return AgentResult(
                self.name,
                {
                    "delivered_at": self._format_timestamp(delivered_at),
                    "estimated_delivery_at": self._format_timestamp(estimated_at),
                    "carrier_handoff_at": self._format_timestamp(carrier_at),
                    "delivery_variance_hours": variance_hours,
                    "seller_handoff_analysis": seller_handoff_analysis,
                    "late_handoff_seller_ids": late_sellers,
                    "is_late_delivery": variance_hours is not None and variance_hours > 0,
                },
                success=True,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    def _analyze_seller_handoff(self, items: pd.DataFrame, order_id: str, carrier_at) -> List[Dict[str, Any]]:
        """Seller handoff: variance = (carrier_date - earliest shipping_limit_date) per seller."""
        limits_by_seller: Dict[str, Any] = {}
        for _, row in items.iterrows():
            sid = row["seller_id"]
            limit = row["shipping_limit_date"]
            if pd.isna(limit):
                continue
            if sid not in limits_by_seller or limit < limits_by_seller[sid]:
                limits_by_seller[sid] = limit

        analyses = []
        for sid in limits_by_seller:
            limit = limits_by_seller[sid]
            variance_hours = self._safe_round(
                (carrier_at - limit).total_seconds() / 3600.0
            )
            analyses.append({
                "seller_id": sid,
                "shipping_limit_at": self._format_timestamp(limit),
                "handoff_variance_hours": variance_hours,
                "late_handoff": variance_hours is not None and variance_hours > 0,
            })
        return analyses

    def _base_result(self) -> Dict[str, Any]:
        return {
            "delivered_at": None,
            "estimated_delivery_at": None,
            "carrier_handoff_at": None,
            "delivery_variance_hours": None,
            "seller_handoff_analysis": [],
            "late_handoff_seller_ids": [],
            "is_late_delivery": False,
        }