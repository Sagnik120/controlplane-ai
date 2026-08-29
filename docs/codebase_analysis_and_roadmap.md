# Codebase Analysis & Roadmap
*Last Updated: August 2026*

This document provides an accurate, up-to-date analysis of the ControlPlane-AI codebase as it currently stands. It reflects all implemented SPECs up through **SPEC 16**, removing outdated assumptions and mapping the actual file structure.

---

## 1. System Architecture (Current State)

The system is designed as an **Enterprise GenAI Risk Orchestration Engine**. It intercepts prompts and LLM tool-calls, evaluates them in parallel against multiple risk dimensions (Performance, Safety, Bias, PII, Cost), and routes the response through a tiered Conformal Prediction policy (ALLOW, MODIFY, REGENERATE, BLOCK, HUMAN). 

It features dynamic calibration (Adaptive Conformal Inference), semantic overlap detection, agentic action gating, and an offline metrics dashboard.

### Core Technologies
- **Backend**: Python 3.11, FastAPI
- **LLM Integrations**: Google GenAI SDK (Gemini), Mock Adapter (for offline/deterministic testing)
- **Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2`) for semantic overlap detection.
- **Frontend**: Premium Vanilla HTML/CSS/JS (Zero-dependency, Glassmorphism aesthetic).
- **Storage**: Local JSONL files (Append-only logs for Audit, Human Review, and Metrics).

---

## 2. Directory Structure & File Index

The `src/` directory contains the entirety of the application logic. Here is what is actually implemented:

### `src/adapters/`
- **`base_adapter.py`**: Abstract base class defining `generate_once` and `generate_stream`.
- **`gemini_adapter.py`**: Implementation for Google Gemini (`google-genai`).
- **`mock_adapter.py`**: Simulates LLM responses for deterministic offline testing. It intelligently detects if it is being used for primary generation or as an "LLM-as-a-judge" to prevent evaluation loops.

### `src/agent/` (Agentic Gating - SPEC 14)
- **`action_gate.py`**: Implements the `ActionRiskChecker`. It acts as a preemptive interceptor for autonomous agent tool calls. Uses a two-tier approach: a fast semantic overlap check (Tier-0) against a catalog, followed by a strict LLM judge (Tier-1) for matching intent.
- **`action_catalog.yaml`**: Defines high-risk operations (e.g., `drop_database`, `execute_shell`) mapped to risk thresholds.

### `src/api/` (Presentation & Routing)
- **`main.py`**: The FastAPI application entrypoint. Mounts the `/api` routes and the static `/ui` directory.
- **`routes.py`**: Exposes `/api/chat`, `/api/policies`, and `/api/metrics` (for the Trust Dashboard).
- **`dependencies.py`**: Initializes the singleton Orchestrator, loads policies from YAML, and injects the active LLM Adapter.

### `src/audit/`
- **`audit_logger.py`**: Handles O(1) append-only logging of `FinalRiskReport` decisions and system metrics to `data/audit_log.jsonl` and `data/metrics_log.jsonl`. Branches HUMAN escalations into a separate queue.

### `src/checkers/` (Evaluation Layer)
- **`base.py`**: Defines the `BaseChecker` interface supporting the 2-Tier `tier0_gate` and `tier1_check` architecture.
- **`bias_checker.py`, `safety_checker.py`**: LLM-as-a-judge evaluators that check for stereotyping and illicit/dangerous content, guarded by fast regex pre-filters.
- **`pii_checker.py`**: Regex-based heuristic checker for sensitive data exfiltration (SSN, Email, Credit Cards).
- **`performance_checker.py`**: Heuristic checker for tone, formatting, and structural constraints.
- **`prompts/`**: Contains the raw text templates (`safety_judge_prompt.txt`, `bias_judge_prompt.txt`, etc.) for the LLM judges.

### `src/cost/`
- **`cost_monitor.py`**: Synchronous, stateless checker that calculates generation cost against the Use Case Policy budget.

### `src/engine/` (Parallel Processing & Overlap)
- **`risk_engine.py`**: Dispatches all checkers concurrently using a `ThreadPoolExecutor`. Compiles individual `CheckerResult`s into a single `FinalRiskReport`. Applies Consequence-Aware Latency Budgets (Circuit Breaker Timeouts) per SPEC 11.
- **`semantic_overlap.py`**: (SPEC 12) Implements `SemanticOverlapDetector`. Uses `char_iou` and Cosine Similarity (via MiniLM) to cluster redundant warnings from overlapping checkers and apply a Noisy-OR penalty.
- **`embedding_registry.py`**: Singleton registry to keep the `sentence-transformers` model resident in memory.

### `src/feedback/` (Adaptive Conformal Inference - SPEC 13)
- **`aci_tuner.py`**: The mathematical engine that dynamically adjusts `tau_low` and `tau_high` based on the miscoverage rate over a trailing window of Human Review verdicts.
- **`feedback_store.py`**: Interface for reading/writing `human_review_queue.jsonl`.
- **`online_learning.py`**: CLI script to trigger the ACI recalculation.

### `src/orchestrator/`
- **`pipeline.py`**: The main brain (`PipelineOrchestrator`). Currently a **synchronous** control loop. It processes a request, routes it to the `RiskEngine`, and delegates to `SpanRepairEngine` or `RegenerationEngine` based on Conformal Prediction thresholds (tau limits). Computes metrics like latency for the audit layer.

### `src/policy/`
- **`schemas.py`**: Pydantic models mapping directly to `configs/use_case_policies.yaml`. Defines the tiered budgets, conformal thresholds, and fallback rules.

### `src/regenerate/` (SPEC 09)
- **`checkpoint_backtrack.py`**: The `RegenerationEngine`. Iteratively re-prompts the LLM up to a `max_retries` limit, appending the explanation of *why* it failed the safety/bias checks to guide the model.

### `src/repair/` (SPEC 09)
- **`span_repair.py`**: The `SpanRepairEngine`. Targets isolated, localized violations (like a PII leak) with an LLM instruct prompt to redact or rewrite just the flagged span, saving latency compared to full regeneration.

### `src/ui/` (Dashboards)
- **`index.html`, `script.js`**: The main interactive testing harness. Allows selecting Use-Case policies, testing prompts, and viewing detailed Risk Reports.
- **`metrics.html`, `metrics.js`**: (SPEC 16) A static Trust Metrics dashboard. Visualizes Empirical vs Guaranteed Coverage, False Positive Rates, and Tier Distributions to prove statistical reliability.
- **`style.css`**: Shared styling.

---

## 3. What Works Beautifully (The Wins)

1. **Tiered Conformal Prediction Routing**: The core mathematical premise (SPEC 03/09) works flawlessly. Low-risk spans are fast-tracked (ALLOW), localized issues are repaired (MODIFY), heavy issues are scrubbed (REGENERATE), and intractable issues are blocked (HUMAN).
2. **Adaptive Conformal Inference (ACI)**: (SPEC 13) The system genuinely auto-corrects. As humans review the queue, the thresholds (`tau_low`, `tau_high`) mathematically drift to preserve the 95% safety guarantee, solving the "static rule" critique.
3. **Semantic Overlap & Agent Gating**: (SPECs 12 & 14) Using embeddings to catch both redundant policy alerts and highly obfuscated agent tool-calls (e.g. mapping "remove all user records" to `drop_database`) provides production-grade security without adding a 2-second LLM delay.
4. **Observable Trust Metrics**: (SPEC 16) The system proves its own worth via the static metrics dashboard, calculating empirical coverage mathematically rather than relying on hand-wavy assertions.

## 4. Current Limitations & Roadmap

1. **Synchronous Outer Loop (`pipeline.py`)**: While `RiskEngine` runs checkers in parallel threads, the main `PipelineOrchestrator` handles requests synchronously. A full `asyncio` rewrite (using `TaskGroup`) is necessary to handle massive concurrent traffic and true streaming proxy behavior (SPEC 15 - Shelved).
2. **Local File Persistence**: Audit logs and metrics rely on append-only `.jsonl` files. For horizontal scaling in a Kubernetes environment, this must transition to PostgreSQL / ElasticSearch (SPEC 10).
3. **Agent Feedback Context**: Currently, if the `ActionRiskChecker` blocks an agent's tool call, it just returns a block decision. It should ideally inject a system prompt back into the agent's context window explaining *why* it was blocked so the agent can self-correct.
