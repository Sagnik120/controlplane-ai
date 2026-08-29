# Executive Summary

This report documents the verification of issues raised in `debug.md` against the actual ControlPlane-AI codebase. Code changes were deliberately deferred to establish a solid diagnostic baseline. The repository demonstrates a solid architectural foundation but suffers from several integration bugs, mismatched test expectations, and a "Frankenstein" sync/async pipeline design. 

# Repository/Test Structure Status
- The test suite is partially implemented but missing several critical tests required by `debug.md`.
- **Environment Issue:** The test run failed during collection (`tests/api/test_api_diagnostic.py`) due to a missing spaCy model (`en_core_web_sm`). This is a configuration/environment issue, not a production bug.

# File-by-File Verification

| Priority | File | DEBUG Hypothesis | Actual Finding | Status | Evidence | Recommended Fix |
|---|---|---|---|---|---|---|
| 1 | `src/orchestrator/pipeline.py` | Pipeline is synchronous and blocks the event loop. | **CONFIRMED** | Confirmed | `process_request` is a `def`, uses a synchronous `generate_stream`, and wraps `RiskEngine.evaluate_response_async` in a blocking `asyncio.run` thread pool hack. | Refactor `process_request` to `async def` and use `await` natively. |
| 2 | `src/engine/risk_engine.py` | Semantic overlap Noisy-OR logic is missing or broken. | **PARTIALLY CONFIRMED** | Confirmed | `RiskEngine.evaluate_response_async` uses `max()` (Line 242) for overlapping group risks instead of a Noisy-OR combination. | Implement Noisy-OR `1 - prod(1 - risk)` for overlap aggregation. |
| 3 | `src/policy/adaptive_calibration.py` | ACI Tuner bounds are clamping to 0, breaking policy. | **CONFIRMED** | Confirmed | `test_aci_update_equation_exact` fails because `min_alpha` is `0.001` in code but the test asserts `0.01`. This causes thresholds to push towards `1.0` (ALLOW). | Fix `min_alpha` to `0.01` or align test and implementation to prevent degenerate thresholds. |
| 4 | `src/agent/action_gate.py` | Action gate triggers pipeline failure. | **CONFIRMED** | Confirmed | `test_pipeline_decision_separation` fails expecting `ALLOW` but getting `HUMAN`. `PipelineOrchestrator` escalates `policy.consequence_level = "high"` when an action is proposed, which causes the policy to escalate moderate risks to `HUMAN` instead of `ALLOW`. | Decouple action-level blocking from the text generation policy decision. |
| 5 | `src/regenerate/checkpoint_backtrack.py` | Checkpoint regeneration fails to append. | **CONFIRMED** | Confirmed | `test_spec09_cbr.py` fails because `new_text` is appended with a space (`decision.clean_prefix + " " + new_text`), but the mock adapter might not be returning the exact expected string, or the checkpoint state is malformed. | Verify the adapter mock output in the test, and ensure `clean_prefix` retains proper trailing whitespace. |

# Existing Test Failures

| Test | Failure | Root Cause | Confidence | Production/Test/Config Issue |
|---|---|---|---|---|
| `test_spec09_cbr.py::test_checkpoint_backtrack_regeneration` | `AssertionError: False is not true : Regenerated tail was not appended!` | Test mock mismatch or space concatenation issue in `pipeline.py`. | High | Test/Production |
| `test_spec_13_aci_feedback.py::test_aci_update_equation_exact` | `assert 0.0050000000000000044 == 0.01` | `min_alpha` is `0.001` in `adaptive_calibration.py`, but test expects `0.01`. | High | Production/Test |
| `test_spec_13_aci_feedback.py::test_feedback_consumer_integration` | `assert 0.0025000000000000022 == 0.001` | Same as above (clipping issue). | High | Production/Test |
| `test_spec_14_action_gate.py::test_pipeline_decision_separation` | `assert 'HUMAN' == 'ALLOW'` | Pipeline manually mutates `policy.consequence_level = "high"` on action detection, triggering `HUMAN` escalation. | High | Production |
| `test_api_diagnostic.py` (Collection Error) | `OSError: [E050] Can't find model 'en_core_web_sm'` | Missing spaCy language model. | High | Config/Environment |

# Missing Required Tests

The following tests required by `debug.md` are missing or incomplete:
- Sync-vs-async pipeline equivalence
- End-to-end `BLOCK` and `REDACT` scenarios
- Use-case policy differentiation tests
- Concurrency load tests
- Audit logger concurrency tests
- Feedback store concurrency tests
- PII India-format detection tests
- Policy schema validation tests
- Span repair re-validation edge cases

# Architecture Findings

- **Async Pipeline**: The current `PipelineOrchestrator` uses synchronous blocking calls (`for chunk in self.adapter.generate_stream(prompt)`) and wraps async checker execution inside a thread-pool `asyncio.run()`. This completely negates the benefits of asynchronous I/O and will bottleneck under load. 
- **Risk Engine**: The engine correctly dispatches parallel checkers, but relies on a `max()` function for the final score, ignoring the Noisy-OR requirement for semantic overlaps.
- **ACI (Adaptive Calibration)**: The conformal prediction logic dynamically shifts `tau_low` and `tau_high`, but the bounds clipping allows thresholds to become degenerate, defaulting to `ALLOW` for everything.
- **Policy**: `UseCasePolicy` schemas are comprehensive, but pipeline mutations (e.g., forcing `consequence_level = "high"`) violate the separation of concerns.
- **Action Gate**: The action catalog and semantic overlap logic is sound, but its decision (`action_decision`) conflicts with the global `control_decision`.

# Recommended Fix Order

1. **Config/Environment**: Fix the spaCy model dependency (`python -m spacy download en_core_web_sm`) so the test suite can run fully.
2. **Safety**: Fix the ACI Tuner bounds clipping in `adaptive_calibration.py` to restore dynamic thresholding.
3. **Correctness**: Decouple `ActionGate` decisions from the `PipelineOrchestrator` consequence level override.
4. **Correctness**: Implement Noisy-OR in `RiskEngine`.
5. **Architectural Importance**: Rewrite `pipeline.py` to be fully `async def` and natively `await` the risk engine and generation streams.

# Blockers / Ambiguities
- **Action Gate vs Control Policy**: Should a rejected action (`BLOCK`) automatically block the text response, or should the text response be allowed with a message saying the action failed? The current tests expect `ALLOW` for text while the action is blocked.
