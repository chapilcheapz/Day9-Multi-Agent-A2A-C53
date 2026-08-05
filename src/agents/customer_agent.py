"""
Customer Agent - Xác định định danh khách hàng và lịch sử đơn hàng.
Truy cập: olist_customers_dataset, olist_orders_dataset.
Output: customer_context (customer_unique_id, related_order_ids) + complaint_summary.
"""

from typing import Any, Dict

from src.base_agent import AgentResult, BaseAgent
from src.input_reader import get_customer_message


class CustomerAgent(BaseAgent):
    """Agent định danh customer (customer_unique_id) và tra cứu lịch sử mua hàng."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("CustomerAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            customer_msg = get_customer_message(case_data)
            llm_notes = None
            llm_used = False

            if customer_msg and self.llm_client.active:
                prompt = (
                    f"Đây là lời khiếu nại của khách hàng cho đơn hàng {order_id}:\n"
                    f"\"{customer_msg}\"\n\n"
                    "Hãy tóm tắt ngắn gọn (tối đa 2 câu) loại vấn đề khách hàng nêu ra "
                    "(ví dụ: giao trễ, đơn bị hủy, thanh toán sai...). Không suy diễn thêm sự kiện."
                )
                response = self.llm_client.chat_completion(prompt, max_tokens=120)
                if not response.startswith("[Fallback"):
                    llm_used = True
                    llm_notes = response.strip()

            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(
                    self.name,
                    {
                        "customer_unique_id": None,
                        "related_order_ids": [],
                        "is_repeat_customer": False,
                        "complaint_summary": llm_notes,
                    },
                    llm_used=llm_used,
                    llm_notes=llm_notes,
                )

            customer = self.data_store.get_customer(order["customer_id"])
            if customer is None:
                return AgentResult(
                    self.name,
                    {
                        "customer_unique_id": None,
                        "related_order_ids": [],
                        "is_repeat_customer": False,
                        "complaint_summary": llm_notes,
                    },
                    llm_used=llm_used,
                    llm_notes=llm_notes,
                )

            customer_unique_id = str(customer["customer_unique_id"])
            all_orders = self.data_store.get_orders_by_customer_unique_id(customer_unique_id)
            related_order_ids = [
                oid for oid in all_orders["order_id"].tolist() if oid != order_id
            ][:5]

            return AgentResult(
                self.name,
                {
                    "customer_unique_id": customer_unique_id,
                    "related_order_ids": related_order_ids,
                    "is_repeat_customer": len(related_order_ids) > 0,
                    "complaint_summary": llm_notes,
                },
                llm_used=llm_used,
                llm_notes=llm_notes,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))
