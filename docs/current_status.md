# ControlPlane-AI Current Status
*Last Updated: August 2026*

This document serves as the definitive ground truth for what is currently implemented, tested, and verified in the ControlPlane-AI repository. It reflects the completion of Tasks 1–8 and successful validation on both deterministic mocks and the live Gemini API.

---

## 1. Project Overview
ControlPlane-AI is a tiered intervention engine designed to intercept, assess, and repair LLM outputs. It uses an asynchronous risk-checking engine to evaluate multiple risk dimensions concurrently, routing the response through a Conformal-Prediction-based policy (ALLOW, MODIFY, REGENERATE, BLOCK, HUMAN).

---

## 2. Problem Statement / Requirement Mapping

For every theoretical capability in the original problem statement, here is the exact current state of the codebase:

| Capability | Current Status | Notes |
| :--- | :--- | :--- |
| **Control Policy** | **Fully Implemented** | Uses statistical Noisy-OR and ACI-drifted conformal thresholds. |
| **Tiered Intervention** | **Fully Implemented** | Native support for ALLOW, MODIFY, REGENERATE, BLOCK, and HUMAN paths. |
| **Action Gating** | **Fully Implemented** | Semantic overlap mapping intent against a high-risk autonomous action catalog. |
| **PII Monitoring** | **Fully Implemented** | Uses Presidio deterministic patterns (including India-specific entities). |
| **Safety/Bias Monitoring** | **Fully Implemented** | Uses LLM-as-a-judge approaches for detection, guarded by keyword pre-filters. |
| **Performance Monitoring** | **Partially Implemented** | Integrates local NLP tools (SelfCheckGPT, Spacy) for hallucination risk. |
| **Async Architecture** | **Fully Implemented** | Entire engine and FastAPI endpoint run natively via Python `asyncio`. |
| **Cost/Quota Handling** | **Prototype** | Uses a mock Pytest intercepter to guard developer quotas, not live spot-pricing dispatch. |
| **Repair & Regeneration** | **Partially Implemented** | Relies on basic string splicing for MODIFY and full text regeneration for REGENERATE. |
| **Black-box evaluation** | **Fully Implemented** | Operates strictly on post-generation text strings outputted by the LLM. |
| **Adaptive ACI** | **Prototype** | Exists as an iterative math function adjusting thresholds based on human review history. |
| **Grey-box evaluation** | **Not Implemented** | No access to model token logits or hidden tensor states. |
| **Streaming / In-flight** | **Not Implemented** | The pipeline buffers the entire string before evaluating risk. No sliding window. |
| **Dynamic Model Routing** | **Not Implemented** | Hardcoded to a single adapter configuration. |
| **RAG / Evidence Retrieval**| **Not Implemented** | Does not utilize vector databases or contextual grounding. |

---

## 3. Current Architecture

```text
User Request
     │
     ▼
[ API (FastAPI) ] ──(native async)──> [ PipelineOrchestrator (process_request_async) ]
                                          │
                                          ├── 1. Generate text (Gemini Adapter)
                                          │
                                          ├── 2. Risk Engine (async asyncio.gather)
                                          │      ├── PIIChecker (Presidio)
                                          │      ├── SafetyChecker (LLM Judge)
                                          │      ├── BiasChecker (LLM Judge)
                                          │      └── PerformanceChecker (SelfCheckGPT)
                                          │
                                          ├── 3. Session State (Cumulative Tracking)
                                          │
                                          ├── 4. Control Policy (Thresholds & ACI)
                                          │
                                          ├── 5. Interventions (5 Tiers)
                                          │
                                          └── 6. Audit Logger (.jsonl files)
                                          │
                                    [ Final Response ]
```

---

## 4. End-to-End Execution Flow
1. A request enters `PipelineOrchestrator.process_request_async()`.
2. The orchestrator instructs the LLM adapter to generate a full text response.
3. The response is passed to `RiskEngine.evaluate_response_async()`, spawning concurrent async tasks for PII, Safety, Bias, and Performance.
4. Overlaps are detected and Noisy-OR math aggregates the risk.
5. `ControlPolicy.evaluate()` checks the scores against dynamic `tau_low` and `tau_high` bounds.
6. The appropriate tier intervention (ALLOW, MODIFY, REGENERATE, BLOCK, HUMAN) is applied.

