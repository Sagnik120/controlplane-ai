# ControlPlane-AI: Codebase Reality & Architecture

## 1. How This Solves the Hackathon Problem Statement

The hackathon challenged us to build a **Responsible AI Checker** that monitors AI responses in real-time for performance (hallucinations), cost, and responsibility (bias/PII). Round 2 expanded this to require handling **multiple use cases with different risk tolerances**, dealing with **overlapping risks**, avoiding **alert fatigue** vs liability, and handling **multi-turn session risks**.

**Here is how our pipeline explicitly solves this:**
1. **Dynamic Risk Tolerance (Use Cases)**: Instead of a hardcoded threshold, we implemented **Conformal Prediction Calibration** (`src/policy/`). Each use case (e.g., Customer Support vs. Internal Chat) has its own `.yaml` config defining acceptable statistical bounds (`alpha_low`, `alpha_high`). The system automatically tunes its blocking thresholds (`tau_low`, `tau_high`) to mathematically guarantee the error rate stays within that specific use-case's budget.
2. **Tiered Decision Logic (Combating Alert Fatigue)**: Instead of binary ALLOW/BLOCK, we implemented 4 tiers: ALLOW, MODIFY (Silent Repair), REGENERATE, and HUMAN (Escalation). This avoids alert fatigue by *silently repairing* moderate risks on the fly, only escalating to a human when the risk mathematically exceeds the conformal bound (`tau_high`).
3. **Overlapping Risks**: Our `PipelineOrchestrator` runs an ensemble of checkers. The `RiskEngine` specifically flags when multiple dimensions overlap (e.g., PII intersecting with a Hallucination) and can escalate severity based on that intersection.
4. **Multi-turn Compounding Risk**: We built `SessionRiskState`. Instead of treating every prompt in isolation, it tracks the user's trajectory over time. It uses Sentence Transformers to measure **Semantic Drift** (is the user slowly jailbreaking the agent away from its initial intent?) and tracks **Cumulative PII Exposure** (leaking identity fragments one by one over 10 turns).
5. **Real-time Intelligent Repair**: We built a `SpanRepairEngine` that catches a flaw, routes PII to a deterministic Presidio anonymizer, and routes hallucinations to a strict, low-temperature LLM micro-repair prompt. It surgically splices *only* the broken sentence, leaving the rest of the response untouched, and re-verifies the patch before release.

---

## 2. The Unfiltered Reality of the Codebase (src/ Directory)

This is a hackathon prototype. While the architectural patterns are state-of-the-art, the implementation trades production-scale optimizations for immediate functionality. Here is the unfiltered reality of what is currently built in `src/`.

### `src/adapters/`
- **What it is**: `base_adapter.py` and `gemini_adapter.py`.
- **The Reality**: Connects to the real Google Gemini API via the `google-genai` SDK. It works, but it is entirely synchronous. In a production real-time inline proxy, this needs to be heavily asynchronous and streamed chunk-by-chunk to the checkers. Currently, we block and accumulate the whole string before checking.

### `src/audit/`
- **What it is**: `audit_logger.py`.
- **The Reality**: A primitive JSONL file appender. It successfully logs every decision, risk score, and metadata (session drift, human verdicts). However, it is not a real database (no Postgres/Elasticsearch), meaning it is entirely unsuited for real-world concurrent read/write scaling.

### `src/checkers/`
- **`performance_checker.py`**: **State-of-the-Art.** Implements the SelfCheckGPT framework (NLI + BERTScore) using HuggingFace sentence-transformers. It detects hallucinations by checking consistency across multiple sampled LLM responses. **Drawback**: Extremely computationally heavy. It is accurate, but too slow for a synchronous inline proxy without dedicated GPU hardware.
- **`pii_checker.py`**: **Robust Hybrid ML/Rules.** Uses Microsoft Presidio combined with a custom HuggingFace NER model (`piiranha-v1`). It is highly accurate and robust against obfuscation (e.g., spaced out phone numbers) due to context-boosting rules.
- **`safety_bias_checker.py`**: **Standard ML Baseline.** Uses the `unitary/toxic-bert` model. It is a solid, standard approach to toxicity detection, far better than regex word-lists, but can struggle with subtle implicit bias.

