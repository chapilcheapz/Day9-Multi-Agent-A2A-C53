from typing import Dict, Any

from src.base_agent import BaseAgent, AgentResult


class VerifierAgent(BaseAgent):
    def __init__(self, data_dir: str = "data"):
        super().__init__("VerifierAgent", data_dir)

    def process(
        self,
        order_id: str,
        case_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> AgentResult:

        try:
            output = context.get("assembled_output", {})

            self._limit_arrays(output)
            self._build_evidence(output, order_id)
            self._normalize_confidence(output)
            self._normalize_financial(output)

            return AgentResult(
                self.name,
                {"verified_output": output},
                success=True,
            )

        except Exception as e:
            return AgentResult(
                self.name,
                {},
                success=False,
                error=str(e),
            )

    def _limit_arrays(self, output):

        entities = output.get("affected_entities", {})

        entities["order_ids"] = entities.get("order_ids", [])[:5]
        entities["item_ids"] = entities.get("item_ids", [])[:5]
        entities["seller_ids"] = entities.get("seller_ids", [])[:3]
        entities["payment_ids"] = entities.get("payment_ids", [])[:5]

        customer = output.get("customer_context", {})
        customer["related_order_ids"] = customer.get(
            "related_order_ids",
            [],
        )[:5]

        product = output.get("product_context", {})

        product["product_ids"] = product.get(
            "product_ids",
            [],
        )[:5]

        product["category_names"] = product.get(
            "category_names",
            [],
        )[:5]

        root = output.get("root_cause_analysis", {})

        root["ranked_causes"] = root.get(
            "ranked_causes",
            [],
        )[:3]

        root["responsible_parties"] = root.get(
            "responsible_parties",
            [],
        )[:3]

        output["resolution_actions"] = output.get(
            "resolution_actions",
            [],
        )[:5]

    def _build_evidence(self, output, order_id):

        evidence = [f"order:{order_id}"]

        entities = output.get("affected_entities", {})

        for item in entities.get("item_ids", []):
            evidence.append(f"item:{item}")

        for payment in entities.get("payment_ids", []):
            evidence.append(f"payment:{payment}")

        causes = output.get("root_cause_analysis", {})
        responsible_parties = causes.get("responsible_parties", [])
        for party in responsible_parties:
            if party.get("party_type") == "seller":
                evidence.append(f"seller:{party.get('party_id')}")

        causes = output.get(
            "root_cause_analysis",
            {},
        ).get(
            "ranked_causes",
            [],
        )

        for cause in causes:
            evidence.append(
                f"policy:{cause['cause_code']}"
            )

        output["evidence_ids"] = list(
            dict.fromkeys(evidence)
        )[:20]

    def _normalize_confidence(self, output):

        assessment = output.get(
            "case_assessment",
            {},
        )

        confidence = assessment.get(
            "confidence",
            0.5,
        )

        assessment["confidence"] = max(
            0.0,
            min(
                1.0,
                round(float(confidence), 2),
            ),
        )

    def _normalize_financial(self, output):

        refund = output.get(
            "financial_resolution",
            {},
        ).get(
            "recommended_refund_brl",
            0.0,
        )

        if refund is None:
            refund = 0.0

        output["financial_resolution"][
            "recommended_refund_brl"
        ] = round(float(refund), 2)