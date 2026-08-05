"""
Order & Product Agent - Kiểm tra order, item, seller, product, category
và phân tích hạn bàn giao của từng seller (shipping_limit_date).
Truy cập: olist_order_items, olist_products, olist_sellers, category translation.
Output: affected_entities, product_context, seller_handoff_analysis.
"""

from typing import Any, Dict, List

import pandas as pd

from src.base_agent import AgentResult, BaseAgent
from src.input_reader import get_customer_message


class OrderProductAgent(BaseAgent):
    """Agent bóc tách thông tin item, seller, product, category và seller handoff."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("OrderProductAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            llm_used = False
            llm_notes = None
            customer_msg = get_customer_message(case_data)
            if customer_msg and self.llm_client.active:
                items_preview = self._describe_items(order_id)
                prompt = (
                    f"Đơn hàng {order_id} gồm các item:\n{items_preview}\n"
                    "Hãy nêu 1 câu nhận định về độ phức tạp của đơn (multi-item/multi-seller/đa danh mục) "
                    "dựa trên dữ liệu. Không thêm thông tin không có trong dữ liệu."
                )
                response = self.llm_client.chat_completion(prompt, max_tokens=120)
                if not response.startswith("[Fallback"):
                    llm_used = True
                    llm_notes = response.strip()

            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(self.name, self._empty_result(), llm_used=llm_used, llm_notes=llm_notes)

            items = self.data_store.get_order_items(order_id)
            if items.empty:
                res = self._empty_result()
                res["order_id"] = order_id
                res["order_status"] = order.get("order_status")
                return AgentResult(self.name, res, llm_used=llm_used, llm_notes=llm_notes)

            item_ids = [f"{order_id}:{int(row['order_item_id'])}" for _, row in items.iterrows()]
            seller_ids = items["seller_id"].unique().tolist()
            product_ids = items["product_id"].unique().tolist()

            category_names: List[str] = []
            for pid in product_ids:
                product = self.data_store.get_product(pid)
                if product is not None and pd.notna(product.get("product_category_name")):
                    cat = self.data_store.get_category_translation(product["product_category_name"])
                    if cat and cat not in category_names:
                        category_names.append(cat)

            carrier_handoff_at = order.get("order_delivered_carrier_date")
            seller_handoff_analysis = self._analyze_seller_handoff(items, seller_ids, carrier_handoff_at)

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
                    "seller_handoff_analysis": seller_handoff_analysis,
                    "late_handoff_seller_ids": [
                        s["seller_id"] for s in seller_handoff_analysis if s["late_handoff"]
                    ],
                },
                llm_used=llm_used,
                llm_notes=llm_notes,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    # ------------------------------------------------------------- helpers
    def _describe_items(self, order_id: str) -> str:
        items = self.data_store.get_order_items(order_id)
        if items.empty:
            return "(không có item)"
        lines = []
        for _, row in items.iterrows():
            lines.append(
                f"- item {row['order_item_id']}: product={row['product_id']}, "
                f"seller={row['seller_id']}, price={row['price']}, "
                f"freight={row['freight_value']}"
            )
        return "\n".join(lines)

    def _analyze_seller_handoff(
        self, items: pd.DataFrame, seller_ids: List[str], carrier_handoff_at
    ) -> List[Dict[str, Any]]:
        """Tính handoff_variance_hours = carrier_handoff - shipping_limit_date sớm nhất của seller."""
        analysis = []
        for sid in seller_ids:
            seller_items = items[items["seller_id"] == sid]
            shipping_limits = seller_items["shipping_limit_date"].dropna()

            if shipping_limits.empty:
                analysis.append({
                    "seller_id": sid,
                    "shipping_limit_at": None,
                    "handoff_variance_hours": None,
                    "late_handoff": False,
                })
                continue

            earliest_limit = shipping_limits.min()
            entry = {
                "seller_id": sid,
                "shipping_limit_at": self._format_timestamp(earliest_limit),
                "handoff_variance_hours": None,
                "late_handoff": False,
            }
            if pd.notna(carrier_handoff_at):
                variance_hours = self._safe_round(
                    (carrier_handoff_at - earliest_limit).total_seconds() / 3600.0
                )
                entry["handoff_variance_hours"] = variance_hours
                entry["late_handoff"] = carrier_handoff_at > earliest_limit
            analysis.append(entry)
        return analysis

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "order_id": None,
            "order_status": None,
            "item_ids": [],
            "seller_ids": [],
            "product_ids": [],
            "category_names": [],
            "is_multi_item": False,
            "is_multi_seller": False,
            "is_multiple_categories": False,
            "seller_handoff_analysis": [],
            "late_handoff_seller_ids": [],
        }
