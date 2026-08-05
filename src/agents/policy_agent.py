"""
Policy Agent - Áp dụng EC_POLICY_V2 để xác định primary/secondary issue,
bên chịu trách nhiệm, khoản hoàn đề xuất và hành động xử lý.

Nhận context đã được các agent nhánh xác minh từ Coordinator (không truy cập
trực tiếp database - chỉ đọc để lấy order_status cho suy luận LLM).

Nguyên tắc: rule engine là nguồn quyết định cuối cùng (ưu tiên dữ liệu kiểm chứng).
LLM (<10B) đóng vai trò đề xuất/second opinion, kết quả được so khớp với quy tắc
nghiệp vụ để điều chỉnh confidence, tránh LLM tự bịa sự kiện.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from src.base_agent import AgentResult, BaseAgent
from src import config
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
            customer_msg = get_customer_message(case_data)

            # --- Xác định primary issue bằng rule engine (theo thứ tự ưu tiên)
            primary_issue = self._determine_primary_issue(order_data, payment_data, delivery_data)
            spec = PRIMARY_TYPES[primary_issue]

            # --- Secondary issues theo đúng thứ tự
            secondary_issues = self._determine_secondary_issues(
                order_data, payment_data, customer_data
            )

            responsible_parties = self._build_responsible_parties(spec, order_data)
            refund_amount = self._calculate_refund(primary_issue, payment_data)
            case_status = "action_required" if refund_amount and refund_amount > 0 else "no_action"
            actions = self._build_actions(spec, order_data, delivery_data, primary_issue)
            confidence = self._calculate_confidence(order_data, payment_data)

            # --- LLM đề xuất (advisory) + so khớp để điều chỉnh confidence
            llm_used = False
            llm_proposal = None
            llm_agree = False
            if order_msg := self._build_llm_prompt(order_id, order_data, payment_data, delivery_data, customer_msg):
                if self.llm_client.active:
                    response = self.llm_client.chat_completion(
                        order_msg,
                        system_prompt=(
                            "You are a policy adjudicator for EC_POLICY_V2 on an e-commerce dispute. "
                            "Return ONLY a JSON object with keys: primary_issue, refund_brl, recommendation (one short sentence). "
                            "Choose primary_issue from: canceled_order_paid, unavailable_order_paid, "
                            "late_delivery_seller, late_delivery_logistics, valid_split_payment, unsupported_late_claim."
                        ),
                        max_tokens=180,
                    )
                    if not response.startswith("[Fallback"):
                        llm_used = True
                        llm_proposal = self.llm_client.extract_json(response)
                        if llm_proposal and llm_proposal.get("primary_issue") == primary_issue:
                            llm_agree = True
                            confidence = min(self._safe_round(confidence + 0.05), 1.0)

            return AgentResult(
                self.name,
                {
                    "primary_issue": primary_issue,
                    "secondary_issues": secondary_issues,
                    "case_status": case_status,
                    "confidence": confidence,
                    "ranked_causes": [{"cause_code": spec["root_cause"], "rank": 1}],
                    "responsible_parties": responsible_parties,
                    "recommended_refund_brl": refund_amount,
                    "resolution_actions": actions,
                    "llm_proposal": llm_proposal,
                    "llm_agreed": llm_agree,
                },
                llm_used=llm_used,
                llm_notes=(json.dumps(llm_proposal, ensure_ascii=False) if llm_proposal else None),
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    # ------------------------------------------------------------ business
    def _determine_primary_issue(
        self, order_data: Dict, payment_data: Dict, delivery_data: Dict
    ) -> str:
        order_status = order_data.get("order_status")
        payment_total = payment_data.get("payment_total_brl", 0) or 0

        if order_status == "canceled" and payment_total > 0:
            return "canceled_order_paid"
        if order_status == "unavailable" and payment_total > 0:
            return "unavailable_order_paid"

        is_late = delivery_data.get("is_late_delivery", False)
        late_sellers = order_data.get("late_handoff_seller_ids", [])
        if is_late:
            return "late_delivery_seller" if late_sellers else "late_delivery_logistics"

        if payment_data.get("is_split_payment", False) and payment_data.get("reconciled") is True:
            return "valid_split_payment"

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

    def _build_responsible_parties(self, spec: Dict, order_data: Dict) -> List[Dict[str, str]]:
        if spec["party_type"] in ("platform", "logistics_provider"):
            return [{"party_type": spec["party_type"], "party_id": spec["party_id"]}]

        if spec["party_type"] == "seller":
            late_sellers = order_data.get("late_handoff_seller_ids", [])[:config.MAX_SELLER_IDS]
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
        self, spec: Dict, order_data: Dict, delivery_data: Dict, primary_issue: str
    ) -> List[str]:
        actions = [spec["main_action"]]
        late_sellers = order_data.get("late_handoff_seller_ids", [])

        if late_sellers and "review_seller_handoff" not in actions:
            actions.append("review_seller_handoff")
        elif delivery_data.get("is_late_delivery", False) and "review_carrier_delay" not in actions:
            actions.append("review_carrier_delay")

        if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
            actions.append("verify_refund_completion")

        if order_data.get("is_multi_seller", False):
            actions.append("coordinate_multi_seller_case")

        if primary_issue != "valid_split_payment" and "verify_payment_allocation" not in actions:
            actions.append("verify_payment_allocation")

        return actions[: config.MAX_RESOLUTION_ACTIONS]

    def _calculate_confidence(self, order_data: Dict, payment_data: Dict) -> float:
        score = 0.45
        if order_data.get("order_status"):
            score += 0.1
        if order_data.get("item_ids"):
            score += 0.1
        if payment_data.get("reconciled") is not None:
            score += 0.05
        if payment_data.get("reconciled") is True:
            score += 0.05
        if order_data.get("seller_handoff_analysis"):
            score += 0.1
        if payment_data.get("payment_total_brl", 0) > 0:
            score += 0.05
        return min(self._safe_round(score), 1.0)

    # ------------------------------------------------------------- prompts
    def _build_llm_prompt(
        self, order_id: str, order_data: Dict, payment_data: Dict, delivery_data: Dict, customer_msg: str
    ) -> str:
        line = []
        line.append(f"Order ID: {order_id}")
        line.append(f"Customer request: {customer_msg}")
        if order_data.get("order_status"):
            line.append(f"Order status: {order_data['order_status']}")
        line.append(f"Delivered at: {delivery_data.get('delivered_at')}")
        line.append(f"Estimated delivery: {delivery_data.get('estimated_delivery_at')}")
        line.append(
            f"Late handoff sellers: {order_data.get('late_handoff_seller_ids', [])}"
        )
        line.append(f"Payment total (BRL): {payment_data.get('payment_total_brl', 0)}")
        line.append(f"Freight total (BRL): {payment_data.get('freight_total_brl')}")
        line.append(f"Reconciled within 0.10 BRL: {payment_data.get('reconciled')}")
        line.append(
            "Determine the primary issue per EC_POLICY_V2. ONLY use the facts above."
        )
        return "\n".join(line)