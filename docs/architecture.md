# ControlPlane-AI — System Architecture & Theoretical Framework

> **Document Version**: 2.4.0-ENTERPRISE  
> **Status**: Production Architecture & Research-Grade Specification  
> **Target Audience**: Enterprise AI Architects, Governance Committees, Regulatory Reviewers, and System Diagram Generators.

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Enterprise Problem Statement (PS)
Modern enterprises deploy Large Language Models (LLMs) across heterogeneous, mission-critical environments—ranging from real-time customer chatbots and code copilots to highly regulated financial and medical decision-support agents. 

However, adopting generative AI introduces four catastrophic runtime risks:
1. **Performance & Reliability Failures**: Stochastic hallucinations, logical self-contradictions, and ungrounded factual assertions.
2. **Regulatory & Compliance Breaches**: Data exfiltration, exposure of Personally Identifiable Information (PII), localized regional IDs (e.g., Indian PAN, Aadhaar, US SSN, EU GDPR identifiers), and intellectual property leakage.
3. **Safety & Demographic Disparities**: Harmful instructional planning, hate speech, jailbreak exploits, and systemic demographic/historical bias.
4. **Agentic Tool Exploitation**: Autonomous agents initiating high-risk, destructive system actions (database drops, unauthorized fund transfers, credential modifications) without verified human confirmation.

### 1.2 Limitations of Legacy Approaches
Traditional AI governance attempts to solve this via two flawed paradigms:
* **Pre/Post-Hoc Binary Filters**: Static regex or keyword blocklists that act as opaque walls. They either pass or hard-block an entire generation, destroying user experience and failing on nuanced, semantic risks.
* **Ungrounded Heuristic Scoring**: Arbitrary score averages (e.g., $Score_{avg} = \frac{Safety + Bias}{2}$) that obscure extreme single-dimension liabilities and lack mathematical coverage guarantees.

### 1.3 The ControlPlane-AI Proposed Solution
**ControlPlane-AI** is a model-agnostic, runtime risk orchestration middleware positioned directly in-flight between client applications and downstream foundation models (Google Gemini, OpenAI GPT, Anthropic Claude, or local OSS models). 

Instead of binary pass/fail filters, ControlPlane-AI implements:
1. **Tiered Mathematical Conformal Inference**: Calibrated Split Conformal Prediction ($1 - \alpha$ risk-coverage bounds) and online **Adaptive Conformal Inference (ACI)** tracking data drift.
2. **5-Tier Dynamic Interventions**: 
   - `ALLOW` (zero-latency release)
   - `MODIFY` (surgical in-place regex/LLM token repair)
   - `REGENERATE` (Checkpoint-Backtrack-Resample prefix-preserving recovery)
   - `HUMAN` (escalation to an audit queue)
   - `BLOCK` (fail-safe hard halt)
3. **Cross-Checker Semantic Overlap Detection**: Noisy-OR probabilistic compounding when multiple orthogonal checkers detect co-occurring risk spans.
4. **Dual-Plane Agentic Action Gate**: Strict isolation between linguistic text generation and agentic tool invocation.

---

## 2. End-to-End System Architecture

The ControlPlane-AI engine executes across 6 sequential, deterministic phases:

```
[ CLIENT INGESTION ] 
         │  (Prompt, SessionContext, ProposedAction)
         ▼
[ 1. INGESTION & ASYNC BUFFER ] ───► [ 2. ADAPTER LAYER ] ───► (LLM Providers: Gemini / Claude / GPT)
                                              │ (Token Stream In-Flight)
                                              ▼
                                 [ 3. PARALLEL RISK ENGINE ]
                                 ┌─────────────────────────┐
                                 │ • PII Presidio Hybrid   │
                                 │ • Safety Judge Rubric   │
                                 │ • Bias Parity Filter    │
                                 │ • SelfCheckGPT NLI/BERT │
                                 │ • Cost & Token Monitor  │
                                 └─────────────────────────┘
                                              │
                                              ▼
                                 [ 4. SEMANTIC OVERLAP & NOISY-OR ]
                                              │
                                              ▼
                                 [ 5. ADAPTIVE CONFORMAL POLICY GATE ]
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
             [ TIER 1: ALLOW ]        [ TIER 2: MODIFY ]       [ TIER 3: REGEN ]
             (Direct Release)         (Surgical Repair)        (Prefix Backtrack)
                    │                         │                         │
                    └─────────────────────────┼─────────────────────────┘
                                              │
                                 ┌────────────┴────────────┐
                                 ▼                         ▼
                          [ TIER 4: HUMAN ]         [ TIER 5: BLOCK ]
                          (Review Queue)            (Fail-Safe Halt)
                                              │
                                              ▼
                                 [ 6. AUDIT & OBSERVABILITY ] ───► [ POSTGRESQL / JSONL LEDGER ]
```

