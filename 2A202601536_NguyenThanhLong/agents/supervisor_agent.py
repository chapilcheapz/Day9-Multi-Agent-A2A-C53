import json
from typing import Dict, Any
import concurrent.futures
from src.base_agent import BaseAgent, AgentResult
from src.agents.customer_agent import CustomerAgent
from src.agents.order_product_agent import OrderProductAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier import VerifierAgent
from src.llm_client import LLMClient

class SupervisorAgent(BaseAgent):
    def __init__(self, data_dir: str = "data"):
        super().__init__("SupervisorAgent", data_dir)
        self.llm = LLMClient()
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

            # Step 1: PLAN (using LLM)
            plan_prompt = f"""You are a Supervisor Agent resolving an e-commerce dispute.
Case ID: {case_id}
Order ID: {order_id}
Investigation Scope: {case_data.get('investigation_scope', [])}

Create an investigation plan outlining the steps to take.
Return ONLY JSON:
{{
  "plan": ["step 1", "step 2", "step 3"]
}}"""
            plan_res = self.llm.chat_completion(plan_prompt, max_tokens=150)
            try:
                plan_json = json.loads(plan_res.replace("```json", "").replace("```", "").strip())
                plan_details = plan_json.get("plan", [])
            except:
                plan_details = ["Investigate customer", "Investigate product", "Investigate payment", "Investigate delivery"]

            trace_steps.append({"step": "plan", "details": plan_details})

            # Step 2: DOMAIN INVESTIGATION
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                f_cust = executor.submit(self.customer_agent.process, order_id, case_data, {})
                f_order = executor.submit(self.order_product_agent.process, order_id, case_data, {})
                f_pay = executor.submit(self.payment_agent.process, order_id, case_data, {})
                f_del = executor.submit(self.delivery_agent.process, order_id, case_data, {})

                cust_res = f_cust.result()
                order_res = f_order.result()
                pay_res = f_pay.result()
                del_res = f_del.result()

            trace_steps.append({"step": "domain investigation", "agent": "CustomerAgent", "details": cust_res.data})
            trace_steps.append({"step": "domain investigation", "agent": "OrderProductAgent", "details": order_res.data})
            trace_steps.append({"step": "domain investigation", "agent": "PaymentAgent", "details": pay_res.data})
            trace_steps.append({"step": "domain investigation", "agent": "DeliveryAgent", "details": del_res.data})

            # Step 3: SYNTHESIS (using LLM)
            synthesis_prompt = f"""You are a Supervisor Agent.
Synthesize the findings from the domain agents into a cohesive summary.
Customer: {json.dumps(cust_res.data)}
Product: {json.dumps(order_res.data)}
Payment: {json.dumps(pay_res.data)}
Delivery: {json.dumps(del_res.data)}

Return ONLY JSON:
{{
  "summary": "Brief summary of the case",
  "conflict_detected": false
}}"""
            synth_res = self.llm.chat_completion(synthesis_prompt, max_tokens=200)
            try:
                synth_json = json.loads(synth_res.replace("```json", "").replace("```", "").strip())
            except:
                synth_json = {"summary": "Synthesis failed", "conflict_detected": False}

            trace_steps.append({"step": "synthesis", "details": synth_json})

            # Step 4: POLICY
            policy_context = {
                "CustomerAgent": cust_res.data,
                "OrderProductAgent": order_res.data,
                "PaymentAgent": pay_res.data,
                "DeliveryAgent": del_res.data,
                "Synthesis": synth_json
            }
            policy_result = self.policy_agent.process(order_id, case_data, policy_context)
            
            from src.agents.policy_engine import PolicyEngine
            engine = PolicyEngine()
            final_policy_data = engine.evaluate(policy_result.data, policy_context)
            
            trace_steps.append({"step": "policy", "details": final_policy_data})

            # Assemble Output
            assembled = self._assemble_output(
                case_id, order_id,
                cust_res.data,
                order_res.data,
                pay_res.data,
                del_res.data,
                final_policy_data,
            )

            # Step 5: VERIFICATION
            verifier_context = {"assembled_output": assembled}
            verifier_result = self.verifier_agent.process(order_id, case_data, verifier_context)
            trace_steps.append({"step": "verification", "details": "Verification completed"})

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
        self, case_id: str, order_id: str,
        customer_data: Dict, order_data: Dict, payment_data: Dict,
        delivery_data: Dict, policy_data: Dict
    ) -> Dict[str, Any]:
        return {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": policy_data.get("primary_issue"),
                "secondary_issues": policy_data.get("secondary_issues", []),
                "case_status": policy_data.get("case_status"),
                "confidence": policy_data.get("confidence", 0.95),
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
