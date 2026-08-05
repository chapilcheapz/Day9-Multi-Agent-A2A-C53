"""
Payment Agent - Tổng hợp payment rows và đối soát với tổng item + freight.
Truy cập: olist_order_payments, olist_order_items.
Output: payment_reconciliation.
"""

from typing import Any, Dict

from src.base_agent import AgentResult, BaseAgent
from src import config


class PaymentAgent(BaseAgent):
    """Agent đối soát thanh toán theo EC_POLICY_V2 (sai số 0.10 BRL)."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("PaymentAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            payments = self.data_store.get_order_payments(order_id)
            items = self.data_store.get_order_items(order_id)

            payment_total_brl = (
                self._safe_round(payments["payment_value"].sum()) if not payments.empty else 0.0
            )
            payment_ids = [
                f"{order_id}:{int(row['payment_sequential'])}"
                for _, row in payments.iterrows()
            ]
            payment_types = (
                payments["payment_type"].unique().tolist() if not payments.empty else []
            )

            if items.empty:
                item_total_brl = None
                freight_total_brl = None
                expected_total_brl = None
                difference_brl = None
                reconciled = None
            else:
                item_total_brl = self._safe_round(items["price"].sum())
                freight_total_brl = self._safe_round(items["freight_value"].sum())
                expected_total_brl = self._safe_round(item_total_brl + freight_total_brl)
                difference_brl = self._safe_round(payment_total_brl - expected_total_brl)
                reconciled = abs(difference_brl) <= config.RECONCILE_TOLERANCE_BRL

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
