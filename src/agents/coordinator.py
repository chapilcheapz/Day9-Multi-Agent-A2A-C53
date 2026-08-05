"""
Coordinator Agent - Điều phối luồng handoff giữa các agent:

1. Nhận case + claimed_order_id.
2. Gọi Customer, Order & Product, Payment, Delivery agents (phân tích song song về mặt logic).
3. Tổng hợp context và handoff cho Policy Agent (áp dụng EC_POLICY_V2).
4. Đóng gói output theo đúng schema đề bài.
5. Gửi cho Verifier Agent kiểm chứng trước khi ghi file.

Trace steps ghi lại handoff giữa các agent.
"""

from typing import Any, Dict, List

from src.base_agent import AgentResult, BaseAgent
from src.agents.customer_agent import CustomerAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.order_product_agent import OrderProductAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier import VerifierAgent


class CoordinatorAgent(BaseAgent):
    """Agent Coordinator điều phối toàn bộ pipeline."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("CoordinatorAgent", data_dir)
        self.customer_agent = CustomerAgent(data_dir)
        self.order_agent = OrderProductAgent(data_dir)
        self.payment_agent = PaymentAgent(data_dir)
        self.delivery_agent = DeliveryAgent(data_dir)
        self.policy_agent = PolicyAgent(data_dir)
        self.verifier_agent = VerifierAgent(data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            case_id = case_data.get("case_id", "")
            steps: List[Dict[str, Any]] = []

            customer = self.customer_agent.process(order_id, case_data, {})
            order = self.order_agent.process(order_id, case_data, {})
            payment = self.payment_agent.process(order_id, case_data, {})
            delivery = self.delivery_agent.process(order_id, case_data, {})

            for result in (customer, order, payment, delivery):
                steps.append(result.to_dict())
                if not result.success:
                    raise RuntimeError(f"{result.agent_name} failed: {result.error}")

            policy_context = {
                "CustomerAgent": customer.data,
                "OrderProductAgent": order.data,
                "PaymentAgent": payment.data,
                "DeliveryAgent": delivery.data,
            }
            policy = self.policy_agent.process(order_id, case_data, policy_context)
            steps.append(policy.to_dict())
            if not policy.success:
                raise RuntimeError(f"PolicyAgent failed: {policy.error}")

            assembled = self._assemble_output(
                case_id, order_id, customer.data, order.data,
                payment.data, delivery.data, policy.data,
            )

            verifier = self.verifier_agent.process(
                order_id, case_data, {"assembled_output": assembled}
            )
            steps.append(verifier.to_dict())
            if not verifier.success:
                raise RuntimeError(f"VerifierAgent failed: {verifier.error}")

            final_output = verifier.data.get("verified_output", assembled)

            return AgentResult(
                self.name,
                {
                    "output": final_output,
                    "trace_steps": steps,
                    "llm_claims": {
                        agent_name: {
                            "llm_used": result.llm_used,
                            "llm_notes": result.llm_notes,
                        }
                        for agent_name, result in (
                            ("CustomerAgent", customer),
                            ("OrderProductAgent", order),
                            ("PaymentAgent", payment),
                            ("DeliveryAgent", delivery),
                            ("PolicyAgent", policy),
                            ("VerifierAgent", verifier),
                        )
                    },
                },
                success=True,
            )

        except RuntimeError as e:
            return AgentResult(self.name, {}, success=False, error=str(e))
        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    # ------------------------------------------------------------ assembly
    def _assemble_output(
        self,
        case_id: str,
        order_id: str,
        customer_data: Dict,
        order_data: Dict,
        payment_data: Dict,
        delivery_data: Dict,
        policy_data: Dict,
    ) -> Dict[str, Any]:
        responsible_sellers = [
            p["party_id"] for p in policy_data.get("responsible_parties", [])
            if p.get("party_type") == "seller"
        ]
        source_sellers = order_data.get("seller_ids", [])
        seller_ids = list(dict.fromkeys(responsible_sellers + source_sellers))[:3]

        return {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": policy_data.get("primary_issue"),
                "secondary_issues": policy_data.get("secondary_issues", []),
                "case_status": policy_data.get("case_status"),
                "confidence": policy_data.get("confidence", 1.0),
            },
            "affected_entities": {
                "order_ids": [order_id],
                "item_ids": order_data.get("item_ids", []),
                "seller_ids": seller_ids,
                "payment_ids": payment_data.get("payment_ids", []),
            },
            "customer_context": {
                "customer_unique_id": customer_data.get("customer_unique_id"),
                "related_order_ids": customer_data.get("related_order_ids", []),
            },
            "product_context": {
                "product_ids": order_data.get("product_ids", []),
                "category_names": order_data.get("category_names", []),
            },
            "delivery_analysis": {
                "delivered_at": delivery_data.get("delivered_at"),
                "estimated_delivery_at": delivery_data.get("estimated_delivery_at"),
                "carrier_handoff_at": delivery_data.get("carrier_handoff_at"),
                "delivery_variance_hours": delivery_data.get("delivery_variance_hours"),
                "seller_handoff_analysis": delivery_data.get("seller_handoff_analysis", []),
                "late_handoff_seller_ids": delivery_data.get("late_handoff_seller_ids", []),
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": payment_data.get("item_total_brl"),
                "freight_total_brl": payment_data.get("freight_total_brl"),
                "expected_total_brl": payment_data.get("expected_total_brl"),
                "payment_total_brl": payment_data.get("payment_total_brl"),
                "difference_brl": payment_data.get("difference_brl"),
                "reconciled": payment_data.get("reconciled"),
                "payment_types": payment_data.get("payment_types", []),
            },
            "root_cause_analysis": {
                "ranked_causes": policy_data.get("ranked_causes", []),
                "responsible_parties": policy_data.get("responsible_parties", []),
            },
            "evidence_ids": [],
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": policy_data.get("recommended_refund_brl", 0.0),
            },
            "resolution_actions": policy_data.get("resolution_actions", []),
        }