"""
Verifier Agent - Kiểm tra schema, giới hạn mảng (limits) và tự động tạo evidence IDs.
"""

from typing import Dict, Any
from src.base_agent import BaseAgent, AgentResult


class VerifierAgent(BaseAgent):
    """Agent validate output schema, array limits và evidence IDs."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("VerifierAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            output = context.get("assembled_output", {})
            output = self._enforce_array_limits(output)
            output = self._validate_evidence_ids(output, order_id)
            output = self._validate_confidence(output)
            output = self._validate_financial(output)

            return AgentResult(self.name, {"verified_output": output}, success=True)

        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    def _enforce_array_limits(self, output: Dict) -> Dict:
        if "affected_entities" in output:
            entities = output["affected_entities"]
            for key, limit in [("order_ids", 5), ("item_ids", 5), ("seller_ids", 3), ("payment_ids", 5)]:
                if key in entities:
                    entities[key] = entities[key][:limit]

        if "customer_context" in output and "related_order_ids" in output["customer_context"]:
            output["customer_context"]["related_order_ids"] = output["customer_context"]["related_order_ids"][:5]

        if "product_context" in output:
            pctx = output["product_context"]
            if "product_ids" in pctx:
                pctx["product_ids"] = pctx["product_ids"][:5]
            if "category_names" in pctx:
                pctx["category_names"] = pctx["category_names"][:5]

        if "root_cause_analysis" in output:
            rca = output["root_cause_analysis"]
            if "ranked_causes" in rca:
                rca["ranked_causes"] = rca["ranked_causes"][:3]
            if "responsible_parties" in rca:
                rca["responsible_parties"] = rca["responsible_parties"][:3]

        if "evidence_ids" in output:
            output["evidence_ids"] = output["evidence_ids"][:20]

        if "resolution_actions" in output:
            output["resolution_actions"] = output["resolution_actions"][:5]

        return output

    def _validate_evidence_ids(self, output: Dict, order_id: str) -> Dict:
        evidence = [f"order:{order_id}"]

        if "affected_entities" in output:
            for item_id in output["affected_entities"].get("item_ids", []):
                evidence.append(f"item:{item_id}")
            for payment_id in output["affected_entities"].get("payment_ids", []):
                evidence.append(f"payment:{payment_id}")

        if "root_cause_analysis" in output:
            for party in output["root_cause_analysis"].get("responsible_parties", []):
                if party["party_type"] == "seller":
                    evidence.append(f"seller:{party['party_id']}")
            for cause in output["root_cause_analysis"].get("ranked_causes", []):
                evidence.append(f"policy:{cause['cause_code']}")

        output["evidence_ids"] = evidence[:20]
        return output

    def _validate_confidence(self, output: Dict) -> Dict:
        if "case_assessment" in output:
            conf = output["case_assessment"].get("confidence", 0.5)
            output["case_assessment"]["confidence"] = max(0.0, min(1.0, conf))
        return output

    def _validate_financial(self, output: Dict) -> Dict:
        if "financial_resolution" in output:
            refund = output["financial_resolution"].get("recommended_refund_brl", 0)
            if refund is None:
                refund = 0.0
            output["financial_resolution"]["recommended_refund_brl"] = round(float(refund), 2)
        return output
