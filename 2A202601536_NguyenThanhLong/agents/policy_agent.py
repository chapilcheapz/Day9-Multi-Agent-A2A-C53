"""
Policy Agent - Áp dụng EC_POLICY_V2.
Kiến trúc: LLM nhận định tình huống và đưa ra phán quyết (primary_issue). 
Python thực thi việc lắp ráp JSON output theo quy định của EC_POLICY_V2 dựa trên phán quyết của LLM.
"""

import json
from typing import Dict, Any
from src.base_agent import BaseAgent, AgentResult
from src.llm_client import LLMClient


class PolicyAgent(BaseAgent):
    def __init__(self, data_dir: str = "data"):
        super().__init__("PolicyAgent", data_dir)
        self.llm = LLMClient()

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            order = self.data_store.get_order(order_id)
            order_status = order["order_status"] if order is not None else None

            order_data = context.get("OrderProductAgent", {})
            payment_data = context.get("PaymentAgent", {})
            delivery_data = context.get("DeliveryAgent", {})
            customer_data = context.get("CustomerAgent", {})

            payment_total = float(payment_data.get("payment_total_brl") or 0)
            freight_total = float(payment_data.get("freight_total_brl") or 0)
            is_late = bool(delivery_data.get("is_late_delivery", False))
            late_sellers = delivery_data.get("late_handoff_seller_ids", []) or []
            is_split = bool(payment_data.get("is_split_payment", False))
            reconciled = payment_data.get("reconciled")

            # LLM đóng vai trò quyết định Taxonomy, Responsibility, Refund và Actions
            llm_prompt = f"""You are the Policy Agent for an e-commerce platform.
Apply EC_POLICY_V2 to determine the case resolution.

Facts:
- order_status: {order_status}
- payment_total_brl: {payment_total}
- freight_total_brl: {freight_total}
- is_late_delivery: {str(is_late).lower()}
- late_handoff_seller_ids: {json.dumps(late_sellers)}
- is_split_payment: {str(is_split).lower()}
- payment_reconciled: {str(reconciled).lower() if reconciled is not None else "null"}
- is_multi_seller: {str(order_data.get("is_multi_seller")).lower()}

EC_POLICY_V2 RULES (Select the FIRST matching issue):
1. 'canceled_order_paid': order_status is 'canceled' AND payment_total > 0
   -> Cause: ORDER_CANCELED_AFTER_PAYMENT, Party: platform (OLIST_PLATFORM), Refund: payment_total, Main Action: issue_full_refund
2. 'unavailable_order_paid': order_status is 'unavailable' AND payment_total > 0
   -> Cause: ORDER_UNAVAILABLE_AFTER_PAYMENT, Party: platform (OLIST_PLATFORM), Refund: payment_total, Main Action: issue_full_refund
3. 'late_delivery_seller': is_late_delivery is true AND late_handoff_seller_ids is not empty
   -> Cause: SELLER_HANDOFF_AFTER_LIMIT, Party: seller (use late_handoff_seller_ids), Refund: freight_total, Main Action: refund_freight
4. 'late_delivery_logistics': is_late_delivery is true AND late_handoff_seller_ids is empty
   -> Cause: CARRIER_DELIVERED_AFTER_ESTIMATE, Party: logistics_provider (LOGISTICS_PROVIDER), Refund: freight_total, Main Action: refund_freight
5. 'valid_split_payment': is_split_payment is true AND payment_reconciled is true
   -> Cause: MULTIPLE_PAYMENTS_RECONCILED, Party: none, Refund: 0.0, Main Action: explain_valid_split_payment
6. 'unsupported_late_claim': (fallback if none match)
   -> Cause: DELIVERY_WITHIN_ESTIMATE, Party: none, Refund: 0.0, Main Action: reject_late_refund

Actions rule: Add main action first. Then add 'review_seller_handoff' if late_delivery_seller, or 'review_carrier_delay' if late_delivery_logistics. Add 'verify_refund_completion' if refund > 0. Add 'coordinate_multi_seller_case' if is_multi_seller is true. Add 'verify_payment_allocation' if issue is NOT valid_split_payment. Max 5 actions.

CRITICAL: Before returning the JSON, you MUST write a <thought> block. Step-by-step verify every single rule. Calculate the delivery difference. Only after writing at least 150 words of thought, output the JSON.

Return ONLY a valid JSON object after the thought block:
{{
  "primary_issue": "<selected_issue>",
  "case_status": "<action_required if refund > 0 else no_action>",
  "confidence": <float between 0.75 and 0.99>,
  "ranked_causes": [{{"cause_code": "<cause>", "rank": 1}}],
  "responsible_parties": [{{"party_type": "<type>", "party_id": "<id>"}}],
  "recommended_refund_brl": <number>,
  "resolution_actions": ["<action1>", "<action2>"]
}}"""

            response_text = self.llm.chat_completion(llm_prompt, max_tokens=1000)
            clean = response_text.replace("```json", "").replace("```", "").strip()
            try:
                # Split by thought block if exists
                if "</thought>" in clean:
                    clean = clean.split("</thought>")[-1]
                
                # Better: match from the first { to the last }
                first_brace = clean.find('{')
                last_brace = clean.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = clean[first_brace:last_brace+1]
                    llm_decision = json.loads(json_str)
                else:
                    llm_decision = json.loads(clean)
            except Exception:
                llm_decision = {}

            primary_issue = llm_decision.get("primary_issue", "unsupported_late_claim")
            
            result = {
                "primary_issue": primary_issue,
                "secondary_issues": [],
                "case_status": llm_decision.get("case_status", "no_action"),
                "confidence": 1.0,
                "ranked_causes": llm_decision.get("ranked_causes", []),
                "responsible_parties": llm_decision.get("responsible_parties", []),
                "recommended_refund_brl": float(llm_decision.get("recommended_refund_brl", 0.0)),
                "resolution_actions": llm_decision.get("resolution_actions", []),
            }

            return AgentResult(self.name, result, success=True)
        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))