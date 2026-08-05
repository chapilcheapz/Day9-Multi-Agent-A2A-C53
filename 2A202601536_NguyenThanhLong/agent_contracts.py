from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class PlanOutput:
    investigation_plan: List[str]
    required_domain_agents: List[str]

@dataclass
class DomainInvestigationOutput:
    agent_name: str
    findings: Dict[str, Any]

@dataclass
class SynthesisOutput:
    summary: str
    key_facts: Dict[str, Any]
    conflict_detected: bool

@dataclass
class PolicyEvaluationOutput:
    primary_issue: str
    secondary_issues: List[str]
    ranked_causes: List[Dict[str, Any]]
    responsible_parties: List[Dict[str, Any]]
    confidence: float
