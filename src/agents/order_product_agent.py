"""
Order & Product Agent - Kiểm tra đơn hàng, sản phẩm, nhà bán và danh mục.
Output: affected_entities, product_context, seller_handoff_analysis
"""

from typing import Dict, Any, List
import pandas as pd
from src.base_agent import BaseAgent, AgentResult


class OrderProductAgent(BaseAgent):
    """Agent bóc tách thông tin item, seller, product và hạn bàn giao của seller."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("OrderProductAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            customer_msg = case_data.get("customer_request", {}).get("message", "")
            if customer_msg and self.llm_client.api_key:
                prompt = f"OrderProductAgent checking product & seller limit dates for order: {order_id}"
                _order_reasoning = self.llm_client.chat_completion(prompt, max_tokens=50)

            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(self.name, self._empty_result(), success=True)

            items = self.data_store.get_order_items(order_id)
            if items.empty:
                return AgentResult(self.name, self._empty_result_with_order(order_id), success=True)

            item_ids = [f"{order_id}:{int(row['order_item_id'])}" for _, row in items.iterrows()][:5]
            seller_ids = items["seller_id"].unique().tolist()[:3]
            product_ids = items["product_id"].unique().tolist()[:5]

            category_names = []
            for pid in product_ids:
                product = self.data_store.get_product(pid)
                if product is not None and pd.notna(product.get("product_category_name")):
                    cat = product["product_category_name"]
                    eng_cat = self.data_store.get_category_translation(cat)
                    if eng_cat and eng_cat not in category_names:
                        category_names.append(eng_cat)
            category_names = category_names[:5]

            is_multi_item = len(items) >= 2
            is_multi_seller = len(items["seller_id"].unique()) >= 2
            is_multiple_categories = len(category_names) >= 2

            carrier_handoff_at = order.get("order_delivered_carrier_date")
            seller_handoff_analysis = self._analyze_seller_handoff(
                items, seller_ids, carrier_handoff_at
            )

            late_handoff_seller_ids = [
                s["seller_id"] for s in seller_handoff_analysis if s["late_handoff"]
            ]

            return AgentResult(
                self.name,
                {
                    "order_id": order_id,
                    "item_ids": item_ids,
                    "seller_ids": seller_ids,
                    "product_ids": product_ids,
                    "category_names": category_names,
                    "is_multi_item": is_multi_item,
                    "is_multi_seller": is_multi_seller,
                    "is_multiple_categories": is_multiple_categories,
                    "seller_handoff_analysis": seller_handoff_analysis,
                    "late_handoff_seller_ids": late_handoff_seller_ids,
                },
                success=True,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    def _analyze_seller_handoff(
        self, items: pd.DataFrame, seller_ids: List[str], carrier_handoff_at
    ) -> List[Dict[str, Any]]:
        """Phân tích trễ hạn bàn giao của từng seller."""
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

            if pd.isna(carrier_handoff_at):
                analysis.append({
                    "seller_id": sid,
                    "shipping_limit_at": self._format_timestamp(earliest_limit),
                    "handoff_variance_hours": None,
                    "late_handoff": False,
                })
                continue

            variance = (carrier_handoff_at - earliest_limit).total_seconds() / 3600.0
            variance = self._safe_round(variance)
            late = carrier_handoff_at > earliest_limit

            analysis.append({
                "seller_id": sid,
                "shipping_limit_at": self._format_timestamp(earliest_limit),
                "handoff_variance_hours": variance,
                "late_handoff": late,
            })

        return analysis

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "order_id": None,
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

    def _empty_result_with_order(self, order_id: str) -> Dict[str, Any]:
        res = self._empty_result()
        res["order_id"] = order_id
        return res