---

## 3. Deep-Dive Component Breakdown

### Component 1: Adapter Layer & Model Ingestion
* **Purpose**: Abstract all model provider differences behind a single asynchronous streaming protocol (`generate_stream()` and `generate_once()`).
* **Components**:
  * `BaseLLMAdapter`: Unified abstract interface.
  * `GeminiAdapter`: Modern Google GenAI SDK integration (`gemini-3.6-flash`) with automated token usage telemetry.
  * `FallbackHandler`: Resilient upstream quota protection (`429 RESOURCE_EXHAUSTED` circuit breaking) that halts the pipeline with authentic provider error telemetry rather than silent corruption.

### Component 2: Parallel Multi-Risk Engine (2-Tier Gating)
To maintain sub-120ms latency, every risk checker implements a **2-Tier Gated Hierarchy**:
* **Tier-0 (Microsecond Heuristic Gate)**: Fast regex matching, digit sequence verification, or entropy checks run in $<2\text{ms}$. If Tier-0 detects zero risk shape, execution bypasses Tier-1 entirely.
* **Tier-1 (Deep Semantic Evaluation)**: Heavy evaluations run only on flagged windows inside an asynchronous worker pool (`ThreadPoolExecutor`).

#### The 5 Risk Dimensions:
1. **PII & Data Exposure Checker (`PiiChecker`)**:
   * *Engine*: Microsoft Presidio Analyzer + Regional Pattern Recognizers.
   * *Coverage*: US SSN, Global Emails, IP Addresses, Credit Cards, and Indian Financial Identifiers (**IN_PAN**: 10-digit alphanumeric tax ID, **IN_AADHAAR**: 12-digit UIDAI).
2. **Content Safety Checker (`SafetyChecker`)**:
   * *Engine*: Structured LLM-as-a-Judge taxonomy evaluating Violence, Weapons, Illegal Acts, and Hate.
   * *Mechanism*: Taxonomy-aligned prompt extraction with regex JSON recovery.
3. **Fairness & Bias Checker (`BiasChecker`)**:
   * *Engine*: Demographic pre-filter cross-referencing demographic identifiers with stereotypical assertion regexes.
4. **Performance & Hallucination Checker (`PerformanceChecker`)**:
   * *Engine*: **SelfCheckGPT** (Zero-resource stochastic consistency evaluation).
   * *Mechanism*: Evaluates sentence-level contradiction across stochastic samples using DeBERTa-v3 NLI and BERTScore embeddings.
5. **Cost & Token Monitor (`CostMonitor`)**:
   * *Mechanism*: Tracks prompt tokens, generated output tokens, latency budgets, and computes compute-efficiency ratios.

### Component 3: Semantic Overlap & Probabilistic Compounding
When multiple checkers flag the same span or co-occurring sentences (e.g., an unauthorized personal detail that is *also* hallucinated), standard additive scoring causes distortion.

ControlPlane-AI implements **Noisy-OR Probabilistic Aggregation**:
$$\text{Risk}_{\text{aggregate}} = 1 - \prod_{i=1}^{N} (1 - r_i)$$

Where $r_i$ represents individual checker risk probabilities. If spatial or sentence-level span intersection is verified by the `SemanticOverlapDetector`, a parameterized overlap multiplier $M_{\text{overlap}} \in [1.15, 1.35]$ is applied:
$$\text{Risk}_{\text{final}} = \min\left(1.0, \, \text{Risk}_{\text{aggregate}} \times M_{\text{overlap}}\right)$$

