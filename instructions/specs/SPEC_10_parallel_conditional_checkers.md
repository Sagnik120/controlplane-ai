# SPEC_10 — Parallel + Conditional Checker Execution (Latency Fix)

**Status:** Draft for implementation
**Owns:** `src/engine/risk_engine.py`, `src/checkers/base.py`, `src/checkers/performance_checker.py`, `src/checkers/pii_checker.py`, `src/checkers/safety_bias_checker.py`, `src/orchestrator/pipeline.py`, `use_case_policies.yaml`
**Solves:** Upgrade #2 — "parallelize the 3 checkers + stop running SelfCheckGPT unconditionally." Per the codebase doc, `performance_checker.py` already has a Tier-0 gate in front of SelfCheckGPT — this spec (a) generalizes that gating pattern to the other two checkers, and (b) fixes the part not yet done: the three checkers still run **sequentially** inside `risk_engine.py`.
**Relationship to SPEC_09:** SPEC_09's regenerate loop calls the risk engine again to re-verify a resampled span. If the risk engine itself is slow, every REGENERATE attempt pays that cost twice. This spec is upstream of SPEC_09's latency in practice — fix this first.

---

## 1. What the codebase doc tells us is actually happening today

Reading `risk_engine.py`'s description literally: it "iterates through the list of registered checkers sequentially." Three checkers means **three sequential round-trips** (one local-model inference each, in the case of PII/safety, or a multi-sample LLM call in the case of performance) before a single risk decision is made. Even with the Tier-0 gate already reducing how often SelfCheckGPT itself fires, the checkers still queue up one after another. There are two separate problems bundled in Upgrade #2's wording, and it's important to treat them as two separate fixes because they have different root causes:

1. **Sequential execution** — a scheduling/concurrency problem. Fix: run checkers concurrently.
2. **Unconditional heavy check** — an architecture problem, already half-solved for the performance checker. Fix: apply the same cascade principle everywhere a heavy model exists, not just SelfCheckGPT.

---

## 2. Research synthesis

### 2.1 Parallel detector architecture — direct precedent
- **OneShield** (2026), a published next-generation LLM guardrails architecture, runs all its detectors (PII, safety, jailbreak, etc.) **in parallel**, and its core latency claim is exactly the property you want: *"the total time for detection is no longer than the individual longest-running detector."* Their measured PII extractor response time was sub-millisecond per typical prompt precisely because it's not waiting behind other detectors in a queue. This is the architectural target for `risk_engine.py`: replace "sum of all checker latencies" with "max of all checker latencies." [arXiv:2507.21170]
- **NVIDIA NeMo Guardrails "Parallel Rails"** is a shipped feature with the same idea (`parallel: true` in config), explicitly recommended for "I/O-bound rails such as external API calls" and "independent rails without shared state dependencies" — and explicitly *not* recommended when rails mutate shared state, because of race conditions. This caveat matters directly for your pipeline: `SessionRiskState` is shared, mutable state that multiple checkers may read/write. [docs.nvidia.com/nemo/guardrails — parallel-rails]
- **The "Adaptive Abstention System"** (2026) fuses both problems you're solving at once: it runs **five parallel detectors**, then combines them through a **hierarchical cascade** that reserves deep analysis for ambiguous/high-risk cases only. This is effectively a direct blueprint — parallel first pass across all detector types, cascade escalation within each. [arXiv:2602.15391]

