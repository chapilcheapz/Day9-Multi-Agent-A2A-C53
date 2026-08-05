"""
Delivery Agent - LLM decides flags, Python builds JSON.
"""

import json
from typing import Dict, Any
import pandas as pd
from src.base_agent import BaseAgent, AgentResult
from src.llm_client import LLMClient


class DeliveryAgent(BaseAgent):
    def __init__(self, data_dir: str = "data"):
        super().__init__("DeliveryAgent", data_dir)
        self.llm = LLMClient()

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(self.name, {}, success=False)

            delivered_at = order["order_delivered_customer_date"]
            estimated_at = order["order_estimated_delivery_date"]
            carrier_at = order["order_delivered_carrier_date"]

            delivery_variance_hours = None
            if pd.notna(delivered_at) and pd.notna(estimated_at):
                delivery_variance_hours = self._safe_round((delivered_at - estimated_at).total_seconds() / 3600.0)

            items = self.data_store.get_order_items(order_id)
            sellers_raw = []
            if not items.empty:
                for seller_id in items["seller_id"].unique():
                    seller_items = items[items["seller_id"] == seller_id]
                    limits = seller_items["shipping_limit_date"].dropna()
                    if limits.empty:
                        sellers_raw.append({"seller_id": seller_id, "shipping_limit_at": None, "handoff_variance_hours": None})
                    else:
                        earliest = limits.min()
                        variance = None
                        if pd.notna(carrier_at):
                            variance = self._safe_round((carrier_at - earliest).total_seconds() / 3600.0)
                        sellers_raw.append({
                            "seller_id": seller_id,
                            "shipping_limit_at": earliest,
                            "handoff_variance_hours": variance,
                        })
                        
            is_late_val = delivery_variance_hours is not None and delivery_variance_hours > 0
            late_sellers_list = [s["seller_id"] for s in sellers_raw if s["handoff_variance_hours"] is not None and s["handoff_variance_hours"] > 0]

            prompt = f"""You are the Delivery Agent.

Data:
- delivery_variance_hours: {delivery_variance_hours}
- sellers_late_handoff: {json.dumps(late_sellers_list)}

Rules:
- is_late_delivery: true if delivery_variance_hours > 0, else false
- late_handoff_seller_ids: output the sellers_late_handoff list

Return ONLY JSON:
{{
    "is_late_delivery": <boolean>,
    "late_handoff_seller_ids": <array_of_ids>
}}"""

            response_text = self.llm.chat_completion(prompt, max_tokens=50)
            clean = response_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            
            # Force mathematically
            is_late_delivery = False
            if pd.notna(delivered_at) and pd.notna(estimated_at):
                is_late_delivery = delivered_at > estimated_at
            late_handoff_seller_ids = late_sellers_list

            seller_analysis = []
            if pd.notna(carrier_at):
                for s in sellers_raw:
                    seller_analysis.append({
                        "seller_id": s["seller_id"],
                        "shipping_limit_at": self._format_timestamp(s["shipping_limit_at"]),
                        "handoff_variance_hours": s["handoff_variance_hours"],
                        "late_handoff": s["seller_id"] in late_handoff_seller_ids
                    })

            return AgentResult(self.name, {
                "delivered_at": self._format_timestamp(delivered_at),
                "estimated_delivery_at": self._format_timestamp(estimated_at),
                "carrier_handoff_at": self._format_timestamp(carrier_at),
                "delivery_variance_hours": delivery_variance_hours,
                "is_late_delivery": is_late_delivery,
                "seller_handoff_analysis": seller_analysis,
                "late_handoff_seller_ids": late_handoff_seller_ids
            }, success=True)
        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))