### Component 4: Conformal Control Policy & Adaptive Drift Tracking
Instead of arbitrary heuristic thresholds, the `ControlPolicy` computes non-conformity quantiles over a calibrated validation distribution $\mathcal{D}_{\text{cal}}$:

* **Conformal Coverage Formulation**:
  $$\hat{q} = \text{Quantile}\left(1 - \alpha; \, \{R_i\}_{i=1}^n\right) \cdot \left(1 + \frac{1}{n}\right)$$
  Yielding statistically bounded lower ($\tau_{\text{low}}$) and upper ($\tau_{\text{high}}$) decision boundaries.

* **Adaptive Conformal Inference (ACI)**:
  Under production concept drift, the error rate $\alpha_t$ dynamically self-corrects:
  $$\alpha_{t+1} = \alpha_t + \gamma (\alpha - \text{err}_t)$$
  $$\tau_{t+1} = \text{Clip}\left(\tau_t + \eta (\text{err}_t - \alpha), \, \tau_{\text{floor}}, \, \tau_{\text{ceiling}}\right)$$

### Component 5: Surgical Edit, Backtrack & Action Gate
* **Tier 2 MODIFY (Surgical In-Place Repair)**:
  * PII spans are excised and substituted using Presidio anonymization tokens (`<IN_PAN>`, `<EMAIL_ADDRESS>`).
  * Linguistic hallucinations and bias spans are spliced and re-verified in-place without discarding the surrounding valid context.
* **Tier 3 REGENERATE (Checkpoint-Backtrack-Resample - CBR)**:
  * Preserves validated prefix tokens $[w_1, \dots, w_k]$.
  * Rewinds stream pointer to the first invalid token index $k+1$ and resamples only the contaminated suffix with temperature adjustment.
* **Action Gate (SPEC 14 Tool Isolation)**:
  * Enforces dual-decision separation: A generated text explanation can be `ALLOW`ed while an accompanying destructive tool execution (e.g., `drop_table`, `refund_payment`) is independently intercepted and `BLOCK`ed.

### Component 6: Audit & Telemetry Ledger
Every request generates an immutable, structured event log recording:
* `request_id` (UUIDv4) & `session_id`
* Applied `UseCasePolicy` profile & calibrated $\tau_{\text{low}}, \tau_{\text{high}}$ bounds
* Full sub-checker risk vector & detected entity spans
* Conformal decision verdict, execution latency ($\text{ms}$), and token cost

---

## 4. Architectural Diagram Prompt Specification (For LLM / Diffusion Image Generation)

Use the following highly structured, precise prompt to generate an award-winning, research-grade architectural diagram:

