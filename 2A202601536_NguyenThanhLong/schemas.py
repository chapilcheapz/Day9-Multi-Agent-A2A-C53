from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class CaseInput:
    case_id: str
    claimed_order_id: str
    investigation_scope: List[str]
    policies: Dict[str, Any]

@dataclass
class FinalCaseOutput:
    case_id: str
    case_assessment: Dict[str, Any]
    affected_entities: Dict[str, Any]
    customer_context: Dict[str, Any]
    product_context: Dict[str, Any]
    delivery_analysis: Dict[str, Any]
    payment_reconciliation: Dict[str, Any]
    root_cause_analysis: Dict[str, Any]
    evidence_ids: List[str]
    financial_resolution: Dict[str, Any]
    resolution_actions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_assessment": self.case_assessment,
            "affected_entities": self.affected_entities,
            "customer_context": self.customer_context,
            "product_context": self.product_context,
            "delivery_analysis": self.delivery_analysis,
            "payment_reconciliation": self.payment_reconciliation,
            "root_cause_analysis": self.root_cause_analysis,
            "evidence_ids": self.evidence_ids,
            "financial_resolution": self.financial_resolution,
            "resolution_actions": self.resolution_actions,
        }
