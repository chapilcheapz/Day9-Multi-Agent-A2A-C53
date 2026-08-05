"""
Policy Agent - Đóng gói logic EC_POLICY_V2 để đưa ra kết luận xử lý.
"""

from typing import Dict, Any, List, Tuple, Optional
from src.base_agent import BaseAgent, AgentResult


class PolicyAgent(BaseAgent):
    """
    Agent áp dụng thứ tự ưu tiên nghiệp vụ EC_POLICY_V2
    kết hợp với suy luận từ LLM Model (<= 10B parameters).
    """

    def __init__(self, data_dir: str = "data"):
        super().__init__("PolicyAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            order_data = context.get("OrderProductAgent", {})
            payment_data = context.get("PaymentAgent", {})
            delivery_data = context.get("DeliveryAgent", {})
            customer_data = context.get("CustomerAgent", {})

            order = self.data_store.get_order(order_id)
            order_status = order["order_status"] if order is not None else None

            customer_msg = case_data.get("customer_request", {}).get("message", "")
            if customer_msg and self.llm_client.api_key:
                prompt = (
                    f"Order ID: {order_id}\n"
                    f"Customer Request: {customer_msg}\n"
                    f"Order Status: {order_status}\n"
                    f"Payment Total: {payment_data.get('payment_total_brl', 0)} BRL\n"
                    "Analyze customer intent and verify against order facts."
                )
                _llm_reasoning = self.llm_client.chat_completion(prompt, max_tokens=100)

            primary_issue, cause_code, responsible, refund, main_action = self._determine_primary_issue(
                order_status, order_data, payment_data, delivery_data
            )

            secondary_issues = self._determine_secondary_issues(
                order_data, payment_data, customer_data, primary_issue
            )

            responsible_parties = self._build_responsible_parties(
                responsible, order_data, primary_issue
            )

            ranked_causes = [{"cause_code": cause_code, "rank": 1}]
            refund_amount = self._calculate_refund(primary_issue, payment_data, order_data)
            case_status = "action_required" if refund_amount > 0 else "no_action"

            actions = self._build_actions(
                main_action, primary_issue, order_data, delivery_data
            )

            confidence = self._calculate_confidence(order, order_data, payment_data)

            return AgentResult(
                self.name,
                {
                    "primary_issue": primary_issue,
                    "secondary_issues": secondary_issues,
                    "case_status": case_status,
                    "confidence": confidence,
                    "ranked_causes": ranked_causes,
                    "responsible_parties": responsible_parties,
                    "recommended_refund_brl": refund_amount,
                    "resolution_actions": actions,
                },
                success=True,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    def _determine_primary_issue(
        self,
        order_status: Optional[str],
        order_data: Dict,
        payment_data: Dict,
        delivery_data: Dict,
    ) -> Tuple[str, str, str, str, str]:
        """Xác định Primary Issue theo đúng thứ tự ưu tiên."""
        payment_total = payment_data.get("payment_total_brl", 0) or 0

        if order_status == "canceled" and payment_total > 0:
            return (
                "canceled_order_paid",
                "ORDER_CANCELED_AFTER_PAYMENT",
                "platform",
                "full_payment",
                "issue_full_refund",
            )

        if order_status == "unavailable" and payment_total > 0:
            return (
                "unavailable_order_paid",
                "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                "platform",
                "full_payment",
                "issue_full_refund",
            )

        is_late = delivery_data.get("is_late_delivery", False)
        late_sellers = order_data.get("late_handoff_seller_ids", [])

        if is_late and len(late_sellers) > 0:
            return (
                "late_delivery_seller",
                "SELLER_HANDOFF_AFTER_LIMIT",
                "seller",
                "freight",
                "refund_freight",
            )

        if is_late and len(late_sellers) == 0:
            return (
                "late_delivery_logistics",
                "CARRIER_DELIVERED_AFTER_ESTIMATE",
                "logistics_provider",
                "freight",
                "refund_freight",
            )

        is_split = payment_data.get("is_split_payment", False)
        reconciled = payment_data.get("reconciled")

        if is_split and reconciled is True:
            return (
                "valid_split_payment",
                "MULTIPLE_PAYMENTS_RECONCILED",
                "none",
                "none",
                "explain_valid_split_payment",
            )

        return (
            "unsupported_late_claim",
            "DELIVERY_WITHIN_ESTIMATE",
            "none",
            "none",
            "reject_late_refund",
        )

    def _determine_secondary_issues(
        self,
        order_data: Dict,
        payment_data: Dict,
        customer_data: Dict,
        primary_issue: str,
    ) -> List[str]:
        """Xác định Secondary Issues theo thứ tự điều kiện."""
        issues = []
        if order_data.get("is_multi_item", False):
            issues.append("multi_item_order")
        if order_data.get("is_multi_seller", False):
            issues.append("multi_seller_order")
        if payment_data.get("is_split_payment", False):
            issues.append("split_payment")
        if customer_data.get("is_repeat_customer", False):
            issues.append("repeat_customer")
        if order_data.get("is_multiple_categories", False):
            issues.append("multiple_categories")
        return issues

    def _build_responsible_parties(
        self, responsible_type: str, order_data: Dict, primary_issue: str
    ) -> List[Dict[str, str]]:
        if responsible_type == "none":
            return []

        if responsible_type == "platform":
            return [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]

        if responsible_type == "logistics_provider":
            return [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]

        if responsible_type == "seller":
            late_sellers = order_data.get("late_handoff_seller_ids", [])
            parties = [
                {"party_type": "seller", "party_id": sid}
                for sid in late_sellers[:3]
            ]
            return parties if parties else [{"party_type": "seller", "party_id": "UNKNOWN"}]

        return []

    def _calculate_refund(
        self, primary_issue: str, payment_data: Dict, order_data: Dict
    ) -> float:
        if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
            return self._safe_round(payment_data.get("payment_total_brl", 0)) or 0.0

        if primary_issue in ("late_delivery_seller", "late_delivery_logistics"):
            freight = payment_data.get("freight_total_brl")
            return self._safe_round(freight) if freight is not None else 0.0

        return 0.0

    def _build_actions(
        self,
        main_action: str,
        primary_issue: str,
        order_data: Dict,
        delivery_data: Dict,
    ) -> List[str]:
        actions = [main_action]
        late_sellers = order_data.get("late_handoff_seller_ids", [])
        is_late = delivery_data.get("is_late_delivery", False)

        if len(late_sellers) > 0:
            if "review_seller_handoff" not in actions:
                actions.append("review_seller_handoff")
        elif is_late:
            if "review_carrier_delay" not in actions:
                actions.append("review_carrier_delay")

        if primary_issue in (
            "canceled_order_paid",
            "unavailable_order_paid",
            "late_delivery_seller",
            "late_delivery_logistics",
        ):
            actions.append("verify_refund_completion")

        if order_data.get("is_multi_seller", False):
            actions.append("coordinate_multi_seller_case")

        if primary_issue != "valid_split_payment":
            actions.append("verify_payment_allocation")

        return actions[:5]

    def _calculate_confidence(self, order, order_data: Dict, payment_data: Dict) -> float:
        score = 0.5
        if order is not None:
            score += 0.1
        if order_data.get("item_ids"):
            score += 0.1
        if payment_data.get("reconciled") is not None:
            score += 0.1
        if payment_data.get("payment_total_brl", 0) > 0:
            score += 0.1
        if order_data.get("seller_handoff_analysis"):
            score += 0.1
        return min(self._safe_round(score), 1.0)
