"""
Customer Agent - Phân tích định danh khách hàng và lịch sử đơn hàng.
Output: customer_context (customer_unique_id, related_order_ids)
"""

from typing import Dict, Any
from src.base_agent import BaseAgent, AgentResult


class CustomerAgent(BaseAgent):
    """Agent xác định customer identity và tra cứu các đơn hàng lịch sử."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("CustomerAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            customer_msg = case_data.get("customer_request", {}).get("message", "")
            if customer_msg and self.llm_client.api_key:
                prompt = f"CustomerAgent analyzing customer identity & request: {customer_msg}"
                _customer_reasoning = self.llm_client.chat_completion(prompt, max_tokens=50)

            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(
                    self.name,
                    {"customer_unique_id": None, "related_order_ids": [], "is_repeat_customer": False},
                    success=True,
                )

            customer_id = order["customer_id"]
            customer = self.data_store.get_customer(customer_id)

            if customer is None:
                return AgentResult(
                    self.name,
                    {"customer_unique_id": None, "related_order_ids": [], "is_repeat_customer": False},
                    success=True,
                )

            customer_unique_id = customer["customer_unique_id"]

            all_orders = self.data_store.get_orders_by_customer_unique_id(customer_unique_id)
            related_order_ids = [
                oid for oid in all_orders["order_id"].tolist() if oid != order_id
            ]
            related_order_ids = related_order_ids[:5]
            is_repeat_customer = len(related_order_ids) > 0

            return AgentResult(
                self.name,
                {
                    "customer_unique_id": customer_unique_id,
                    "related_order_ids": related_order_ids,
                    "is_repeat_customer": is_repeat_customer,
                },
                success=True,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))
