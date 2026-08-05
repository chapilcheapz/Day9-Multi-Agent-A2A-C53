"""
Payment Agent - Tổng hợp payment rows và đối soát với tổng item + freight.
Truy cập: olist_order_payments, olist_order_items.
Output: payment_reconciliation.

item_total_brl/freight_total_brl/payment_total_brl luôn là số (0.0 khi không có
dữ liệu); expected_total/difference/reconciled là null khi order không có item.
"""

from typing import Any, Dict

from src import config
from src.base_agent import AgentResult, BaseAgent


class PaymentAgent(BaseAgent):
    """Agent đối soát thanh toán theo EC_POLICY_V2 (sai số 0.10 BRL)."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("PaymentAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            payments = self.data_store.get_order_payments(order_id)
            items = self.data_store.get_order_items(order_id)

            payment_total_brl = self._safe_round(payments["payment_value"].sum()) or 0.0
            payment_ids = [
                f"{order_id}:{int(row['payment_sequential'])}" for _, row in payments.iterrows()
            ]
            payment_types = payments["payment_type"].unique().tolist() if not payments.empty else []

            item_total_brl = 0.0
            freight_total_brl = 0.0
            if not items.empty:
                item_total_brl = self._safe_round(items["price"].sum()) or 0.0
                freight_total_brl = self._safe_round(items["freight_value"].sum()) or 0.0

            if items.empty:
                expected_total_brl = None
                difference_brl = None
                reconciled = None
            else:
                expected_total_brl = self._safe_round(item_total_brl + freight_total_brl)
                difference_brl = self._safe_round(payment_total_brl - expected_total_brl)
                reconciled = difference_brl is not None and abs(difference_brl) <= config.RECONCILE_TOLERANCE_BRL

            return AgentResult(
                self.name,
                {
                    "payment_ids": payment_ids,
                    "payment_total_brl": payment_total_brl,
                    "item_total_brl": item_total_brl,
                    "freight_total_brl": freight_total_brl,
                    "expected_total_brl": expected_total_brl,
                    "difference_brl": difference_brl,
                    "reconciled": reconciled,
                    "payment_types": payment_types,
                    "is_split_payment": len(payments) >= 2,
                    "payment_count": len(payments),
                },
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))