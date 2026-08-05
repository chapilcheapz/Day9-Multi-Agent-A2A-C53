from typing import Dict, Any, List
import pandas as pd

class PolicyEngine:
    def __init__(self):
        self.POLICY_MAPPING = {
            "late_delivery_seller": ("SELLER_HANDOFF_AFTER_LIMIT", "refund_freight"),
            "late_delivery_logistics": ("CARRIER_DELIVERED_AFTER_ESTIMATE", "refund_freight"),
            "canceled_order_paid": ("ORDER_CANCELED_AFTER_PAYMENT", "issue_full_refund"),
            "unavailable_order_paid": ("ORDER_UNAVAILABLE_AFTER_PAYMENT", "issue_full_refund"),
            "valid_split_payment": ("MULTIPLE_PAYMENTS_RECONCILED", "explain_valid_split_payment"),
            "unsupported_late_claim": ("DELIVERY_WITHIN_ESTIMATE", "reject_late_refund"),
        }

    def evaluate(self, policy_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        primary_issue = policy_data.get("primary_issue", "unsupported_late_claim")
        
        # Override with math logic if necessary to prevent hallucination
        order_data = context.get("OrderProductAgent", {})
        payment_data = context.get("PaymentAgent", {})
        delivery_data = context.get("DeliveryAgent", {})

        payment_total = float(payment_data.get("payment_total_brl") or 0)
        freight_total = float(payment_data.get("freight_total_brl") or 0)
        
        order_status = order_data.get("order_status")

        is_late_delivery = delivery_data.get("is_late_delivery", False)
        is_split = False
        reconciled = payment_data.get("reconciled", False)
        if payment_data.get("payment_types") and len(payment_data.get("payment_types")) > 1:
            is_split = True
            
        late_sellers = delivery_data.get("late_handoff_seller_ids", []) or []

        if order_status == "canceled" and payment_total > 0:
            primary_issue = "canceled_order_paid"
        elif order_status == "unavailable" and payment_total > 0:
            primary_issue = "unavailable_order_paid"
        elif is_late_delivery:
            if late_sellers:
                primary_issue = "late_delivery_seller"
            else:
                primary_issue = "late_delivery_logistics"
        elif is_split and reconciled:
            primary_issue = "valid_split_payment"
        elif not is_late_delivery and reconciled:
            primary_issue = "unsupported_late_claim"

        mapping = self.POLICY_MAPPING[primary_issue]
        cause_code = mapping[0]
        main_action = mapping[1]

        parties = []
        if primary_issue in ["canceled_order_paid", "unavailable_order_paid"]:
            parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
        elif primary_issue == "late_delivery_seller":
            parties = [{"party_type": "seller", "party_id": s} for s in late_sellers]
        elif primary_issue == "late_delivery_logistics":
            parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]

        refund_amount = 0.0
        if main_action == "refund_freight":
            refund_amount = freight_total
        elif main_action == "issue_full_refund":
            refund_amount = payment_total

        actions = [main_action]
        if primary_issue == "late_delivery_seller": actions.append("review_seller_handoff")
        if primary_issue == "late_delivery_logistics": actions.append("review_carrier_delay")
        if refund_amount > 0: actions.append("verify_refund_completion")
        if order_data.get("is_multi_seller"): actions.append("coordinate_multi_seller_case")
        if is_split and primary_issue != "valid_split_payment": actions.append("verify_payment_allocation")
        actions = actions[:5]

        case_status = "action_required" if refund_amount > 0 else "no_action"

        return {
            "primary_issue": primary_issue,
            "secondary_issues": policy_data.get("secondary_issues", []),
            "case_status": case_status,
            "confidence": 1.0,
            "ranked_causes": [{"cause_code": cause_code, "rank": 1}],
            "responsible_parties": parties,
            "recommended_refund_brl": float(refund_amount),
            "resolution_actions": actions,
        }
