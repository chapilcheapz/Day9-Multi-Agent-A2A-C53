"""
Policy Agent - Áp dụng EC_POLICY_V2 để xác định primary/secondary issue,
bên chịu trách nhiệm, khoản hoàn đề xuất và hành động xử lý.

Nhận context đã được các agent nhánh xác minh từ Coordinator. Rule engine là
nguồn quyết định cuối cùng (ưu tiên dữ liệu kiểm chứng); LLM (<10B) đóng vai
trò đề xuất được so khớp với quy tắc nghiệp vụ.
"""

from typing import Any, Dict, List

from src import config
from src.base_agent import AgentResult, BaseAgent
from src.input_reader import get_customer_message

PRIMARY_TYPES: Dict[str, Dict[str, Any]] = {
    "canceled_order_paid": {
        "root_cause": "ORDER_CANCELED_AFTER_PAYMENT",
        "party_type": "platform",
        "party_id": "OLIST_PLATFORM",
        "refund": "full_payment",
        "main_action": "issue_full_refund",
    },
    "unavailable_order_paid": {
        "root_cause": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "party_type": "platform",
        "party_id": "OLIST_PLATFORM",
        "refund": "full_payment",
        "main_action": "issue_full_refund",
    },
    "late_delivery_seller": {
        "root_cause": "SELLER_HANDOFF_AFTER_LIMIT",
        "party_type": "seller",
        "party_id": None,
        "refund": "freight",
        "main_action": "refund_freight",
    },
    "late_delivery_logistics": {
        "root_cause": "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "party_type": "logistics_provider",
        "party_id": "LOGISTICS_PROVIDER",
        "refund": "freight",
        "main_action": "refund_freight",
    },
    "valid_split_payment": {
        "root_cause": "MULTIPLE_PAYMENTS_RECONCILED",
        "party_type": "none",
        "party_id": None,
        "refund": "none",
        "main_action": "explain_valid_split_payment",
    },
    "unsupported_late_claim": {
        "root_cause": "DELIVERY_WITHIN_ESTIMATE",
        "party_type": "none",
        "party_id": None,
        "refund": "none",
        "main_action": "reject_late_refund",
    },
}


