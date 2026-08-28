# ControlPlane.ai — Codebase Analysis and Roadmap

This document provides a structured analysis of the current state of the ControlPlane.ai repository. It assesses what has been built, how it aligns with the Round 1 and Round 2 problem statements, what critical features are missing, and a detailed breakdown of the codebase architecture and underlying logic.

---

## 1. What This Codebase is Capable Of

The current implementation provides a working prototype of a real-time Responsible AI Checker middleware. Its core capabilities include:

*   **Real-Time Observation:** Intercepts LLM generation requests via an adapter layer.
*   **Multi-Dimensional Risk Evaluation:** Analyzes responses across four dimensions: Performance, Safety, Bias, and PII leakage. It also monitors token cost and generation time.
*   **Risk Engine Aggregation:** Combines individual checker scores into a unified `FinalRiskReport`. It is capable of detecting **overlapping risks** (e.g., a text span that is both PII and Biased) and escalating the risk score accordingly.
*   **Configurable Governance (Policy Layer):** Uses YAML configurations to adjust risk tolerance based on the specific enterprise use-case (e.g., strict thresholds for a customer-facing chatbot vs. relaxed thresholds for internal research). Powered by **Conformal Prediction**, providing mathematical guarantees on error rates.
*   **Actionable Control:** Interprets the risk report against the active policy to issue a 4-tier calibrated decision: `ALLOW`, `MODIFY`, `REGENERATE`, or `HUMAN`.
*   **Audit Logging:** Durably records every request, response, risk profile, and decision to a local JSONL log for compliance and metrics tracking. It also routes `HUMAN` escalations to a dedicated review queue.

---

## 2. Alignment with the Problem Statement (PS)

**What is Achieved:**
*   **Architecture & Middleware Pattern:** The system successfully acts as a technology layer sitting on top of the foundation model, observing outputs before they reach the user.
*   **Varying Risk Tolerance:** The `use_case_policies.yaml` perfectly addresses the PS requirement that "a single, one-size-fits-all checking approach rarely works well everywhere."
*   **Complexity Handling (Overlaps):** The `risk_engine` addresses the PS note that "Bias, hallucination, and privacy risks often overlap."
*   **Governance & Audit:** The local JSONL audit trail fulfills the requirement for a "clear audit trail behind every decision."

**Partially Achieved:**
*   **Tiered Responses:** The system now routes responses into four distinct actions: `ALLOW`, `MODIFY`, `REGENERATE`, and `HUMAN`. However, `MODIFY` currently returns a structured fallback rather than actively employing a micro-repair LLM prompt (which is slated for a future spec).
*   **Human-in-the-Loop Escalation:** The policy successfully catches severe risks and routes them to a `human_review_queue.jsonl`, but a dedicated Human Review UI dashboard is pending.

---

## 3. What is Remaining (Focus Areas for Next Phase)

To build a robust, production-ready solution that fully addresses the Round 2 PS, the following areas represent critical gaps that must be solved:

1.  **Intelligent Edit & Modify (Span-Level Repair):** 
    *   *Current State:* The `MODIFY` action correctly triggers when risk spans cover < 25% of the response text, but it currently returns a fallback string.
    *   *Required:* Implement a dynamic rewriting layer. The system should use a secondary LLM or intelligent parser to edit out *only* the flagged spans via RAG+micro-repair, allowing the rest of the safe response to pass through seamlessly.
2.  **Advanced Bias & Safety Checkers:** 
    *   *Current State:* Performance is handled by SelfCheckGPT and PII by Presidio/Transformers. However, Bias and Safety checkers still rely on static regex and keyword matching.
    *   *Required:* Integrate LLM-as-a-judge (e.g., G-Eval/RAGAS-style) or statistical anomaly detection for Bias and Safety to eliminate high false-positive rates.
4.  **Multi-turn Conversation Context:** 
    *   *Current State:* The `orchestrator` evaluates a single response payload in total isolation. 
    *   *Required:* AI agents take actions across multi-turn chats. The system must maintain a rolling context window to detect compounding risks where one questionable output shapes downstream behavior.
5.  **Feedback Loops:** 
    *   *Current State:* No mechanism exists to learn from mistakes.
    *   *Required:* A pipeline where overridden/flagged cases (especially those corrected by a human) are fed back into the system to tune thresholds or fine-tune the detection models.

---

## 4. Exhaustive Codebase Explanation (`src/` Deep Dive)

Understanding the underlying logic of the modules is critical, as the current rule-based architecture is a prototype that will fail in real-world scenarios. Below is a detailed, folder-by-folder and file-by-file breakdown of the core execution layer (`src/`).

### `src/adapters/`
**Purpose:** Standardized wrappers for different LLM foundation providers to ensure the orchestrator can intercept generation streams uniformly.
*   **`base_adapter.py`**: 
    *   **Purpose:** Defines the abstract base class `BaseLLMAdapter` that all adapters must inherit from. It enforces the `generate_stream` contract.
    *   **Logic:** Interface definition only.
*   **`gemini_adapter.py`**:
    *   **Purpose:** Connects to Google's Gemini API using the `google-genai` SDK. 
    *   **Logic:** Streams the chunks directly from the API. Handles basic connection logic.
*   **`mock_adapter.py`**:
    *   **Purpose:** A deterministic dummy LLM used for testing without burning API credits.
    *   **Logic:** **Rule-Based.** It checks the input prompt for specific keywords (like "bias", "unsafe", "pii") and yields a hardcoded string simulating a stream. 

