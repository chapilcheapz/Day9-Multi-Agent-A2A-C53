"""
Payment Agent - Đối soát thanh toán.
Output: payment_reconciliation
"""

from typing import Dict, Any
import pandas as pd
from src.base_agent import BaseAgent, AgentResult


class PaymentAgent(BaseAgent):
    """Agent tổng hợp thanh toán và đối soát với tổng item + freight."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("PaymentAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            customer_msg = case_data.get("customer_request", {}).get("message", "")
            if customer_msg and self.llm_client.api_key:
                prompt = f"PaymentAgent analyzing payment reconciliation for order: {order_id}"
                _payment_reasoning = self.llm_client.chat_completion(prompt, max_tokens=50)

            payments = self.data_store.get_order_payments(order_id)
            items = self.data_store.get_order_items(order_id)

            payment_total_brl = self._safe_round(payments["payment_value"].sum()) if not payments.empty else 0.0
            payment_ids = [
                f"{order_id}:{int(row['payment_sequential'])}" for _, row in payments.iterrows()
            ][:5]
            payment_types = payments["payment_type"].unique().tolist() if not payments.empty else []

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
                reconciled = abs(difference_brl) <= 0.10

            is_split_payment = len(payments) >= 2

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
                    "is_split_payment": is_split_payment,
                    "payment_count": len(payments),
                },
                success=True,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))