class PolicyAgent(BaseAgent):
    """Agent áp dụng quy tắc nghiệp vụ EC_POLICY_V2 kết hợp suy luận LLM."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("PolicyAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            order_data = context.get("OrderProductAgent", {})
            payment_data = context.get("PaymentAgent", {})
            delivery_data = context.get("DeliveryAgent", {})
            customer_data = context.get("CustomerAgent", {})

            primary_issue = self._determine_primary_issue(order_data, payment_data, delivery_data)
            spec = PRIMARY_TYPES[primary_issue]
            secondary_issues = self._determine_secondary_issues(order_data, payment_data, customer_data)
            responsible_parties = self._build_responsible_parties(spec, delivery_data)
            refund_amount = self._calculate_refund(primary_issue, payment_data)
            case_status = "action_required" if refund_amount and refund_amount > 0 else "no_action"
            actions = self._build_actions(primary_issue, secondary_issues)

            llm_used = False
            llm_agree = False
            customer_msg = get_customer_message(case_data)
            if self.llm_client.active:
                prompt = (
                    f"Order ID: {order_id}\nCustomer request: {customer_msg}\n"
                    f"Order status: {order_data.get('order_status')}\n"
                    f"Delivery variance hours: {delivery_data.get('delivery_variance_hours')}\n"
                    f"Late handoff sellers: {delivery_data.get('late_handoff_seller_ids', [])}\n"
                    f"Payment total: {payment_data.get('payment_total_brl', 0)} BRL\n"
                    f"Freight total: {payment_data.get('freight_total_brl')} BRL\n"
                    f"Reconciled: {payment_data.get('reconciled')}\n"
                    "The rule engine classified this case as: {primary_issue}. "
                    "Nếu bạn đồng ý, hãy trả lời AGREE; nếu không, nêu lý do ngắn gọn."
                )
                response = self.llm_client.chat_completion(prompt, max_tokens=60)
                if not response.startswith("[Fallback"):
                    llm_used = True
                    llm_agree = "AGREE" in response.upper()

            return AgentResult(
                self.name,
                {
                    "primary_issue": primary_issue,
                    "secondary_issues": secondary_issues,
                    "case_status": case_status,
                    "confidence": 1.0,
                    "ranked_causes": [{"cause_code": spec["root_cause"], "rank": 1}],
                    "responsible_parties": responsible_parties,
                    "recommended_refund_brl": refund_amount,
                    "resolution_actions": actions,
                    "llm_agreed": llm_agree,
                },
                llm_used=llm_used,
                llm_notes=("AGREE" if llm_agree else response) if llm_used else None,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    # ------------------------------------------------------------ business
    def _determine_primary_issue(
        self, order_data: Dict, payment_data: Dict, delivery_data: Dict
    ) -> str:
        order_status = order_data.get("order_status")
        payment_total = payment_data.get("payment_total_brl", 0) or 0
        variance = delivery_data.get("delivery_variance_hours")
        late_sellers = delivery_data.get("late_handoff_seller_ids", [])
        reconciled = payment_data.get("reconciled")

        if order_status == "canceled" and payment_total > 0:
            return "canceled_order_paid"
        if order_status == "unavailable" and payment_total > 0:
            return "unavailable_order_paid"
        if variance is not None and variance > 0 and late_sellers:
            return "late_delivery_seller"
        if variance is not None and variance > 0:
            return "late_delivery_logistics"
        if payment_data.get("is_split_payment", False) and reconciled is True:
            return "valid_split_payment"
        if variance is not None and variance <= 0 and reconciled is True:
            return "unsupported_late_claim"
        return "unsupported_late_claim"

    def _determine_secondary_issues(
        self, order_data: Dict, payment_data: Dict, customer_data: Dict
    ) -> List[str]:
        conditions = {
            "multi_item_order": order_data.get("is_multi_item", False),
            "multi_seller_order": order_data.get("is_multi_seller", False),
            "split_payment": payment_data.get("is_split_payment", False),
            "repeat_customer": customer_data.get("is_repeat_customer", False),
            "multiple_categories": order_data.get("is_multiple_categories", False),
        }
        return [key for key in config.SECONDARY_ISSUE_ORDER if conditions.get(key)]

    def _build_responsible_parties(self, spec: Dict, delivery_data: Dict) -> List[Dict[str, str]]:
        if spec["party_type"] in ("platform", "logistics_provider"):
            return [{"party_type": spec["party_type"], "party_id": spec["party_id"]}]
        if spec["party_type"] == "seller":
            late_sellers = delivery_data.get("late_handoff_seller_ids", [])[: config.MAX_SELLER_IDS]
            if late_sellers:
                return [{"party_type": "seller", "party_id": sid} for sid in late_sellers]
            return [{"party_type": "seller", "party_id": "UNKNOWN"}]
        return []

    def _calculate_refund(self, primary_issue: str, payment_data: Dict) -> float:
        spec = PRIMARY_TYPES[primary_issue]
        if spec["refund"] == "full_payment":
            return self._safe_round(payment_data.get("payment_total_brl", 0)) or 0.0
        if spec["refund"] == "freight":
            return self._safe_round(payment_data.get("freight_total_brl")) or 0.0
        return 0.0

    def _build_actions(
        self, primary_issue: str, secondary: List[str]
    ) -> List[str]:
        actions = [PRIMARY_TYPES[primary_issue]["main_action"]]
        if primary_issue == "late_delivery_seller":
            actions.append("review_seller_handoff")
        elif primary_issue == "late_delivery_logistics":
            actions.append("review_carrier_delay")
        elif primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
            actions.append("verify_refund_completion")
        if "multi_seller_order" in secondary:
            actions.append("coordinate_multi_seller_case")
        if "split_payment" in secondary and primary_issue != "valid_split_payment":
            actions.append("verify_payment_allocation")
        return actions[: config.MAX_RESOLUTION_ACTIONS]