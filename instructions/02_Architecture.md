# 02_Architecture.md — System Architecture

## STATUS: AUTHORITATIVE. This defines HOW the PRD gets built. Follow structure exactly.

---

## 1. High-Level Data Flow

```
[Client / Dashboard UI]
        |
        v
[API Layer: POST /generate]  (FastAPI)
        |
        v
[ControlPlane Orchestrator: guarded_call()]
        |
        |--> [Initial Router]  -> selects model tier (stub is acceptable: simple/moderate/complex heuristic)
        |
        v
[LLM Adapter Interface] --> one of: GeminiAdapter | MockAdapter | (optional) OpenAIAdapter
        |
        v
[Streaming Buffer]  -- collects small windows of generated text
        |
        v
   +---------------------------+---------------------------+
   |                           |                           |
[Performance Checker]  [Responsibility Checkers]     [Cost Monitor]
                        (Safety, Bias, PII - run
                         in parallel, async)
   |                           |                           |
   +---------------------------+---------------------------+
                            |
                            v
                     [Risk Engine]
                (combines into RiskProfile object,
                 flags overlapping risk categories)
                            |
                            v
              [Use-Case Policy Config Loader]
           (loads thresholds for the active use_case)
                            |
                            v
                     [Control Policy]
        (compares RiskProfile against thresholds,
         returns Decision: ALLOW/MODIFY/REGENERATE/HUMAN
         + reason string)
                            |
                            v
                     [Audit Logger]
              (appends full record to audit_log.jsonl
               or SQLite table)
                            |
                            v
              [Response returned to Client/UI]
```

## 2. Folder Structure (see 08_Folder_Structure.md for the full canonical structure)

High-level only here:
```
controlplane-ai/
├── instructions/        # all planning .md files (this folder)
├── src/
│   ├── adapters/         # LLM provider adapters (Gemini, Mock, OpenAI)
│   ├── checkers/         # performance, safety, bias, pii checkers
│   ├── cost/             # cost monitor
│   ├── risk_engine/      # combines checker outputs
│   ├── policy/           # use-case configs + control policy logic
│   ├── audit/            # audit logger + log reader
│   ├── api/              # FastAPI routes
│   └── dashboard/         # frontend (simple HTML/JS or React, kept minimal)
├── tests/                # see 07_Test.md, mirrors src/ structure
├── docs/                 # progress.md and any generated reports
├── configs/              # use_case_policies.yaml, model_registry.yaml
├── .env                  # API keys, NEVER committed, NEVER read by the agent directly in chat
├── .gitignore
└── README.md
```

## 3. Tech Stack (fixed — do not substitute without asking first)

- **Language**: Python 3.11+
- **Backend framework**: FastAPI (async support needed for parallel checkers)
- **Server**: uvicorn
- **Frontend**: plain HTML/CSS/JS (no heavy framework) OR a minimal React app if Antigravity strongly
  prefers it — but must stay simple, no unnecessary component libraries.
- **Storage**: JSON Lines file (`audit_log.jsonl`) for the audit log. SQLite is an acceptable upgrade
  IF it doesn't cost significant extra time. No Postgres/MySQL/cloud DB.
- **Config format**: YAML for use-case policies and model registry (`configs/*.yaml`)
- **LLM SDKs**: `google-generativeai` (Gemini) as the primary real adapter. Additional providers are
  optional stretch goals only.
- **Testing**: `pytest` for automated diagnostic scripts (see 07_Test.md).
- **Env management**: `python-dotenv` to load `.env`, never hardcode keys anywhere in source.

## 4. Key Design Patterns (must be used)

1. **Adapter Pattern for LLMs** — a single `BaseLLMAdapter` abstract class with `generate_stream(prompt) -> Iterator[str]`.
   Every provider implements this. ControlPlane orchestrator code must NEVER import a provider SDK
   directly outside of its adapter file. This is what proves the "works on any LLM" claim.
2. **Strategy Pattern for Policy Config** — the Control Policy loads a strategy (thresholds) by
   `use_case` key at request time. Do not hardcode thresholds inside the Control Policy function body.
3. **Pipeline/Chain pattern for Checkers** — checkers run independently (ideally concurrently via
   `asyncio.gather`) and each returns a standard `CheckerResult` object:
   ```python
   {
     "checker_name": "pii",
     "risk_score": 0.76,
     "flagged_span": "John Doe's SSN is 123-45-6789",
     "overlaps_with": ["performance"],   # populated by Risk Engine, not the checker itself
     "explanation": "Detected SSN-pattern entity not present in source context"
   }
   ```
4. **Structured Decision Object** — Control Policy always returns:
   ```python
   {
     "decision": "MODIFY",
     "reason": "pii_risk (0.76) exceeded threshold (0.40) for use_case=customer_support_chatbot",
     "risk_profile": {...},
     "policy_applied": "customer_support_chatbot_v1"
   }
   ```

## 5. Use-Case Policy Config (concrete file, place at `configs/use_case_policies.yaml`)

```yaml
use_cases:
  customer_support_chatbot:
    latency_budget_ms: 800
    thresholds:
      performance_risk: 0.60
      safety_risk: 0.30
      bias_risk: 0.50
      pii_risk: 0.40
      cost_risk: 0.70
    human_escalation_threshold: 0.85

  internal_knowledge_assistant:
    latency_budget_ms: 3000
    thresholds:
      performance_risk: 0.40
      safety_risk: 0.20
      bias_risk: 0.35
      pii_risk: 0.25
      cost_risk: 0.85
    human_escalation_threshold: 0.65

  decision_support_regulated:
    latency_budget_ms: 5000
    thresholds:
      performance_risk: 0.25
      safety_risk: 0.10
      bias_risk: 0.20
      pii_risk: 0.10
      cost_risk: 0.90
    human_escalation_threshold: 0.40
```
## 4B. Note on Internal Detection Logic (post-Phase-9)

The Checkers, Risk Engine aggregation, and Control Policy thresholds described above define the
*shape* of the pipeline (interfaces, data contracts, folder ownership) — this remains fixed. Their
*internal detection method* (e.g. regex vs. NLI-based hallucination detection) is upgraded
incrementally per `instructions/specs/SPEC_TRACKER.md` and is expected to diverge from a literal
reading of "heuristic" language elsewhere in this doc. When in doubt, the active spec file wins for
internal method; this file wins for interfaces/data contracts/folder structure.

## 6. Audit Log Record Schema (place logic at `src/audit/logger.py`)

```json
{
  "timestamp": "ISO-8601 string",
  "request_id": "uuid",
  "use_case": "string",
  "llm_provider": "string",
  "prompt_excerpt": "string, truncated to 200 chars",
  "risk_profile": { "performance": 0.0, "safety": 0.0, "bias": 0.0, "pii": 0.0, "cost": 0.0 },
  "overlaps_detected": ["performance+pii"],
  "policy_applied": "string",
  "decision": "ALLOW|MODIFY|REGENERATE|HUMAN",
  "reason": "string",
  "latency_ms": 0
}
```

## 7. What "Model-Agnostic" Must Concretely Demonstrate

The SAME orchestrator code, unmodified, must run successfully with `llm_provider="gemini"` and
`llm_provider="mock"` (and a third real provider if time allows), selected via a config value or
dropdown — not via code changes. This is a required demo scenario, not optional polish.
