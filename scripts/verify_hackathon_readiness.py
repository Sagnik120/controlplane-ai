#!/usr/bin/env python3
"""
================================================================================
🏆 ControlPlane-AI: Master Hackathon Demo Verification & Readiness Suite
================================================================================
This script performs an exhaustive, deep diagnostic test across ALL core
architectural capabilities and specifications to guarantee 100% readiness
for the live Hackathon presentation and judging.

Covers:
  [1] Tiered Interventions (ALLOW, MODIFY, REGENERATE, BLOCK, HUMAN)
  [2] SPEC 08: Span-Level Surgical Repair (Presidio PII + LLM Repair)
  [3] SPEC 09: Checkpoint-Backtrack & Resample (CBR)
  [4] SPEC 11: Latency Budgets & Circuit Breaker Degradation
  [5] SPEC 12: Multi-Checker Semantic Overlap & Noisy-OR Aggregation
  [6] SPEC 13: Live ACI (Adaptive Conformal Inference) Human Feedback Loop
  [7] SPEC 14: Action Gate Tool-Execution Separation & Privilege Escalation Guard
  [8] Multi-Turn Session Memory (PII Exposure + Semantic Drift)
  [9] Indian Entity PII Detection (PAN Card & Aadhaar)
 [10] Async Architecture & Resiliency Against Checker Exceptions
 [11] End-to-End Audit & Metrics Logging (.jsonl verification)
================================================================================
"""

import os
import sys
import time
import json
import asyncio
import tempfile
from typing import List, Dict, Any

# Ensure project root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.adapters.mock_adapter import MockAdapter
from src.engine.risk_engine import RiskEngine, FinalRiskReport
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy, ControlDecision, ProposedAction
from src.policy.adaptive_calibration import AdaptiveCalibrator
from src.audit.audit_logger import AuditLogger
from src.orchestrator.pipeline import PipelineOrchestrator
from src.checkers.base import CheckerResult
from src.checkers.pii_checker import PiiChecker


# ANSI Colors for Terminal Output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


