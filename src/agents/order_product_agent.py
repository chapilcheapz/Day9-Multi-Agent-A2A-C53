"""
Order & Product Agent - Kiểm tra order, item, seller, product, category.
Truy cập: olist_order_items, olist_products.
Output: affected_entities (item/seller/product ids), product_context (raw categories).
"""

from typing import Any, Dict, List

import pandas as pd

from src.base_agent import AgentResult, BaseAgent
from src.input_reader import get_customer_message


class OrderProductAgent(BaseAgent):
    """Agent bóc tách thông tin item, seller, product và category (tên gốc CSV)."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("OrderProductAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            llm_used = False
            llm_notes = None
            customer_msg = get_customer_message(case_data)
            if customer_msg and self.llm_client.active:
                prompt = (
                    f"Order {order_id}: tổng hợp các item, seller, product trong đơn.\n"
                    "Trả lời 1 câu nhận định về độ phức tạp của đơn (multi-item/multi-seller/đa danh mục)."
                )
                response = self.llm_client.chat_completion(prompt, max_tokens=100)
                if not response.startswith("[Fallback"):
                    llm_used = True
                    llm_notes = response.strip()

            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(self.name, self._empty_result(order_status=None), llm_used=llm_used, llm_notes=llm_notes)

            items = self.data_store.get_order_items(order_id)
            if items.empty:
                res = self._empty_result(order.get("order_status"))
                res["order_id"] = order_id
                return AgentResult(self.name, res, llm_used=llm_used, llm_notes=llm_notes)

            item_ids = [f"{order_id}:{int(row['order_item_id'])}" for _, row in items.iterrows()]
            seller_ids = self._stable_unique(items["seller_id"].tolist())
            product_ids = self._stable_unique(items["product_id"].tolist())

            category_names: List[str] = []
            for pid in product_ids:
                product = self.data_store.get_product(pid)
                if product is not None and pd.notna(product.get("product_category_name")):
                    cat = str(product["product_category_name"])
                    if cat and cat not in category_names:
                        category_names.append(cat)

            return AgentResult(
                self.name,
                {
                    "order_id": order_id,
                    "order_status": order.get("order_status"),
                    "item_ids": item_ids,
                    "seller_ids": seller_ids,
                    "product_ids": product_ids,
                    "category_names": category_names,
                    "is_multi_item": len(items) >= 2,
                    "is_multi_seller": len(seller_ids) >= 2,
                    "is_multiple_categories": len(category_names) >= 2,
                },
                llm_used=llm_used,
                llm_notes=llm_notes,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    @staticmethod
    def _stable_unique(values: List[str]) -> List[str]:
        return list(dict.fromkeys(values))

    def _empty_result(self, order_status=None) -> Dict[str, Any]:
        return {
            "order_id": None,
            "order_status": order_status,
            "item_ids": [],
            "seller_ids": [],
            "product_ids": [],
            "category_names": [],
            "is_multi_item": False,
            "is_multi_seller": False,
            "is_multiple_categories": False,
        }