"""
Coordinator Agent - Điều phối toàn bộ luồng làm việc của các Agent.
"""

from typing import Dict, Any
from src.base_agent import BaseAgent, AgentResult
from src.agents.customer_agent import CustomerAgent
from src.agents.order_product_agent import OrderProductAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier import VerifierAgent


class CoordinatorAgent(BaseAgent):
    """
    Agent Coordinator quản lý pipeline:
    1. Nhận order_id và thông tin case.
    2. Gọi Customer, OrderProduct, Payment, Delivery agents.
    3. Handoff kết quả cho Policy Agent.
    4. Gửi kết quả cho Verifier Agent validate.
    5. Đóng gói JSON hoàn chỉnh.
    """

    def __init__(self, data_dir: str = "data"):
        super().__init__("CoordinatorAgent", data_dir)
        self.customer_agent = CustomerAgent(data_dir)
        self.order_product_agent = OrderProductAgent(data_dir)
        self.payment_agent = PaymentAgent(data_dir)
        self.delivery_agent = DeliveryAgent(data_dir)
        self.policy_agent = PolicyAgent(data_dir)
        self.verifier_agent = VerifierAgent(data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            case_id = case_data.get("case_id", "")
            trace_steps = []

            customer_result = self.customer_agent.process(order_id, case_data, {})
            trace_steps.append(self._make_trace_step("CustomerAgent", customer_result))

            order_result = self.order_product_agent.process(order_id, case_data, {})
            trace_steps.append(self._make_trace_step("OrderProductAgent", order_result))

            payment_result = self.payment_agent.process(order_id, case_data, {})
            trace_steps.append(self._make_trace_step("PaymentAgent", payment_result))

            delivery_result = self.delivery_agent.process(order_id, case_data, {})
            trace_steps.append(self._make_trace_step("DeliveryAgent", delivery_result))

            policy_context = {
                "CustomerAgent": customer_result.data,
                "OrderProductAgent": order_result.data,
                "PaymentAgent": payment_result.data,
                "DeliveryAgent": delivery_result.data,
            }

            policy_result = self.policy_agent.process(order_id, case_data, policy_context)
            trace_steps.append(self._make_trace_step("PolicyAgent", policy_result))

            assembled = self._assemble_output(
                case_id, order_id,
                customer_result.data,
                order_result.data,
                payment_result.data,
                delivery_result.data,
                policy_result.data,
            )

            verifier_context = {"assembled_output": assembled}
            verifier_result = self.verifier_agent.process(order_id, case_data, verifier_context)
            trace_steps.append(self._make_trace_step("VerifierAgent", verifier_result))

            final_output = verifier_result.data.get("verified_output", assembled)

            return AgentResult(
                self.name,
                {
                    "output": final_output,
                    "trace_steps": trace_steps,
                },
                success=True,
            )

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

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
        """Tạo đối tượng JSON theo đúng cấu trúc schema đề bài yêu cầu."""
        return {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": policy_data.get("primary_issue"),
                "secondary_issues": policy_data.get("secondary_issues", []),
                "case_status": policy_data.get("case_status"),
                "confidence": policy_data.get("confidence", 0.5),
            },
            "affected_entities": {
                "order_ids": [order_id] if order_data.get("order_id") else [],
                "item_ids": order_data.get("item_ids", []),
                "seller_ids": order_data.get("seller_ids", []),
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
                "seller_handoff_analysis": order_data.get("seller_handoff_analysis", []),
                "late_handoff_seller_ids": order_data.get("late_handoff_seller_ids", []),
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

    def _make_trace_step(self, agent_name: str, result: AgentResult) -> Dict[str, Any]:
        return {
            "agent": agent_name,
            "timestamp": result.timestamp,
            "success": result.success,
            "error": result.error if not result.success else "",
        }