### `src/api/`
**Purpose:** Exposes the application over HTTP using FastAPI.
*   **`main.py`**:
    *   **Purpose:** The FastAPI application entrypoint. It mounts the API routes and serves the static Vanilla HTML/CSS UI.
*   **`routes.py`**:
    *   **Purpose:** Defines the HTTP endpoints (e.g., `/chat` for generation, `/policies` for dropdown configs).
    *   **Logic:** It acts as a controller. It takes the incoming HTTP request, fetches the requested policy, and passes it to the `PipelineOrchestrator`. 
*   **`dependencies.py`**:
    *   **Purpose:** Manages Dependency Injection for FastAPI. Initializes global instances of the `RiskEngine`, `ControlPolicy`, `AuditLogger`, and the `MockAdapter`.
    *   **Logic:** Also contains the hardcoded demo `POLICIES` (Standard, Medical, Lenient).

### `src/audit/`
**Purpose:** Durable storage for tracking system decisions.
*   **`audit_logger.py`**:
    *   **Purpose:** A local JSON-based logger.
    *   **Logic:** **File I/O.** It takes the `FinalRiskReport` and `ControlDecision` objects, converts them to JSON, and appends them in O(1) time complexity to `data/audit_log.jsonl`. No complex analytics happen here yet.

### `src/checkers/`
**Purpose:** Individual modules that inspect text for specific risk categories.
**Logic Used:** A mix of advanced statistical models and legacy rules. The Performance and PII checkers have been upgraded, but Bias and Safety still require modernization.
*   **`base.py`**: Defines the `CheckerResult` schema that all checkers must return.
*   **`pii_checker.py`**:
    *   **Logic:** Uses a hybrid Microsoft Presidio pipeline. Combines base regex/checksums with a HuggingFace transformer model (`piiranha-v1`) for unstructured text. Employs context-word boosting to catch obfuscated edge cases (e.g., "my number is 5 five 5...").
*   **`bias_checker.py`**:
    *   **Logic:** Uses Regex to find demographic keywords located within 30 characters of a stereotypical phrase (e.g., "women" + "are typically"). Fails to detect implicit bias or dog-whistles. *(Pending Upgrade)*
*   **`safety_checker.py`**:
    *   **Logic:** Uses basic substring matching against a hard-coded array of unsafe keywords (e.g., "kill", "bomb"). Will aggressively over-flag innocent queries (e.g., "kill a background process"). *(Pending Upgrade)*
*   **`performance_checker.py`**:
    *   **Logic:** Uses a Zero-Resource hallucination detector based on **SelfCheckGPT**. It samples the LLM multiple times and measures structural consistency via NLI (Natural Language Inference) and BERTScore to calculate uncertainty. Highly robust.

### `src/cost/`
**Purpose:** Monitors generation metrics to prevent budget burns.
*   **`cost_monitor.py`**:
    *   **Logic:** **Rule-Based Math Heuristic.** It divides the response length by 4 to estimate tokens, and calculates a risk score based on a static threshold (e.g., > 2000 tokens) combined with generation time penalties.

### `src/engine/`
**Purpose:** Central aggregator for all individual checker modules.
*   **`risk_engine.py`**:
    *   **Purpose:** Takes outputs from all checkers and forms the `FinalRiskReport`.
    *   **Logic:** **Rule-Based Aggregation.** It calculates "overlaps" by checking if text character indices flagged by different checkers intersect. If an overlap is detected, it applies a static +0.15 mathematical penalty to the final risk score. 
    *   **Verdict:** While functional, a static penalty is inflexible. Dynamic weighting based on the *severity* of the overlapping categories would be more robust.

### `src/orchestrator/`
**Purpose:** The central nervous system of ControlPlane-AI.
*   **`pipeline.py`**:
    *   **Purpose:** Executes the end-to-end flow. 
    *   **Logic:** **Synchronous Procedural Flow.** 1) Fetches LLM response via adapter. 2) Passes it to `RiskEngine`. 3) Gets 4-tier decision from `ControlPolicy`. 4) Logs to `AuditLogger`. 5) Returns final output. It handles extreme failures by injecting a synthetic "SYSTEM EXCEPTION" block decision.

### `src/policy/`
**Purpose:** The governance configuration and enforcement layer.
*   **`schemas.py`**: Defines Pydantic data models for `UseCasePolicy` and `ControlDecision`.
*   **`control_policy.py`**:
    *   **Purpose:** The decision-maker. Compares the `FinalRiskReport` against the use-case configuration.
    *   **Logic:** **Conformal-Prediction-Calibrated Tiered Routing.** Instead of arbitrary thresholds, it uses statistically derived bounds (`tau_low`, `tau_high`) to guarantee error limits. It evaluates span coverage density to decide between targeted `MODIFY` (<25% coverage) or full `REGENERATE` (>25% coverage), and immediately escalates high risks to `HUMAN`.

### `src/ui/`
**Purpose:** Static frontend dashboard.
*   **`index.html`**, **`script.js`**, **`style.css`**: Vanilla web files that interact with the FastAPI backend. No complex state management frameworks are used.

### Non-`src/` Folders Summary
*   **`tests/`**: Diagnostic scripts (`tests/checkers/`, `tests/run_all_diagnostics.py`). Validate that rule-based heuristics behave as expected against hand-crafted edge cases.
*   **`configs/`**: Contains `use_case_policies.yaml`, an essential file that defines specific thresholds (`max_overall_risk`) and behaviors for different operational modes.
*   **`data/`**: Persistent storage, containing `audit_log.jsonl`.
