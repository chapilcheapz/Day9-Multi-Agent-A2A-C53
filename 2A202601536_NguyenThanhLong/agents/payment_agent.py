"""
Payment Agent - LLM decides flags, Python builds JSON.
"""

import json
from typing import Dict, Any
from src.base_agent import BaseAgent, AgentResult
from src.llm_client import LLMClient


class PaymentAgent(BaseAgent):
    def __init__(self, data_dir: str = "data"):
        super().__init__("PaymentAgent", data_dir)
        self.llm = LLMClient()

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            payments = self.data_store.get_order_payments(order_id)
            items = self.data_store.get_order_items(order_id)

            payment_total_brl = self._safe_round(payments["payment_value"].sum()) if not payments.empty else 0.0
            payment_ids = [f"{order_id}:{int(r['payment_sequential'])}" for _, r in payments.iterrows()][:5]
            payment_types = payments["payment_type"].unique().tolist() if not payments.empty else []
            payment_count = len(payments)

            if items.empty:
                item_total_brl = 0.0
                freight_total_brl = 0.0
                expected_total_brl = None
                difference_brl = None
            else:
                item_total_brl = self._safe_round(items["price"].sum())
                freight_total_brl = self._safe_round(items["freight_value"].sum())
                expected_total_brl = self._safe_round(item_total_brl + freight_total_brl)
                difference_brl = self._safe_round(payment_total_brl - expected_total_brl)

            prompt = f"""You are the Payment Agent.

Data:
- difference_brl: {difference_brl}
- payment_count: {payment_count}

Rules:
- reconciled: true if absolute difference_brl <= 0.10, false otherwise. If difference_brl is None, reconciled must be null.
- is_split_payment: true if payment_count >= 2, false otherwise.

Return ONLY JSON:
{{
    "reconciled": <boolean_or_null>,
    "is_split_payment": <boolean>
}}"""

            response_text = self.llm.chat_completion(prompt, max_tokens=30)
            clean = response_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)

            # Force mathematically
            rec = None
            if difference_brl is not None:
                rec = abs(difference_brl) <= 0.10
                
            is_split = payment_count >= 2

            return AgentResult(self.name, {
                "item_total_brl": item_total_brl,
                "freight_total_brl": freight_total_brl,
                "expected_total_brl": expected_total_brl,
                "payment_total_brl": payment_total_brl,
                "difference_brl": difference_brl,
                "reconciled": rec,
                "is_split_payment": is_split,
                "payment_ids": payment_ids,
                "payment_types": payment_types,
                "payment_count": payment_count
            }, success=True)
        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))