### 2.2 Cascade / cheap-first-pass literature (generalizing your existing Tier-0 pattern)
- **FrugalGPT** (Stanford, 2023) formalized the "LLM cascade" idea generally: route to the cheapest model that's likely to be good enough, escalate only when its own confidence is low, reporting up to 98% cost reduction with matched accuracy. Your Tier-0/Tier-1 split on the performance checker is a two-stage instance of this idea. [arXiv:2305.05176]
- **Cost-Saving LLM Cascades with Early Abstention** (Caltech, 2025) refines this further: rather than a single deterministic threshold, cascades that allow the cheap stage to *abstain* (defer to the expensive stage) when genuinely uncertain — rather than forcing a binary pass/fail on the cheap signal alone — trade a small increase in deferral rate for a real reduction in error rate. This is the right framing for tuning your `uncertain_threshold` band: don't tune it to minimize Tier-1 calls at all costs, tune it to minimize *missed* escalations, then measure Tier-1 call rate as the resulting metric. [arXiv:2502.09054]
- **Semantic Agreement Cascades** (2025) is worth citing for the "why cheap-first works at all" justification: their cascades matched target-model quality using only 40% of the compute budget and cut latency 39–61% versus always calling the expensive model — this is the kind of number you can put in front of a judge to justify the architecture, not just "we made it faster." [arXiv:2509.21837]

**Generalizing to PII and safety/bias checkers**, which don't currently have a Tier-0 gate per the codebase doc:
- **PII checker Tier-0**: Presidio itself already ships fast, cheap **regex/pattern recognizers** (phone numbers, emails, SSN-shaped strings, credit-card-shaped strings) that run in microseconds, before you ever need the heavier `iiiorg/piiranha-v1-detect-personal-information` NER pass. Today's implementation apparently runs the full NER pipeline unconditionally. Fix: run Presidio's built-in pattern recognizers first (cheap); only invoke the NER model when (a) a pattern recognizer already found something and needs corroboration/expansion, or (b) the text contains entity-shaped tokens (capitalized runs, digit sequences) that regex alone can't classify. This mirrors the same cheap→expensive structure as the performance checker's Tier-0/Tier-1 split, just with a rule-based gate instead of a logit-based one.
- **Safety/bias checker**: `unitary/toxic-bert` is already a small DistilBERT-class model, cheap relative to SelfCheckGPT's multi-sample NLI/BERTScore pipeline — it likely does not need its own Tier-0 gate for latency reasons. Where a cascade *does* help here is the **bias** check specifically: your original ControlPlane.ai design doc already notes "bias often requires more context [so] it can be evaluated less frequently than simple safety checks" — implement that literally as a sampling/frequency gate (e.g., run the full bias pass every Nth window or when session-level drift is already elevated) rather than a per-window cheap/expensive split.

### 2.3 The concurrency implementation detail almost everyone gets wrong
This is the single most important technical correction to make before writing code: **`asyncio.gather` alone does not parallelize your three checkers.**