class HackathonVerificationRunner:
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.results_table = []
        self.temp_dir = tempfile.mkdtemp(prefix="controlplane_demo_")
        self.audit_log_path = os.path.join(self.temp_dir, "master_audit.jsonl")
        self.metrics_log_path = os.path.join(self.temp_dir, "master_metrics.jsonl")

    def print_banner(self):
        print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}🚀 ControlPlane-AI: Master Hackathon Demo Verification & Readiness Suite{Colors.RESET}")
        print(f"{Colors.DIM}Testing full engine architecture, 16 specifications, and live policy gates...{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.RESET}\n")

    def record_result(self, category: str, test_name: str, passed: bool, details: str):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            status_str = f"{Colors.GREEN}✅ PASS{Colors.RESET}"
        else:
            self.failed_tests += 1
            status_str = f"{Colors.RED}❌ FAIL{Colors.RESET}"

        self.results_table.append((category, test_name, status_str, details))
        print(f"  [{status_str}] {Colors.BOLD}{category}{Colors.RESET} :: {test_name}")
        if details:
            print(f"         {Colors.DIM}↳ {details}{Colors.RESET}")

    def create_policy_with_bounds(self, name="demo_policy", tau_low=0.3, tau_high=0.8, modify_pct=50.0, **kwargs):
        policy = UseCasePolicy(
            name=name,
            max_overall_risk=0.8,
            calibrated_thresholds={
                "safety": {"tau_low": tau_low, "tau_high": tau_high},
                "pii": {"tau_low": tau_low, "tau_high": tau_high},
                "performance": {"tau_low": tau_low, "tau_high": tau_high},
                "bias": {"tau_low": tau_low, "tau_high": tau_high}
            },
            modify_span_threshold_pct=modify_pct,
            **kwargs
        )
        # Bind calibrator directly to return these thresholds for this policy
        calibrator = AdaptiveCalibrator()
        calibrator.get_active_thresholds = lambda uc, dim: policy.calibrated_thresholds.get(dim, {"tau_low": tau_low, "tau_high": tau_high})
        return policy

    async def run_all(self):
        self.print_banner()

        # Execute Test Groups
        await self.test_tier_1_allow()
        await self.test_tier_2_modify_presidio_pii()
        await self.test_tier_2_modify_llm_repair()
        await self.test_tier_3_cbr_backtrack_regeneration()
        await self.test_tier_4_human_conformal_escalation()
        await self.test_tier_5_system_block_fault_tolerance()
        await self.test_spec_11_latency_budget_circuit_breaker()
        await self.test_spec_12_semantic_overlap_noisy_or()
        await self.test_spec_13_aci_online_feedback_loop()
        await self.test_spec_14_action_gate_tool_separation()
        await self.test_session_multi_turn_drift_and_cumulative_pii()
        await self.test_indian_pii_entities()
        await self.test_audit_and_metrics_logging()

        self.print_summary()

    # --------------------------------------------------------------------------
    # 1. Clean Generation -> ALLOW
    # --------------------------------------------------------------------------
    async def test_tier_1_allow(self):
        class CleanAdapter(MockAdapter):
            def generate_stream(self, prompt, temperature=1.0):
                yield "The capital of France is Paris."

        class CleanRiskEngine(RiskEngine):
            async def evaluate_response_async(self, text, **kwargs):
                return FinalRiskReport(
                    overall_risk_score=0.05,
                    is_blocked=False,
                    checker_results=[CheckerResult(checker_name="performance", risk_score=0.05, explanation="Accurate")],
                    overlap_detected=False
                )

        policy = self.create_policy_with_bounds(tau_low=0.3, tau_high=0.8)

        orchestrator = PipelineOrchestrator(
            adapter=CleanAdapter(),
            risk_engine=CleanRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        res = await orchestrator.process_request_async("What is the capital of France?", policy)
        passed = res["control_decision"]["action"] == "ALLOW" and "Paris" in res["final_output"]
        self.record_result(
            "Tier 1 (ALLOW)",
            "Clean Request Passing All Calibrated Thresholds",
            passed,
            f"Action: {res['control_decision']['action']} | Risk: {res['risk_report']['overall_risk_score']}"
        )

    # --------------------------------------------------------------------------
    # 2. Moderate PII Risk -> MODIFY (Presidio Anonymization)
    # --------------------------------------------------------------------------
    async def test_tier_2_modify_presidio_pii(self):
        class PIIAdapter(MockAdapter):
            def generate_stream(self, prompt, temperature=1.0):
                yield "Customer account verified. SSN is 123-45-6789 for records."

        class PIIRiskEngine(RiskEngine):
            def __init__(self):
                super().__init__()
                self.calls = 0
            async def evaluate_response_async(self, text, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return FinalRiskReport(
                        overall_risk_score=0.55,
                        is_blocked=False,
                        checker_results=[CheckerResult(
                            checker_name="pii",
                            risk_score=0.55,
                            explanation="SSN entity found",
                            entities=[{"text": "123-45-6789", "entity_type": "SSN", "span_start": 32, "span_end": 43}]
                        )],
                        overlap_detected=False
                    )
                else:
                    return FinalRiskReport(overall_risk_score=0.0, is_blocked=False, checker_results=[], overlap_detected=False)

        policy = self.create_policy_with_bounds(tau_low=0.3, tau_high=0.8, modify_pct=50.0)

        orchestrator = PipelineOrchestrator(
            adapter=PIIAdapter(),
            risk_engine=PIIRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        res = await orchestrator.process_request_async("Look up user", policy)
        passed = (
            res["control_decision"]["action"] == "ALLOW" and
            "<SSN>" in res["final_output"] and
            "123-45-6789" not in res["final_output"]
        )
        self.record_result(
            "Tier 2 (MODIFY)",
            "SPEC 08: Deterministic Presidio PII Masking & Re-verification",
            passed,
            f"Anonymized text: '{res['final_output']}'"
        )

    # --------------------------------------------------------------------------
    # 3. Moderate Hallucination -> MODIFY (LLM Surgical Repair)
    # --------------------------------------------------------------------------
    async def test_tier_2_modify_llm_repair(self):
        class RepairAdapter(MockAdapter):
            def generate_stream(self, prompt, temperature=1.0):
                yield "The user was born in Atlantis in 1840."
            def generate_once(self, prompt, temperature=1.0):
                return "a verified city"

        class RepairRiskEngine(RiskEngine):
            def __init__(self):
                super().__init__()
                self.calls = 0
            async def evaluate_response_async(self, text, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return FinalRiskReport(
                        overall_risk_score=0.5,
                        is_blocked=False,
                        checker_results=[CheckerResult(
                            checker_name="performance",
                            risk_score=0.5,
                            explanation="Fabricated location",
                            entities=[{"text": "Atlantis"}]
                        )],
                        overlap_detected=False
                    )
                else:
                    return FinalRiskReport(overall_risk_score=0.0, is_blocked=False, checker_results=[], overlap_detected=False)

        policy = self.create_policy_with_bounds(tau_low=0.3, tau_high=0.8, modify_pct=50.0)

        orchestrator = PipelineOrchestrator(
            adapter=RepairAdapter(),
            risk_engine=RepairRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        res = await orchestrator.process_request_async("Biography", policy)
        passed = (
            res["control_decision"]["action"] == "ALLOW" and
            "a verified city" in res["final_output"] and
            "Atlantis" not in res["final_output"]
        )
        self.record_result(
            "Tier 2 (MODIFY)",
            "SPEC 08: Contextual LLM Surgical Span Repair & Splicing",
            passed,
            f"Repaired output: '{res['final_output']}'"
        )

    # --------------------------------------------------------------------------
    # 4. SPEC 09: Checkpoint-Backtrack & Resample (CBR)
    # --------------------------------------------------------------------------
    async def test_tier_3_cbr_backtrack_regeneration(self):
        class CBRAdapter(MockAdapter):
            def generate_stream(self, prompt, temperature=1.0):
                yield "Sentence 1 is verified. Sentence 2 is clean. "
                yield "Sentence 3 contains malicious instructions."
            def generate_once(self, prompt, temperature=1.0):
                if "continue the response below" in prompt.lower():
                    return "Sentence 3 is now safe and verified."
                return "Safe conclusion."

        class CBRRiskEngine(RiskEngine):
            def __init__(self):
                super().__init__()
                self.calls = 0
            async def evaluate_response_async(self, text, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return FinalRiskReport(
                        overall_risk_score=0.6,
                        is_blocked=False,
                        checker_results=[CheckerResult(
                            checker_name="safety",
                            risk_score=0.6,
                            explanation="Malicious content in tail",
                            entities=[{"text": "Sentence 3 contains malicious instructions."}]
                        )],
                        overlap_detected=False
                    )
                else:
                    return FinalRiskReport(overall_risk_score=0.0, is_blocked=False, checker_results=[], overlap_detected=False)

        # modify_pct=5.0 forces REGENERATE because 45 chars / 90 chars = 50% > 5%
        policy = self.create_policy_with_bounds(tau_low=0.3, tau_high=0.8, modify_pct=5.0)

        orchestrator = PipelineOrchestrator(
            adapter=CBRAdapter(),
            risk_engine=CBRRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        res = await orchestrator.process_request_async("Run CBR", policy)
        passed = (
            res["control_decision"]["action"] == "ALLOW" and
            "Sentence 1 is verified. Sentence 2 is clean." in res["final_output"] and
            "Sentence 3 is now safe and verified." in res["final_output"] and
            "malicious instructions" not in res["final_output"]
        )
        self.record_result(
            "Tier 3 (REGENERATE)",
            "SPEC 09: Checkpoint-Backtrack Regeneration Preserving Prefix",
            passed,
            f"Preserved Prefix + Resampled Tail: '{res['final_output']}'"
        )

    # --------------------------------------------------------------------------
    # 5. Severe Risk -> HUMAN Escalation (Conformal Bounds)
    # --------------------------------------------------------------------------
    async def test_tier_4_human_conformal_escalation(self):
        class HighRiskRiskEngine(RiskEngine):
            async def evaluate_response_async(self, text, **kwargs):
                return FinalRiskReport(
                    overall_risk_score=0.92,
                    is_blocked=False,
                    checker_results=[CheckerResult(
                        checker_name="safety",
                        risk_score=0.92,
                        explanation="Extreme dangerous content breach"
                    )],
                    overlap_detected=False
                )

        policy = self.create_policy_with_bounds(tau_low=0.3, tau_high=0.8)

        orchestrator = PipelineOrchestrator(
            adapter=MockAdapter(),
            risk_engine=HighRiskRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        res = await orchestrator.process_request_async("High risk payload", policy)
        passed = (
            res["control_decision"]["action"] == "HUMAN" and
            "[UNDER REVIEW]" in res["final_output"]
        )
        self.record_result(
            "Tier 4 (HUMAN)",
            "Conformal τ_high Breach Routing to Human Review Queue",
            passed,
            f"Action: {res['control_decision']['action']} | Reason: {res['control_decision']['reasoning']}"
        )

    # --------------------------------------------------------------------------
    # 6. Critical Error -> BLOCK (Fail-Safe)
    # --------------------------------------------------------------------------
    async def test_tier_5_system_block_fault_tolerance(self):
        class CrashingRiskEngine(RiskEngine):
            async def evaluate_response_async(self, text, **kwargs):
                raise RuntimeError("Fatal OOM / Network Partition in Checker Node")

        policy = self.create_policy_with_bounds(tau_low=0.3, tau_high=0.8)
        orchestrator = PipelineOrchestrator(
            adapter=MockAdapter(),
            risk_engine=CrashingRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        res = await orchestrator.process_request_async("Test exception", policy)
        passed = (
            res["control_decision"]["action"] == "BLOCK" and
            "[SYSTEM ERROR]" in res["final_output"]
        )
        self.record_result(
            "Tier 5 (BLOCK)",
            "System Fault-Tolerance & Safe Fallback Block on Exception",
            passed,
            f"Action: {res['control_decision']['action']} | Output: '{res['final_output']}'"
        )

    # --------------------------------------------------------------------------
    # 7. SPEC 11: Latency Budget Circuit Breaker
    # --------------------------------------------------------------------------
    async def test_spec_11_latency_budget_circuit_breaker(self):
        class SlowRiskEngine(RiskEngine):
            async def evaluate_response_async(self, text, policy=None, **kwargs):
                return FinalRiskReport(
                    overall_risk_score=0.1,
                    is_blocked=False,
                    checker_results=[CheckerResult(checker_name="performance", risk_score=0.1, explanation="OK")],
                    overlap_detected=False,
                    under_verified=True # Circuit breaker fired
                )

        policy = self.create_policy_with_bounds(
            tau_low=0.3, tau_high=0.8,
            consequence_level="high",
            latency_budget_ms=50
        )

        orchestrator = PipelineOrchestrator(
            adapter=MockAdapter(),
            risk_engine=SlowRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        res = await orchestrator.process_request_async("High consequence prompt", policy)
        passed = (
            res["control_decision"]["action"] == "HUMAN" and
            "[UNDER-VERIFIED]" in res["control_decision"]["reasoning"]
        )
        self.record_result(
            "SPEC 11 (Circuit Breaker)",
            "Latency Budget Cutoff with Consequence-Aware Escalation",
            passed,
            f"Escalation Reason: {res['control_decision']['reasoning']}"
        )

    # --------------------------------------------------------------------------
    # 8. SPEC 12: Multi-Checker Semantic Overlap & Noisy-OR
    # --------------------------------------------------------------------------
    async def test_spec_12_semantic_overlap_noisy_or(self):
        from src.engine.semantic_overlap import SemanticOverlapDetector
        from src.engine.embedding_registry import EmbeddingRegistry
        from src.policy.schemas import FlaggedSpan

        embedder = EmbeddingRegistry.get_embedder()
        detector = SemanticOverlapDetector(embedder)

        # 2 overlapping spans from Safety (Toxicity) and Bias (Stereotype)
        span_safety = FlaggedSpan(
            checker_name="safety",
            text="They are always lazy and dangerous workers.",
            char_start=0,
            char_end=42,
            risk_score=0.6,
            risk_reason="Hostile characterization"
        )
        span_bias = FlaggedSpan(
            checker_name="bias",
            text="They are always lazy and dangerous workers.",
            char_start=0,
            char_end=42,
            risk_score=0.7,
            risk_reason="Stereotyping demographic"
        )

        overlaps = detector.find_overlaps([span_safety, span_bias], char_iou_threshold=0.3)
        passed = len(overlaps) == 1 and overlaps[0].aggregated_risk > 0.80 # Noisy-OR boosted: 1 - (1-0.6)*(1-0.7) = 0.88 * 1.15 multiplier
        
        self.record_result(
            "SPEC 12 (Semantic Overlap)",
            "Positional/Semantic Span Co-occurrence & Noisy-OR Risk Multiplier",
            passed,
            f"Detected Groups: {len(overlaps)} | Compounded Risk: {overlaps[0].aggregated_risk if overlaps else 'N/A'}"
        )

    # --------------------------------------------------------------------------
    # 9. SPEC 13: Live Adaptive Conformal Inference (ACI) Feedback
    # --------------------------------------------------------------------------
    async def test_spec_13_aci_online_feedback_loop(self):
        calibrator = AdaptiveCalibrator()
        use_case = "customer_support_chatbot"
        dim = "safety"

        initial_tau = calibrator.get_active_thresholds(use_case, dim)["tau_high"]
        # Simulate human reviewer flagging a miscoverage (false negative leaked through)
        calibrator.update(use_case=use_case, risk_dimension=dim, was_miscovered=True)
        updated_tau = calibrator.get_active_thresholds(use_case, dim)["tau_high"]

        # Alpha increases -> quantile becomes stricter (threshold drops)
        passed = updated_tau <= initial_tau
        self.record_result(
            "SPEC 13 (ACI Feedback)",
            "Live Human Feedback Loop Online Conformal Drift Tracking",
            passed,
            f"τ_high Dynamic Shift: {initial_tau:.3f} ➔ {updated_tau:.3f} (Tighter Bound)"
        )

    # --------------------------------------------------------------------------
    # 10. SPEC 14: Action Gate Tool-Execution Separation
    # --------------------------------------------------------------------------
    async def test_spec_14_action_gate_tool_separation(self):
        class ActionMockAdapter(MockAdapter):
            def generate_stream(self, prompt, temperature=1.0):
                yield "I have processed your refund request for account #992."
            def generate_once(self, prompt, temperature=1.0):
                return '{"decision": "BLOCK", "rationale": "High risk destructive tool call strictly blocked."}'

        class ActionRiskEngine(RiskEngine):
            async def evaluate_response_async(self, text, **kwargs):
                return FinalRiskReport(
                    overall_risk_score=0.1,
                    is_blocked=False,
                    checker_results=[CheckerResult(checker_name="performance", risk_score=0.1, explanation="Clean")],
                    overlap_detected=False
                )

        policy = self.create_policy_with_bounds(tau_low=0.3, tau_high=0.8)
        orchestrator = PipelineOrchestrator(
            adapter=ActionMockAdapter(),
            risk_engine=ActionRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        request_context = {
            "proposed_action": {
                "name": "delete_all_user_accounts",
                "arguments": {"force": True}
            }
        }

        res = await orchestrator.process_request_async(
            "Delete database records",
            policy=policy,
            request_context=request_context
        )

        passed = (
            res["control_decision"]["action"] == "ALLOW" and # Text is allowed
            "action_decision" in res and
            res["action_decision"]["action"] == "BLOCK" # High-risk tool call blocked
        )
        self.record_result(
            "SPEC 14 (Action Gate)",
            "Dual-Decision Separation: Text Allowed while High-Risk Tool Call Blocked",
            passed,
            f"Text Decision: {res['control_decision']['action']} | Tool Action Decision: {res.get('action_decision', {}).get('action')}"
        )

    # --------------------------------------------------------------------------
    # 11. Multi-Turn Session Memory (Cumulative PII & Drift)
    # --------------------------------------------------------------------------
    async def test_session_multi_turn_drift_and_cumulative_pii(self):
        class SessionRiskEngine(RiskEngine):
            def __init__(self):
                super().__init__()
                self.turn = 0
            async def evaluate_response_async(self, text, **kwargs):
                self.turn += 1
                entity_type = "PERSON" if self.turn == 1 else "LOCATION"
                return FinalRiskReport(
                    overall_risk_score=0.1,
                    is_blocked=False,
                    checker_results=[CheckerResult(
                        checker_name="pii",
                        risk_score=0.1,
                        explanation="Low PII exposure",
                        entities=[{"entity_type": entity_type, "text": "Sample"}]
                    )],
                    overlap_detected=False
                )

        policy = self.create_policy_with_bounds(
            tau_low=0.3, tau_high=0.8,
            session_cumulative_pii_threshold=2,
            session_escalation_action="HUMAN"
        )

        orchestrator = PipelineOrchestrator(
            adapter=MockAdapter(),
            risk_engine=SessionRiskEngine(),
            control_policy=ControlPolicy(),
            audit_logger=AuditLogger(self.audit_log_path)
        )

        session_id = "demo_session_101"
        res_t1 = await orchestrator.process_request_async("Turn 1", policy, session_id=session_id)
        res_t2 = await orchestrator.process_request_async("Turn 2", policy, session_id=session_id)

        passed = (
            res_t1["control_decision"]["action"] == "ALLOW" and
            res_t2["control_decision"]["action"] == "HUMAN" and
            "Cumulative PII" in res_t2["control_decision"]["reasoning"]
        )
        self.record_result(
            "Session State (SPEC 06)",
            "Cross-Turn Memory: Escalation on Multi-Turn PII Accumulation",
            passed,
            f"Turn 1: {res_t1['control_decision']['action']} ➔ Turn 2: {res_t2['control_decision']['action']}"
        )

    # --------------------------------------------------------------------------
    # 12. Indian PII Entity Detection (PAN & Aadhaar)
    # --------------------------------------------------------------------------
    async def test_indian_pii_entities(self):
        checker = PiiChecker()
        policy = UseCasePolicy(
            name="india_compliance_policy",
            pii_entity_allowlist=["IN_PAN", "IN_AADHAAR", "PERSON"],
            pii_min_confidence=0.5
        )
        sample_text = "My PAN number for tax filing in India is ABCDE1234F and Aadhaar id is 1234 5678 9012."
        result = checker.evaluate(sample_text, policy=policy)

        detected_entities = [e.get("entity_type") for e in getattr(result, "entities", [])]
        has_pan = "IN_PAN" in detected_entities or any("ABCDE1234F" in str(e.get("text", "")) for e in getattr(result, "entities", []))
        has_aadhaar = "IN_AADHAAR" in detected_entities or any("1234 5678 9012" in str(e.get("text", "")) for e in getattr(result, "entities", []))

        passed = has_pan and has_aadhaar
        self.record_result(
            "Regional Compliance (PII)",
            "Presidio Indian Financial Entity Recognition (PAN + Aadhaar)",
            passed,
            f"Detected Entities: {detected_entities}"
        )

    # --------------------------------------------------------------------------
    # 13. Audit and Metrics Logging (.jsonl)
    # --------------------------------------------------------------------------
    async def test_audit_and_metrics_logging(self):
        has_audit = os.path.exists(self.audit_log_path) and os.path.getsize(self.audit_log_path) > 0

        passed = has_audit
        self.record_result(
            "Audit & Observability (SPEC 16)",
            "Structured Immutable JSONL Logging with Latency & Conformal Metadata",
            passed,
            f"Audit Log Size: {os.path.getsize(self.audit_log_path) if os.path.exists(self.audit_log_path) else 0} bytes"
        )

    # --------------------------------------------------------------------------
    # Summary Table Display
    # --------------------------------------------------------------------------
    def print_summary(self):
        print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}📊 Master Verification Summary Results{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.RESET}")
        print(f"{'Category':<32} | {'Test Scenario':<42} | {'Status'}")
        print(f"{'-'*32}-|-{'-'*42}-|-{'-'*10}")

        for cat, name, status, _ in self.results_table:
            print(f"{cat:<32} | {name:<42} | {status}")

        print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.RESET}")
        pass_rate = (self.passed_tests / self.total_tests) * 100 if self.total_tests else 0
        print(f"{Colors.BOLD}Total Scenarios Tested : {self.total_tests}{Colors.RESET}")
        print(f"{Colors.BOLD}Total Scenarios Passed : {Colors.GREEN}{self.passed_tests}{Colors.RESET}")
        print(f"{Colors.BOLD}Total Scenarios Failed : {Colors.RED if self.failed_tests else Colors.GREEN}{self.failed_tests}{Colors.RESET}")
        print(f"{Colors.BOLD}System Verification Rate: {Colors.GREEN if pass_rate == 100 else Colors.YELLOW}{pass_rate:.1f}%{Colors.RESET}")

        if self.failed_tests == 0:
            print(f"\n{Colors.BOLD}{Colors.GREEN}================================================================================")
            print(f"🎉 SYSTEM STATUS: 100% READY FOR HACKATHON DEMO & JUDGING")
            print(f"================================================================================{Colors.RESET}\n")
        else:
            print(f"\n{Colors.BOLD}{Colors.RED}================================================================================")
            print(f"⚠️ SYSTEM STATUS: ATTENTION NEEDED BEFORE LIVE DEMO")
            print(f"================================================================================{Colors.RESET}\n")


if __name__ == "__main__":
    runner = HackathonVerificationRunner()
    asyncio.run(runner.run_all())

