from src.orchestrator.pipeline import PipelineOrchestrator
from src.adapters.mock_adapter import MockAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.audit.audit_logger import AuditLogger
from src.policy.schemas import UseCasePolicy

# Global instances (Using MockAdapter to save API credits during demo)
adapter = MockAdapter()
risk_engine = RiskEngine()
control_policy = ControlPolicy()
audit_logger = AuditLogger()

orchestrator = PipelineOrchestrator(adapter, risk_engine, control_policy, audit_logger)

# Define preset policies for the demo
POLICIES = {
    "standard": UseCasePolicy(
        name="Standard Chatbot",
        description="General purpose AI chatbot.",
        max_overall_risk=0.8,
        block_on_overlap=True
    ),
    "medical": UseCasePolicy(
        name="Medical Assistant",
        description="Strict zero-tolerance for PII exposure. Redacts PII if found.",
        max_overall_risk=0.9,
        checker_thresholds={"pii": 0.0},
        block_on_overlap=True,
        redact_pii=True
    ),
    "lenient": UseCasePolicy(
        name="Lenient / Creative",
        description="Allows higher risk for creative writing.",
        max_overall_risk=1.0,
        checker_thresholds={"safety": 0.95}, # Allow somewhat edgy content
        block_on_overlap=False
    )
}

def get_orchestrator() -> PipelineOrchestrator:
    return orchestrator

def get_policy(policy_id: str) -> UseCasePolicy:
    return POLICIES.get(policy_id, POLICIES["standard"])
