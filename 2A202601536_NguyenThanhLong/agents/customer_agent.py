"""
Customer Agent - LLM decides flags, Python builds JSON.
"""

import json
from typing import Dict, Any
from src.base_agent import BaseAgent, AgentResult
from src.llm_client import LLMClient


class CustomerAgent(BaseAgent):
    def __init__(self, data_dir: str = "data"):
        super().__init__("CustomerAgent", data_dir)
        self.llm = LLMClient()

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            order = self.data_store.get_order(order_id)
            if order is None:
                return AgentResult(self.name, {"customer_unique_id": None, "related_order_ids": [], "is_repeat_customer": False}, success=True)

            customer = self.data_store.get_customer(order["customer_id"])
            if customer is None:
                return AgentResult(self.name, {"customer_unique_id": None, "related_order_ids": [], "is_repeat_customer": False}, success=True)

            customer_unique_id = customer["customer_unique_id"]
            orders_df = self.data_store.get_orders_by_customer_unique_id(customer_unique_id)
            all_order_ids = orders_df["order_id"].tolist() if orders_df is not None and not orders_df.empty else []
            related_order_ids = [oid for oid in all_order_ids if oid != order_id][:5]

            prompt = f"""You are the Customer Agent.

Data:
- related_order_ids: {json.dumps(related_order_ids)}

Question:
1. is_repeat_customer: Is this customer a repeat customer? (true if related_order_ids is not empty, else false)

Return ONLY JSON:
{{
    "is_repeat_customer": <boolean>
}}"""

            response_text = self.llm.chat_completion(prompt, max_tokens=30)
            clean = response_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            # Force mathematically
            is_repeat = bool(related_order_ids)

            return AgentResult(self.name, {
                "customer_unique_id": customer_unique_id,
                "related_order_ids": related_order_ids,
                "is_repeat_customer": is_repeat
            }, success=True)
        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))