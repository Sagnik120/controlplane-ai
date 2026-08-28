import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.orchestrator.pipeline import PipelineOrchestrator
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.checkers.base import CheckerResult
from src.adapters.base_adapter import BaseLLMAdapter

class MockAdapter(BaseLLMAdapter):
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        return "Mock response"
        
    def generate_stream(self, prompt: str, temperature: float = 1.0):
        yield "Mock response"

class MockRiskEngine(RiskEngine):
    def __init__(self):
        super().__init__()
        self.mock_results = []
        
    def evaluate_response(self, response_text: str, **kwargs):
        from src.engine.risk_engine import FinalRiskReport
        return FinalRiskReport(
            overall_risk_score=0.0,
            is_blocked=False,
            checker_results=self.mock_results,
            overlap_detected=False
        )

def print_header(title):
    print("\n" + "="*80)
    print(f"🔬 {title}")
    print("="*80)

def main():
    print_header("Deep Real-World Edge Cases for Session Context (SPEC 06)")
    
    adapter = MockAdapter()
    risk_engine = MockRiskEngine()
    policy_engine = ControlPolicy()
    logger = AuditLogger("data/test_session_edge_cases_log.jsonl")
    
    orchestrator = PipelineOrchestrator(adapter, risk_engine, policy_engine, logger)
    
    policy = UseCasePolicy(
        name="edge_case_policy",
        session_drift_window_size=3,
        session_drift_threshold=0.55,
        session_require_monotonic_trend=True,
        session_cumulative_pii_threshold=3,
        session_escalation_action="HUMAN"
    )

    passed = 0
    total = 0

    # -------------------------------------------------------------------------
    # Scenario 1: Harmless Topic Change (Spike, not monotonic)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 1: Harmless Sudden Topic Change (False Positive Mitigation)")
    session_id_1 = "session_topic_change"
    
    turns = [
        "How do I configure my router?", # Turn 1: base
        "How do I set up port forwarding?", # Turn 2: similar
        "By the way, what's a good recipe for chocolate cake?", # Turn 3: Massive drift spike
        "How much flour do I need for the cake?" # Turn 4: Continues on new topic
    ]
    
    escalated = False
    for i, prompt in enumerate(turns):
        risk_engine.mock_results = []
        result = orchestrator.process_request(prompt, policy, session_id=session_id_1)
        if result["control_decision"]["action"] == "HUMAN":
            escalated = True
            
    if not escalated:
        print("  ✅ PASS: System correctly ignored the non-monotonic topic change.")
        passed += 1
    else:
        print("  ❌ FAIL: System falsely escalated a harmless topic change.")

    # -------------------------------------------------------------------------
    # Scenario 2: Re-identifying Fragments Distributed Across Many Turns
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 2: Long-Term Distributed PII Accumulation")
    session_id_2 = "session_long_term_pii"
    
    # 10 turns. Leaks on turns 1, 6, and 10.
    events = [
        [{"entity_type": "PERSON", "text": "John"}], # Turn 1
        [], [], [], [], # Turns 2-5: clean
        [{"entity_type": "LOCATION", "text": "London"}], # Turn 6
        [], [], [], # Turns 7-9: clean
        [{"entity_type": "ORGANIZATION", "text": "ACME"}] # Turn 10: TRIGGER
    ]
    
    escalated_turn = -1
    for i, entities in enumerate(events):
        if entities:
            risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=entities)]
        else:
            risk_engine.mock_results = []
            
        # Dummy prompt to avoid drift triggering it
        result = orchestrator.process_request(f"Normal conversation {i}", policy, session_id=session_id_2)
        if result["control_decision"]["action"] == "HUMAN":
            escalated_turn = i + 1
            break
            
    if escalated_turn == 10:
        print("  ✅ PASS: Retained state for 10 turns and escalated exactly on the 3rd distinct entity.")
        passed += 1
    else:
        print(f"  ❌ FAIL: Escalated on turn {escalated_turn} instead of turn 10.")

    # -------------------------------------------------------------------------
    # Scenario 3: Redundant PII (Self-Compounding Mitigation)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 3: Repeated Same-Type PII (False Positive Mitigation)")
    session_id_3 = "session_redundant_pii"
    
    # User just keeps naming different people and locations, but no 3rd type.
    events = [
        [{"entity_type": "PERSON", "text": "John"}],
        [{"entity_type": "PERSON", "text": "Mike"}],
        [{"entity_type": "PERSON", "text": "Sarah"}],
        [{"entity_type": "LOCATION", "text": "London"}],
        [{"entity_type": "LOCATION", "text": "Paris"}],
        [{"entity_type": "PERSON", "text": "David"}]
    ]
    
    escalated = False
    for i, entities in enumerate(events):
        risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=entities)]
        result = orchestrator.process_request(f"Normal conversation {i}", policy, session_id=session_id_3)
        if result["control_decision"]["action"] == "HUMAN":
            escalated = True
            break
            
    if not escalated:
        state = orchestrator.session_store.get_or_create(session_id_3)
        cpe = state.cumulative_pii_exposure_score
        if cpe == 2.0:
            print(f"  ✅ PASS: System correctly grouped distinct types. Final CPE Score: {cpe}.")
            passed += 1
        else:
            print(f"  ❌ FAIL: Expected CPE 2.0, got {cpe}.")
    else:
        print("  ❌ FAIL: System falsely escalated due to redundant PII types.")

    # -------------------------------------------------------------------------
    # Scenario 4: Session Isolation (Concurrency Safety)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 4: Session Isolation / Concurrency Safety")
    
    # Session A gets 2 fragments. Session B gets 2 fragments. Neither should trigger.
    risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=[{"entity_type": "PERSON", "text": "John"}])]
    orchestrator.process_request("A1", policy, session_id="A")
    
    risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=[{"entity_type": "LOCATION", "text": "Paris"}])]
    orchestrator.process_request("B1", policy, session_id="B")
    
    risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=[{"entity_type": "ORGANIZATION", "text": "ACME"}])]
    result_a = orchestrator.process_request("A2", policy, session_id="A") # A now has PERSON + ORG (2)
    
    risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=[{"entity_type": "EMAIL", "text": "test@test.com"}])]
    result_b = orchestrator.process_request("B2", policy, session_id="B") # B now has LOCATION + EMAIL (2)
    
    if result_a["control_decision"]["action"] != "HUMAN" and result_b["control_decision"]["action"] != "HUMAN":
        cpe_a = orchestrator.session_store.get_or_create("A").cumulative_pii_exposure_score
        cpe_b = orchestrator.session_store.get_or_create("B").cumulative_pii_exposure_score
        if cpe_a == 2.0 and cpe_b == 2.0:
            print("  ✅ PASS: Sessions remained completely isolated.")
            passed += 1
        else:
            print(f"  ❌ FAIL: Isolation breached. CPE A={cpe_a}, CPE B={cpe_b}")
    else:
        print("  ❌ FAIL: Isolation breached, falsely triggered escalation.")
        
    print_header(f"Edge Case Summary: {passed}/{total} Passed")

if __name__ == "__main__":
    main()
