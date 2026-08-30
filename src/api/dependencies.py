import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from src.orchestrator.pipeline import PipelineOrchestrator
from src.adapters.mock_adapter import MockAdapter
from src.adapters.gemini_adapter import GeminiAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.audit.audit_logger import AuditLogger
from src.policy.schemas import UseCasePolicy

# Automatically use GeminiAdapter if API key is set, otherwise fall back to MockAdapter
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    print("🔌 [ControlPlane-AI] Active LLM Adapter: Google Gemini (gemini-3.6-flash)")
    adapter = GeminiAdapter(model_name="gemini-3.6-flash")
else:
    print("⚠️ [ControlPlane-AI] Warning: GEMINI_API_KEY not found. Using MockAdapter.")
    adapter = MockAdapter()

risk_engine = RiskEngine()
control_policy = ControlPolicy()
audit_logger = AuditLogger()

orchestrator = PipelineOrchestrator(adapter, risk_engine, control_policy, audit_logger)

# Define preset policies for the demo
POLICIES = {
    "standard": UseCasePolicy(
        name="Standard Enterprise Chatbot",
        description="General enterprise policy with balanced calibrated conformal risk bounds.",
        max_overall_risk=0.8,
        block_on_overlap=True
    ),
    "medical": UseCasePolicy(
        name="Medical Clinical Assistant",
        description="Strict zero-tolerance for PII exposure. Automatically redacts and anonymizes sensitive data.",
        max_overall_risk=0.85,
        checker_thresholds={"pii": 0.0},
        block_on_overlap=True,
        redact_pii=True
    ),
    "lenient": UseCasePolicy(
        name="Creative Studio Copilot",
        description="High risk tolerance designed for creative writing, brainstorming, and copy generation.",
        max_overall_risk=1.0,
        checker_thresholds={"safety": 0.95},
        block_on_overlap=False
    )
}

def get_orchestrator() -> PipelineOrchestrator:
    return orchestrator

def get_policy(policy_id: str) -> UseCasePolicy:
    return POLICIES.get(policy_id, POLICIES["standard"])
