"""
Verifier Agent - Kiểm chứng schema output trước khi ghi file:
1. Enforce giới hạn mảng (array limits).
2. Sinh evidence_ids chuẩn từ dữ liệu thật (không bịa).
3. Clamp confidence [0,1], round tiền 2 chữ số.
4. Kiểm tra null handling (order không có item -> rỗng/null).
"""

from typing import Any, Dict

from src.base_agent import AgentResult, BaseAgent

ARRAY_LIMITS = {
    "order_ids": 5,
    "item_ids": 5,
    "seller_ids": 3,
    "payment_ids": 5,
    "related_order_ids": 5,
    "product_ids": 5,
    "category_names": 5,
}


class VerifierAgent(BaseAgent):
    """Agent validate schema, giới hạn mảng và evidence IDs."""

    def __init__(self, data_dir: str = "data"):
        super().__init__("VerifierAgent", data_dir)

    def process(self, order_id: str, case_data: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        try:
            output = context.get("assembled_output", {})
            output = self._enforce_array_limits(output)
            output = self._build_evidence_ids(output, order_id)
            output = self._validate_confidence(output)
            output = self._validate_financial(output)
            output = self._validate_status_consistency(output)
            return AgentResult(self.name, {"verified_output": output}, success=True)
        except Exception as e:
            return AgentResult(self.name, {}, success=False, error=str(e))

    # ------------------------------------------------------------ helpers
    def _enforce_array_limits(self, output: Dict) -> Dict:
        entities = output.get("affected_entities", {})
        for key, limit in ARRAY_LIMITS.items():
            if key in entities and isinstance(entities[key], list):
                entities[key] = entities[key][:limit]

        cctx = output.get("customer_context", {})
        if isinstance(cctx.get("related_order_ids"), list):
            cctx["related_order_ids"] = cctx["related_order_ids"][:5]

        pctx = output.get("product_context", {})
        if isinstance(pctx.get("product_ids"), list):
            pctx["product_ids"] = pctx["product_ids"][:5]
        if isinstance(pctx.get("category_names"), list):
            pctx["category_names"] = pctx["category_names"][:5]

        rca = output.get("root_cause_analysis", {})
        if isinstance(rca.get("ranked_causes"), list):
            rca["ranked_causes"] = rca["ranked_causes"][:3]
        if isinstance(rca.get("responsible_parties"), list):
            rca["responsible_parties"] = rca["responsible_parties"][:3]

        if isinstance(output.get("evidence_ids"), list):
            output["evidence_ids"] = output["evidence_ids"][:20]
        if isinstance(output.get("resolution_actions"), list):
            output["resolution_actions"] = output["resolution_actions"][:5]
        return output

    def _build_evidence_ids(self, output: Dict, order_id: str) -> Dict:
        evidence = [f"order:{order_id}"]
        entities = output.get("affected_entities", {})
        for item_id in entities.get("item_ids", []):
            evidence.append(f"item:{item_id}")
        for payment_id in entities.get("payment_ids", []):
            evidence.append(f"payment:{payment_id}")

        rca = output.get("root_cause_analysis", {})
        for party in rca.get("responsible_parties", []):
            if party.get("party_type") == "seller":
                evidence.append(f"seller:{party['party_id']}")
        for cause in rca.get("ranked_causes", []):
            evidence.append(f"policy:{cause.get('cause_code')}")

        output["evidence_ids"] = evidence[:20]
        return output

    def _validate_confidence(self, output: Dict) -> Dict:
        assessment = output.get("case_assessment", {})
        conf = assessment.get("confidence", 0.5)
        if conf is None:
            conf = 0.5
        assessment["confidence"] = round(max(0.0, min(1.0, float(conf))), 2)
        return output

    def _validate_financial(self, output: Dict) -> Dict:
        fin = output.get("financial_resolution", {})
        refund = fin.get("recommended_refund_brl", 0)
        if refund is None:
            refund = 0.0
        fin["recommended_refund_brl"] = round(float(refund), 2)
        return output

    def _validate_status_consistency(self, output: Dict) -> Dict:
        """case_status phải = action_required khi có hoàn tiền, ngược lại no_action."""
        assessment = output.get("case_assessment", {})
        refund = output.get("financial_resolution", {}).get("recommended_refund_brl", 0)
        expected = "action_required" if refund and refund > 0 else "no_action"
        assessment["case_status"] = expected
        return output