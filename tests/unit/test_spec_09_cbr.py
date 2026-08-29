import sys
import os

# Add root to python path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.regenerate.checkpoint_backtrack import CheckpointManager, RegenerationEngine
from src.adapters.base_adapter import BaseLLMAdapter
from src.policy.schemas import UseCasePolicy
from src.checkers.performance_checker import PerformanceChecker

class MockAdapter(BaseLLMAdapter):
    def generate_stream(self, prompt: str):
        yield "mock output"
        
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        prompt_lower = prompt.lower()
        if "generate 2-4 short, independent, checkable" in prompt_lower:
            return "Is Paris the capital of France?\nWhen was the Eiffel Tower built?"
        if "answer the following question" in prompt_lower:
            return "Yes, it is.\nIt was built in 1889."
        if "continue the response below" in prompt_lower:
            return " The Eiffel Tower, located in Paris, was built in 1889."
        return "mock text"

def test_checkpoint_manager():
    print("Running CheckpointManager Test...")
    cm = CheckpointManager()
    cp = cm.commit("turn_1", 10, 5, None, "This is good.")
    assert cp.char_offset == 10, "Checkpoint failed to save character offset"
    assert cm.backtrack("turn_1") == "This is good.", "Backtrack returned incorrect prompt state"
    print("✅ CheckpointManager passed!")

def test_regeneration_engine():
    print("Running RegenerationEngine Test...")
    adapter = MockAdapter()
    cm = CheckpointManager()
    cm.commit("turn_2", 15, 0, None, "Clean prefix.")
    engine = RegenerationEngine(adapter, cm)
    
    policy = UseCasePolicy(name="Test Policy")
    
    result = engine.regenerate(
        turn_id="turn_2",
        original_prompt="Tell me about Paris.",
        flagged_span="Paris is in Germany.",
        risk_reason="Hallucination detected.",
        use_case_policy=policy
    )
    
    assert "Eiffel Tower" in result, "Resampled text did not contain expected content from MockAdapter"
    print("✅ RegenerationEngine passed (Diagnose -> Verify -> Resample chain successful)!")

def test_performance_checker_tier0():
    print("Running PerformanceChecker Tier-0 Bypass Test...")
    try:
        checker = PerformanceChecker()
        policy = UseCasePolicy(name="Test Policy", tier0_uncertain_band_low=0.20)
        
        # Highly confident text (few words) -> should bypass
        confident_text = "This is short."
        adapter = MockAdapter()
        res1 = checker.evaluate(confident_text, prompt="hello", adapter=adapter, policy=policy)
        
        assert res1.tier == 0, f"Expected tier 0 but got {res1.tier}"
        assert res1.ran_selfcheck == False, "Expected ran_selfcheck to be False"
        print("✅ PerformanceChecker Tier-0 Bypass passed!")
    except (ImportError, OSError) as e:
        print(f"⚠️ Skipping PerformanceChecker test due to missing dependencies: {e}")

if __name__ == "__main__":
    print("======================================================")
    print(" Starting Diagnostics for SPEC 09 (CBR)               ")
    print("======================================================\n")
    try:
        test_checkpoint_manager()
        test_regeneration_engine()
        test_performance_checker_tier0()
        print("\n🎉 All SPEC 09 diagnostic tests completed successfully!")
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Error during testing: {e}")