`asyncio.gather` gives you concurrency for **I/O-bound** work — waiting on network calls (e.g., the Gemini adapter's API round-trip for SelfCheckGPT's extra samples). But Presidio, the PII NER pipeline, and `toxic-bert` are **local model inference** running on CPU/GPU — that's **CPU-bound** work. In standard CPython, CPU-bound work holds the GIL, so if you call these synchronously inside `async def` functions and just wrap them in `asyncio.gather`, they will still execute one after another on the same thread — `asyncio.gather` will *appear* to work (no errors) but deliver **zero actual parallelism** for these three checkers, which is exactly the trap Upgrade #2 would fall into if implemented literally as written. Community documentation on this is consistent: asyncio's high-level APIs "are focused on I/O-bound, not CPU-bound operations," and CPU-bound work needs to go through `loop.run_in_executor()` with a `ThreadPoolExecutor` (releases GIL during native model ops, works for most HF/PyTorch inference since the actual tensor ops release the GIL) or a `ProcessPoolExecutor` (true parallelism, higher overhead, needed if a library doesn't release the GIL during compute). [pypi.org/project/asynccpu; medium.com "async.io and python core utilization"]

**Correct pattern:**
```python
performance_result = loop.run_in_executor(thread_pool, performance_checker.check_sync, window)
pii_result = loop.run_in_executor(thread_pool, pii_checker.check_sync, window)
safety_result = loop.run_in_executor(thread_pool, safety_checker.check_sync, window)
results = await asyncio.gather(performance_result, pii_result, safety_result)
```
The Gemini adapter calls *inside* `performance_checker.check_sync` (the extra stochastic samples for SelfCheckGPT) are the one piece that's genuinely I/O-bound and should be `await`-ed natively with `asyncio.gather` internally, not thread-pooled — mixing the two correctly (native async for the network leg, executor pool for the local-model leg) is what actually gets you both wins.

---

## 3. Proposed architecture: parallel dispatch + per-checker cascade

```
                 window_text, context, logprobs
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                     ▼
 PerformanceChecker     PIIChecker           SafetyBiasChecker
   Tier-0: logit         Tier-0: Presidio      (usually runs
   entropy/margin         pattern regex          directly —
   (free)                 (µs, regex)             already cheap)
        │ uncertain?           │ hit?                   │
        ▼                      ▼                        │
   Tier-1: SelfCheckGPT   Tier-1: NER model              │
   (NLI+BERTScore,         (piiranha)                    │
    multi-sample,                                        │
    I/O-bound → native                                   │
    asyncio.gather                                       │
    internally)                                          │
        │                      │                         │
        └──────────┬───────────┴─────────────────────────┘
                    ▼
        asyncio.gather(perf_future, pii_future, safety_future)
        each future = loop.run_in_executor(thread_pool, checker.run, window)
                    ▼
        total latency ≈ max(perf, pii, safety), not sum
                    ▼
              RiskEngine.combine() → FinalRiskReport
```

### 3.1 Standardize the checker interface (`src/checkers/base.py`)
```python
class BaseChecker(ABC):
    def run(self, window_text: str, context: dict) -> CheckerResult:
        """Synchronous entrypoint — called inside a thread/process pool."""
        tier0 = self.tier0_gate(window_text, context)
        if not tier0.needs_tier1:
            return CheckerResult(risk=tier0.risk, tier=0, ran_heavy=False,
                                  latency_ms=tier0.latency_ms)
        tier1 = self.tier1_check(window_text, context)
        return CheckerResult(risk=tier1.risk, tier=1, ran_heavy=True,
                              latency_ms=tier0.latency_ms + tier1.latency_ms)

    @abstractmethod
    def tier0_gate(self, window_text, context) -> Tier0Result: ...

    @abstractmethod
    def tier1_check(self, window_text, context) -> Tier1Result: ...
```
Every checker (performance, PII, safety/bias) implements the same two-method contract. Where a checker's "heavy" model is already cheap (safety/bias per §2.2), `tier0_gate` can simply always return `needs_tier1=True` — the interface stays uniform even when a given checker chooses not to exploit the cascade, which keeps `risk_engine.py` simple and keeps the door open to add a gate later without changing the call site.

### 3.2 Rewrite `src/engine/risk_engine.py` dispatch
```python
class RiskEngine:
    def __init__(self, checkers: list[BaseChecker], max_workers: int = 3):
        self.checkers = checkers
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    async def evaluate(self, window_text: str, context: dict) -> FinalRiskReport:
        loop = asyncio.get_running_loop()
        futures = [
            loop.run_in_executor(self.thread_pool, checker.run, window_text, context)
            for checker in self.checkers
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)
        return self._combine(results, context)
```
Note `return_exceptions=True` — see §3.4 (error handling), this is also explicitly called out in your own Upgrade #14 checklist ("what happens if PII checker itself crashes?") and is the natural place to fix it while you're already rewriting this function.

### 3.3 Session-state race safety (the NeMo caveat, §2.1)
`SessionRiskState` (semantic drift, cumulative PII exposure) is read by more than one checker and written after the combined result is known. Per NeMo's explicit warning, do **not** let individual checkers mutate `SessionRiskState` directly inside their parallel `run()` calls — race conditions there would silently corrupt drift tracking. Keep the contract strictly read-only inside `checker.run()`; only `RiskEngine._combine()` (which runs after `asyncio.gather` completes, back on the single event loop thread) is allowed to write session-state updates. This is a one-line discipline rule but worth stating explicitly in code review / PR description since it's the kind of bug that only shows up under real concurrent load, not in a demo.

### 3.4 Checker-failure isolation (closes an Upgrade #14 gap for free)
Because `asyncio.gather(..., return_exceptions=True)` returns exceptions as values instead of raising, a crashed PII checker (model OOM, bad input, etc.) no longer takes down the whole risk evaluation. `_combine()` should treat a checker exception as **"unknown risk, escalate to HUMAN"** rather than either (a) silently treating it as zero risk (dangerous — a crashed PII checker is not the same as "no PII found") or (b) crashing the whole request. This turns a previously-unhandled failure mode into a defined, testable behavior.

### 3.5 Config additions to `use_case_policies.yaml`
Extend the per-use-case gating you already introduced for the performance checker (SPEC_09 §3.5) to the PII checker's regex-vs-NER gate:
```yaml
customer_facing_chat:
  pii_tier0_mode: "pattern_only_unless_hit"   # cheap regex gates the NER pass
  bias_check_frequency: "every_4th_window"     # sampled, not every window

internal_decision_support:
  pii_tier0_mode: "always_full_ner"            # higher scrutiny, matches risk tolerance
  bias_check_frequency: "every_window"
```

---

## 4. What to measure to prove this actually fixed latency

Directly reusable by Upgrade #8's dashboard:
- **p50/p95/p99 time-to-decision per window**, before vs. after — the headline number.
- **Tier-1 invocation rate per checker type** (performance / PII / bias) — should drop sharply for performance and PII, roughly flat for safety/bias by design.
- **Wall-clock risk-engine latency vs. max(individual checker latency)** — should converge close to 1.0 once parallel dispatch is correct; if it's still close to the *sum*, the executor-pool wiring in §2.3 wasn't done correctly and checkers are still serializing under the GIL.
- **Checker exception rate and HUMAN-escalation-due-to-checker-failure count** — from §3.4, gives you a concrete answer to "what happens if a checker crashes" for a judge.

---

## 5. Testing checklist

- Unit test: `tier0_gate` correctly skips `tier1_check` on a low-risk PII window (no entity-shaped tokens) and correctly triggers it on one containing an SSN-shaped string.
- Unit test: `RiskEngine.evaluate` wall-clock time on three checkers with artificially staggered sleep times (e.g., 100ms/200ms/300ms) is close to 300ms, not 600ms — this is the regression test that would have caught a naive `asyncio.gather`-without-executor-pool implementation.
- Unit test: a checker raising an exception inside `run()` results in `FinalRiskReport` marking that dimension as unknown and routes to HUMAN, not a silent pass.
- Integration test: concurrent requests against the same session ID don't corrupt `SessionRiskState` (a basic stress test with N concurrent turns on one session, assert final drift value is deterministic/consistent, per §3.3's write-after-gather discipline).
- Load test: measure actual thread-pool contention at your expected concurrent-request volume — `ThreadPoolExecutor(max_workers=3)` per request instance means N concurrent user requests want `3*N` threads; size the shared pool deliberately rather than creating one per request (this is a follow-on scaling note worth a comment in the PR, ties into Upgrade #11's Redis/scaling discussion).

---

## 6. Reference list

- OneShield — the Next Generation of LLM Guardrails, 2026 — arXiv:2507.21170 (parallel-detector latency = max, not sum)
- NVIDIA NeMo Guardrails, Parallel Rails documentation — docs.nvidia.com/nemo/guardrails (parallel execution guidance + shared-state race caveat)
- "Improving LLM Reliability through Hybrid Abstention and Adaptive Detection" (Adaptive Abstention System, five parallel detectors + hierarchical cascade), 2026 — arXiv:2602.15391
- Chen, Zaharia, Zou, "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance," Stanford, 2023 — arXiv:2305.05176
- Zellinger, Liu, Thomson, "Cost-Saving LLM Cascades with Early Abstention," Caltech, 2025 — arXiv:2502.09054
- "Semantic Agreement Enables Efficient Open-Ended LLM Cascades," 2025 — arXiv:2509.21837
- `asynccpu` (PyPI) and general Python asyncio CPU-bound-vs-I/O-bound guidance — pypi.org/project/asynccpu; background on why `run_in_executor` (thread/process pool) is required for local model inference under asyncio.