### `src/engine/`
- **What it is**: `risk_engine.py`
- **The Reality**: Iterates through the checkers to build a `FinalRiskReport`. 
- **The Flaw**: It runs sequentially. In a real environment, checking PII, Toxicity, and Hallucinations must happen in parallel (async) to meet latency budgets. Our overlap detection is also currently a rudimentary regex bounding-box check rather than semantic overlap.

### `src/policy/`
- **What it is**: `control_policy.py`, `schemas.py`
- **The Reality**: **State-of-the-Art Concept.** Implements the mathematics of Conformal Prediction to set tier thresholds based on desired error rates. However, our calibration phase is simulated using a mock dataset rather than a massive historical data warehouse. The routing logic (ALLOW -> MODIFY -> REGENERATE -> HUMAN) is exceptionally robust and handled all of our edge-case matrix tests flawlessly.

### `src/repair/`
- **What it is**: `span_repair.py`
- **The Reality**: **State-of-the-Art Pattern.** It does not use a naive "rewrite this whole text" prompt. It uses exact string splicing to preserve the original output byte-for-byte, executing a micro-prompt at `temperature=0.2` to surgically fix only the flawed sentence, and leverages Presidio for deterministic PII tagging. It includes a strict re-verification loop that successfully catches failed LLM repairs and escalates them.

### `src/session/`
- **What it is**: `session_state.py`
- **The Reality**: **State-of-the-Art Heuristics.** Uses `all-MiniLM-L6-v2` embeddings to track cosine distance across user prompts over time, measuring "Drift from Start" and "Immediate Cross-Turn Drift" to catch slow-burn adversarial jailbreaks. It works beautifully in memory, but state is currently just kept in a Python dictionary. A production deployment requires Redis or Memcached.

### `src/feedback/`
- **What it is**: `feedback_store.py`
- **The Reality**: **Basic Implementation.** It reads a human review queue, deduplicates by timestamp, and appends to a calibration set. The "Active Learning" script mathematically shifts the conformal bounds based on human overrides (fixing false positives). It demonstrates the feedback loop perfectly, but lacks a real UI or database backend for the human reviewer.

---

## 3. The End-to-End Pipeline in Plain English

When a user sends a prompt, here is exactly what the `PipelineOrchestrator` does:

1. **Generation**: It asks the LLM for a response.
2. **Observation (The Checkers)**: It hands the response to the Risk Engine. The engine runs Heavy ML models (BERT, NLI, NER) to calculate a risk score from 0.0 to 1.0 for Safety, Hallucination, and PII.
3. **Session Context**: It checks the user's history. Have they been slowly shifting the topic to something dangerous over the last 5 turns? Have they leaked 3 pieces of PII over the last 10 minutes?
4. **The Policy Judge**: It looks at the specific Use Case config. If this is a high-risk medical app, the threshold for blocking is tiny. If it's an internal sandbox, the threshold is higher. It compares the Risk Scores against these mathematically calibrated thresholds.
5. **The Intervention (Repair)**:
   - If the risk is low, it **ALLOWS** it.
   - If the risk is moderate and localized (e.g., one toxic sentence or one SSN), it halts the response. It runs the **Span Repair Engine** to surgically anonymize the SSN or rewrite the single toxic sentence. It *re-checks* the repaired text, and if it's safe now, it silently releases it.
   - If the risk is high, or the repair failed, it forces the LLM to **REGENERATE**.
   - If the risk is extreme, or the user is exhibiting adversarial session drift, it hard-blocks the request and escalates to a **HUMAN**.
6. **Audit**: Every single score, decision, and replaced string is logged to an immutable JSONL file for governance review and active learning recalibration.