---

## 5. Current Validations

### Deterministic E2E Validation (6/6 PASS)
The pipeline explicitly validates all logical branches using deterministic mock adapters to ensure mathematical certainty:
- **Clean Request**: Risk < tau_low → `ALLOW`.
- **Moderate Safety Risk**: Risk > tau_low → `MODIFY` → Silent Repair.
- **Moderate PII Risk**: Risk > tau_low → `MODIFY` → Presidio Anonymization.
- **Failed Repair Verification**: Repair fails secondary check → `REGENERATE`.
- **High Risk**: Risk >= tau_high → `HUMAN`.
- **Multi-Turn Session State**: Cumulative PII > limits → `HUMAN`.

### Real Gemini Smoke Test Validation
*(Validated via `scripts/live_gemini_smoke.py`)*

The system successfully integrates with the live Google GenAI API. 
The first attempt failed because the previously configured `gemini-2.5-flash` model was deprecated, confirming the pipeline's failure states. The model configuration was updated to `gemini-3.6-flash`.

The **second execution successfully completed one real Gemini request** through the fully integrated ControlPlane pipeline. 
**Actual Results Produced:**
- **Final Action**: ALLOW
- **Overall Risk**: 0.10
- **Checker Breakdown**:
  - Performance: 0.10 (Bypassed Tier-1 SelfCheckGPT due to low initial confidence)
  - Safety: 0.00
  - Bias: 0.00
  - PII: 0.00
  - Cost: 0.00 (3 tokens generated)

No checker or API errors occurred.

---

## 6. Current Limitations
These limitations reflect the explicit constraints of the current working prototype:
- **Black-Box Only**: The current system only operates on post-generation text strings. It cannot evaluate model confidence mathematically via logit/token distributions.
- **Synchronous Buffering**: The pipeline evaluates the complete response after generation. True in-flight risk interception during token streaming is not implemented.
- **String Splicing Brittleness**: The `MODIFY` intervention uses naive `.replace()` logic, which easily breaks under complex LLM formatting drift.
- **Heavy NLP Overhead**: The `PerformanceChecker` utilizes PyTorch/Spacy which injects significant synchronous I/O delay, counteracting the async architecture.
- **Ephemeral State**: Relies entirely on local `.jsonl` files for persistence, metrics, and audit history. It lacks a production-grade backend (e.g. Postgres/Redis) for real human-review infrastructure.

---

## 7. Next Improvement Opportunities
*Ranked by visible demo impact, alignment with the original problem statement, and feasibility:*

1. **Streaming / In-Flight Risk Interception (High Impact, Medium Effort)**
   - *Value*: True real-time intervention is the ultimate differentiator for an enterprise "Control Plane".
   - *How*: Inject a buffer hook into `adapter.generate_stream()` to fire lightweight PII/Regex checkers every 20 tokens, forcefully killing the stream if `tau_high` is breached, before the text even reaches the user.

2. **Lightweight Evidence-Grounded Repair (High Impact, Medium Effort)**
   - *Value*: Makes the `MODIFY` pipeline significantly more robust and reliable.
   - *How*: Eliminate brittle Python string manipulation. Pass the original text, the flagged span, and the specific checker violation to the LLM directly as a structured repair prompt, returning a newly synthesized safe string, bypassing raw Python string manipulation entirely.

3. **LLM-Judge Structured JSON Outputs (Medium Impact, Low Effort)**
   - *Value*: Prevents pipeline crashes / parsing errors when the model responds creatively.
   - *How*: Force `response_mime_type="application/json"` on the API adapter configuration for internal Judge LLM calls.

4. **Grey-Box Logit Monitoring (High Innovation, High Effort)**
   - *Value*: True grey-box capability provides predictive failure detection ahead of the generation completing.
   - *How*: Implement a local HuggingFace adapter (`transformers`) that exposes token logprobs. If average logprob confidence drops below a threshold, flag it as a hallucination early (bypassing heavy SelfCheckGPT).