```text
A professional, publication-quality system architecture diagram of an enterprise AI governance engine named "ControlPlane-AI", designed in the clean, sophisticated visual style of an IEEE / ACM Nature Machine Intelligence research paper. 

Layout and Composition:
- Wide landscape layout (16:9 aspect ratio) with an asymmetric Swiss information design grid.
- Dark ink navy background (#070B14) with subtle slate grid lines, vibrant Control Lime (#C8F45A) primary active routing lines, Cobalt Blue (#2563EB) structural containers, and Coral Red (#EF4444) warning pathways.
- Crisp vector aesthetics, sharp geometric containers, subtle drop shadows, thin structural connector lines with glowing data packet nodes.
- High contrast, pristine typography using Space Grotesk for block titles and JetBrains Mono for system metrics and telemetry labels.

Architecture Flow (Left to Right):

1. LEFT SECTION - "CLIENT & MODEL INGESTION LAYER":
   - Box labelled "USER / CLIENT APPLICATION" sending payload: "Prompt + Session Context + Proposed Action".
   - Flow line connects to "FASTAPI ASYNC PROXY GATEWAY" with sub-labels "Session Store", "Latency Circuit Breaker (<120ms)".
   - Connected to "LLM ADAPTER INTERFACE" with provider icons/nodes for "Google Gemini", "OpenAI GPT", "Anthropic Claude", "Local LLMs".

2. MIDDLE SECTION - "PARALLEL RISK ORCHESTRATION ENGINE":
   - Large central processing container labelled "PARALLEL RISK ENGINE (ASYNC THREAD POOL)".
   - Four horizontal parallel inspection lanes inside:
     a) "01 / PII & EXPOSURE" -> "Presidio Hybrid (PAN, Aadhaar, SSN, Email)"
     b) "02 / SAFETY" -> "LLM-as-a-Judge Taxonomy Rubric"
     c) "03 / BIAS & FAIRNESS" -> "Demographic Parity Filter"
     d) "04 / PERFORMANCE" -> "SelfCheckGPT (NLI + BERTScore Hallucination)"
   - Parallel flow branches into a central node: "SEMANTIC OVERLAP DETECTOR (Noisy-OR Compounding)".

3. RIGHT-CENTER SECTION - "ADAPTIVE CONFORMAL POLICY GATE":
   - Hexagonal or diamond decision core labelled "ADAPTIVE CONFORMAL INFERENCE (ACI)".
   - Inputs: "Calibrated Quantiles (tau_low, tau_high)", "Session Drift Tracker", "Use-Case Policies (Standard / Medical / Creative)".
   - 5 Distinct Outgoing Routing Paths with glowing status chips:
     * Route 1: "TIER 1: ALLOW" (Lime Green #C8F45A) -> "Direct Output Release"
     * Route 2: "TIER 2: MODIFY" (Cyan Blue #38BDF8) -> "Surgical In-Place Span Repair"
     * Route 3: "TIER 3: REGENERATE" (Purple #A78BFA) -> "Checkpoint-Backtrack Prefix Resampling"
     * Route 4: "TIER 4: HUMAN" (Amber Orange #F59E0B) -> "Human Review Escalation Queue"
     * Route 5: "TIER 5: BLOCK" (Coral Red #EF4444) -> "Fail-Safe Safety Halt"

4. BOTTOM SECTION - "DUAL-PLANE AGENT ACTION GATE & AUDIT LEDGER":
   - Lower Left Box: "ACTION GATE (SPEC 14)" -> "Separation of Linguistic Text vs Destructive Tool Calls".
   - Lower Right Box: "AUDIT & OBSERVABILITY LEDGER" -> "Immutable Structured JSONL / PostgreSQL Telemetry".

Exact Spelling & Label Requirements (Zero Spelling Errors):
"CONTROLPLANE-AI", "ENTERPRISE GENAI RISK ORCHESTRATION ENGINE", "INGESTION LAYER", "ASYNC PROXY", "PARALLEL RISK ENGINE", "PRESIDIO HYBRID", "SELFCHECKGPT", "SEMANTIC OVERLAP", "NOISY-OR AGGREGATION", "ADAPTIVE CONFORMAL INFERENCE", "ALLOW", "MODIFY", "REGENERATE", "HUMAN REVIEW", "BLOCK", "ACTION GATE", "AUDIT LEDGER".
```

---

## 5. Architectural Verification & Compliance Matrix

| Architectural Goal | Theoretical Mechanism | Runtime Implementation | Verification Spec |
| :--- | :--- | :--- | :--- |
| **Hallucination Detection** | Stochastic Sample Inconsistency (NLI & BERTScore) | `src/checkers/performance_checker.py` | SPEC 01 / SPEC 09 |
| **Regional PII Compliance** | Microsoft Presidio + Custom Indian Entity Patterns | `src/checkers/pii_checker.py` | SPEC 02 / Indian PII |
| **Bounded Error Rate** | Split Conformal Quantiles ($1 - \alpha = 95\%$) | `src/policy/control_policy.py` | SPEC 03 |
| **Real-time Latency Budget** | Circuit Breaker & Adaptive Degradation | `src/engine/risk_engine.py` | SPEC 11 |
| **Probabilistic Compounding**| Noisy-OR Span Intersection Formula | `src/engine/risk_engine.py` | SPEC 12 |
| **Dynamic Drift Tracking** | Adaptive Conformal Inference (ACI) | `src/policy/adaptive_calibration.py` | SPEC 13 |
| **Tool Execution Safety** | Dual-Plane Text vs Action Gate Isolation | `src/agent/action_gate.py` | SPEC 14 |
| **Auditability & Observability**| Structured JSONL & Conformal Coverage Telemetry | `src/audit/audit_logger.py` | SPEC 16 / Dashboard |
