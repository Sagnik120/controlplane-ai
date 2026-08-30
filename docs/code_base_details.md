# ControlPlane-AI -- Codebase Details

## 1. Core Modules

| File | Role | Important behavior / functions | Relevant for testing? |
|------|------|--------------------------------|-----------------------|
| `src/api/main.py` | FastAPI app | Mounts API and static UI (`src/ui`). | Low |
| `src/api/routes.py` | API endpoints | `POST /api/chat`, `/api/policies`, `/api/metrics` | High (Entry) |
| `src/api/dependencies.py` | Singletons | Sets `GeminiAdapter(gemini-3.6-flash)` or `MockAdapter` based on `.env`. Loads `POLICIES`. | High (Mocks/Auth) |
| `src/adapters/gemini_adapter.py` | Gemini integration | Uses `google-genai` SDK. | High |
| `src/adapters/mock_adapter.py` | Test adapter | Deterministic keyword-based responses (bias, unsafe, pii, hallucination). | High |
| `src/orchestrator/pipeline.py` | Central coordinator | `process_request_async()`. **BUG:** Steps 5-10 (eval, policy, repair) are dead code in `except` block on success path. | Critical |
| `src/engine/risk_engine.py` | Async dispatcher | `evaluate_response_async()` runs checkers in ThreadPoolExecutor. | High |
| `src/checkers/performance_checker.py`| Hallucination check | Heuristic Tier-0. SelfCheckGPT Tier-1. | High |
| `src/checkers/safety_checker.py` | Safety check | Keyword Tier-0. Gemini LLM-judge Tier-1. | High |
| `src/checkers/bias_checker.py` | Bias check | Keyword Tier-0. Gemini LLM-judge Tier-1. | High |
| `src/checkers/pii_checker.py` | PII check | Regex + Presidio + piiranha NER. | High |
| `src/policy/control_policy.py` | Decision making | Compares scores to ACI thresholds. Maps ALLOW/MODIFY/REGEN/HUMAN/BLOCK. | High |
| `src/repair/span_repair.py` | Span repair | Presidio anonymizer for PII. LLM micro-prompt (`temp=0.2`) for others. Brittle `.replace()`. | High |
| `src/regenerate/checkpoint_backtrack.py` | Regeneration | Checkpoint commit + adapter continuation. | High |
| `src/session/session_state.py` | Session tracking | Tracks drift/PII. In-memory. UI doesn't preserve IDs. | Medium |
| `src/agent/action_gate.py` | Tool action gate | SPEC 14: semantic overlap of tools vs risks. | Medium |
| `src/ui/script.js` | UI logic | Fetch logic, DOM updates. | Low |
| `configs/use_case_policies.yaml` | Policy params | Defines `tau_low`, `tau_high` base values per dimension. | High |
| `tests/test_end_to_end_pipeline.py`| E2E test | Validates 6 primary paths via MockAdapter. | High |
| `scripts/live_gemini_smoke.py` | E2E Gemini check | Basic connectivity/success check for real adapter. | High |

## 2. Key Architecture Details

- **Adapter Factory:** Determined entirely by the presence of `GEMINI_API_KEY` in `.env` at startup.
- **Pipeline Dead-Code Bug:** A known bug in `pipeline.py` causes all successful Gemini completions to hit an exception handler and return `BLOCK`. Testing real Gemini requires fixing this first, otherwise rely on `MockAdapter`.
- **UI:** No separate frontend server (FastAPI serves static files). The UI does not persist `session_id`, meaning multi-turn tracking breaks.
- **Audit Logs:** Written as JSONL appends in `data/`. `metrics.html` relies on a pre-generated `metrics_summary.json` (no live aggregation).
