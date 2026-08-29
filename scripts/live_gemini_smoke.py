import asyncio
import os
import sys

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.gemini_adapter import GeminiAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.orchestrator.pipeline import PipelineOrchestrator
from dotenv import load_dotenv

load_dotenv()

async def main():
    print("==================================================")
    print("🚀 ControlPlane-AI: Live Gemini Smoke Test")
    print("==================================================\n")
    
    # 1. Ensure API key is set
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ ERROR: GEMINI_API_KEY environment variable is not set.")
        print("Please set it before running this script.")
        return
        
    print("[1] Initializing Pipeline Components...")
    
    try:
        # 2. Setup the existing components
        adapter = GeminiAdapter(model_name="gemini-3.6-flash")
        risk_engine = RiskEngine()
        control_policy = ControlPolicy()
        
        # Use stdout for audit logger to avoid writing junk log files, or just use a dummy one
        audit_logger = AuditLogger(log_file="smoke_audit.jsonl")
        
        # 3. Create the Orchestrator
        pipeline = PipelineOrchestrator(
            adapter=adapter,
            risk_engine=risk_engine,
            control_policy=control_policy,
            audit_logger=audit_logger
        )
        
        # 4. Define a simple, safe UseCasePolicy
        policy = UseCasePolicy(
            name="customer_support_chatbot",
            max_overall_risk=0.8
        )
        
        prompt = "Hello! Please reply with exactly 'System Check OK'."
        print(f"\n[2] Processing Request: '{prompt}'")
        
        # 5. Process Request (using the newly rewritten async method)
        result = await pipeline.process_request_async(prompt=prompt, policy=policy)
        
        print("\n[3] Results:")
        print("--------------------------------------------------")
        
        # Extract metadata
        decision = result.get("control_decision", {})
        action = decision.get("action", "UNKNOWN")
        reasoning = decision.get("reasoning", "")
        final_text = result.get("final_output", "")
        
        risk_report = result.get("risk_report", {})
        overall_score = risk_report.get("overall_risk_score", 0.0)
        
        print(f"Final Action   : {action}")
        print(f"Overall Risk   : {overall_score:.2f}")
        print(f"Rationale      : {reasoning}")
        print(f"Generated Text : {final_text}")
        
        if "latency_ms" in result:
            print(f"Total Latency  : {result['latency_ms']:.2f} ms")
            
        print("\nChecker Results:")
        for checker in risk_report.get("checker_results", []):
            name = checker.get("checker_name", "unknown")
            score = checker.get("risk_score", 0.0)
            expl = checker.get("explanation", "")
            print(f"  - {name:15} | Risk: {score:.2f} | {expl}")
            
        print("\n==================================================")
        
        has_errors = any(c.get("is_error", False) for c in risk_report.get("checker_results", []))
        
        if action == "ALLOW" and not has_errors:
            print("✅ SMOKE TEST PASSED SUCCESSFULLY.")
        elif has_errors or action == "BLOCK":
            print(f"❌ SMOKE TEST FAILED: Pipeline halted or checker experienced API/Model errors.")
            sys.exit(1)
        else:
            print(f"⚠️ SMOKE TEST FINISHED WITH NON-ALLOW ACTION: {action}")
            
    except Exception as e:
        print(f"\n❌ FATAL ERROR DURING SMOKE TEST: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
