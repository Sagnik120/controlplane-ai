# SPEC_15 — Full Async Orchestration via Structured Concurrency

**Status:** Draft for implementation
**Owns:** `src/adapters/base_adapter.py`, `src/adapters/gemini_adapter.py`, `src/orchestrator/pipeline.py`, plus the call boundaries in `src/engine/risk_engine.py` (SPEC_10), `src/regenerate/checkpoint_backtrack.py` (SPEC_09), `src/agent/action_gate.py` (SPEC_14), `src/feedback/feedback_consumer.py` (SPEC_13)
**Solves:** Upgrade #7 — "async the whole pipeline — adapters, pipeline.py are fully synchronous; move to asyncio so checkers, retries, and repairs don't block each other. Needed to make #2 real, not cosmetic."
**Why this is the correct spec to close last, not first:** the codebase doc's Harsh Reality #3 is consistent across every prior spec: SPEC_10 made `RiskEngine` internally parallel, SPEC_11 added circuit-breaker timeouts, SPEC_13 added an async feedback consumer — but `pipeline.py`'s **outer loop**, and the adapter underneath it, are still synchronous. Every one of those specs built a correctly-async *component*; this spec is what stitches them into one coherent async **request lifecycle**, which is the only way any of the individual fixes stop being local optimizations and start being a real systemic latency fix.

---

## 1. What "async the whole pipeline" actually requires, precisely

It is tempting to read this upgrade as "add `async def` in front of the existing functions." That would be a mistake, and it's worth stating why explicitly, because it's the exact same trap SPEC_10 flagged for the checkers, now at the orchestration level: **wrapping synchronous, blocking code in `async def` without either making the underlying I/O genuinely non-blocking or offloading CPU-bound work to an executor produces code that looks async and provides zero concurrency benefit.** A known, well-documented asyncio anti-pattern is exactly this: blocking calls inside coroutines silently serialize everything behind them, and another is spawning tasks without properly tracking/awaiting them, which lets them be silently garbage-collected mid-flight. Both failure modes are realistic risks in a naive version of this rewrite, given how much surface area `pipeline.py` now touches (adapter, risk engine, session state, control policy, span repair, regeneration engine, action gate, audit logger — SPECs 09 through 14 all hang off this one loop).

---

## 2. Research synthesis

### 2.1 Structured concurrency — the architectural backbone, not an implementation detail
The concept that should govern this entire rewrite is **structured concurrency**: every task spawned during a request's lifetime lives inside a bounded scope tied to that request, so when the scope exits — normally, by cancellation, or by exception — every child task is guaranteed to be either completed or cleanly cancelled. No orphaned tasks, no silent leaks. This idea, popularized by Nathaniel J. Smith's Trio library and its "nursery" concept, was added to Python's standard library in 3.11 as `asyncio.TaskGroup` (paired with `asyncio.timeout()` and `PEP 654` exception groups for handling multiple simultaneous task failures cleanly). The core guarantee: exiting a `TaskGroup`'s `async with` block automatically awaits every child task — no manual `gather()`/`join()` bookkeeping — and if any child raises, the others are cancelled and all exceptions are collected into a single `ExceptionGroup` rather than losing all but the first. [Python 3.11 `asyncio.TaskGroup`; PEP 654; structured-concurrency background from Trio/`quattro`, a backport implementing the same nursery pattern for pre-3.11 Python]

**Why this is the right primitive for your specific system, not a generic best practice:** SPEC_11's circuit breaker already needs to cancel in-flight checker tasks when a latency budget is exceeded (`asyncio.wait_for`/`asyncio.timeout`), and SPEC_14's action gate and SPEC_09's regenerate loop both spawn nested async work mid-request. Without a structured scope, a circuit-breaker timeout firing partway through a REGENERATE-inside-MODIFY-inside-RiskEngine call stack risks leaving orphaned tasks running in the background (silently consuming your adapter's rate limit or GPU time for a response nobody will ever see) rather than being cleanly torn down. `TaskGroup` gives you that cleanup for free at the language level, instead of hand-rolled cancellation bookkeeping scattered across five files.

### 2.2 The buffer-then-release design in your original ControlPlane.ai doc is a producer/consumer problem — make it one literally
Your own original architecture doc describes the core mechanism as: *"LLM → small output buffer → User... This allows ControlPlane to inspect the emerging response during generation, rather than waiting for the entire response."* Today, per the codebase doc, this is implemented as a synchronous blocking loop — the adapter blocks until a chunk is ready, the risk engine then blocks evaluating it, then the next chunk is requested. That is *sequential*, not *streaming*, even though the data model (buffer, window) is right.

The correct implementation of "buffer + inspect during generation" is a genuine **producer/consumer pipeline** using `asyncio.Queue`: one task (the adapter, producing tokens) writes windows into the queue as they're generated; a separate task (the risk engine, per SPEC_10's cascade) consumes windows from the queue and evaluates them, running concurrently with the *next* window's generation rather than waiting for it to be requested. This is the standard asyncio pattern for exactly this kind of streaming-with-inspection scenario — a bounded `asyncio.Queue` also gives you free backpressure (if the risk engine falls behind because SPEC_10's Tier-1 checks are running, the queue fills and the producer naturally slows down, rather than either unboundedly buffering in memory or dropping windows).

NVIDIA NeMo Guardrails' own `StreamingHandler` is a directly relevant existing implementation of this exact shape worth using as a design reference (already cited in SPEC_09 for its chunking config): it implements Python's `AsyncIterator` protocol so a caller can `async for chunk in streaming_handler`, with internal buffering, fully decoupling how fast tokens are produced from how fast a consumer processes them. Rewriting `gemini_adapter.py`'s `generate_stream()` to this shape — an `AsyncIterator`/`asyncio.Queue`-backed producer instead of a plain blocking generator — is the concrete unit of work this spec asks for at the adapter layer. [docs.nvidia.com/nemo/guardrails/streaming]

### 2.3 Be honest about what's actually I/O-bound at the adapter boundary
Per SPEC_10 §2.3's finding (still the correct lesson here, just applied one layer up): only work that's genuinely **I/O-bound** — waiting on the network — benefits from native `async`/`await`. If the underlying `google-genai` Python SDK's client is itself synchronous under the hood (many LLM provider SDKs historically shipped sync-only clients before adding async variants), then simply calling it inside an `async def` function does **not** make it non-blocking — it will still block the event loop for the duration of the call, exactly like calling a synchronous HF model inference function inside `async def` blocks the event loop in SPEC_10's checkers. Two honest options, and this spec should pick one explicitly rather than let it be discovered late:
1. **If `google-genai` ships a native async client** (check the SDK version in use — many providers now do), use it directly; this is the "real" fix.
2. **If it doesn't**, wrap the synchronous call in `loop.run_in_executor()` exactly as SPEC_10 did for the local checker models — this still gets you real concurrency (the event loop is free to run other tasks — other users' requests, other checkers — while this call is in flight on a worker thread), it's just implemented via executor-offload rather than native async I/O. Document which case applies in the PR description; don't let the adapter's docstring claim "fully async" if it's actually executor-wrapped, for the same honesty-with-judges reason SPEC_13 flagged for the simplified ACI step size.

### 2.4 The real payoff is cross-request concurrency, not single-request speed — say this explicitly to judges
This is the single most important framing point for defending this spec to a judge, because it's easy to under-sell: **making one request's own pipeline async does not, by itself, make that one request faster.** SPEC_09's REGENERATE loop is still a sequential diagnose→verify→resample chain; SPEC_10's parallel checkers already got you the within-request latency win. What full async orchestration actually buys you is **many simultaneous requests no longer serialize behind each other** — today, per the codebase doc, "a single user request blocks the entire Python thread for the duration of generation, checking, repairing, regenerating, and re-checking," meaning a second user's request cannot even *start* being processed until the first user's entire pipeline (including a REGENERATE loop, if triggered) finishes. After this spec, the event loop interleaves work across requests, so one user's expensive REGENERATE loop no longer stalls every other concurrent user. This is the concrete, measurable claim to put in front of judges — not "requests are faster," but "the system now serves concurrent traffic instead of one request at a time," which is the difference between a working demo and a system that would fall over the moment more than one judge tries it simultaneously.

---

## 3. Proposed architecture

### 3.1 Adapter layer — `AsyncIterator`-based streaming (§2.2/§2.3)
```python
class BaseAdapter(ABC):
    @abstractmethod
    async def generate_once(self, prompt: str, **kwargs) -> str: ...

    @abstractmethod
    def generate_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Returns an async iterator of token/chunk strings.
        Callers use `async for chunk in adapter.generate_stream(...)`."""
        ...
```
```python
class GeminiAdapter(BaseAdapter):
    async def generate_once(self, prompt: str, **kwargs) -> str:
        if self._client_is_native_async:               # §2.3 case 1
            response = await self._async_client.generate(...)
        else:                                            # §2.3 case 2
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self._executor, self._sync_client.generate, prompt, kwargs)
        return response.text

    async def generate_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=BUFFER_SIZE)  # §2.2 backpressure
        async def _produce():
            try:
                for chunk in self._sync_client.generate_stream(prompt, **kwargs):  # blocking iterator
                    await queue.put(chunk)      # executor-thread-safe via run_coroutine_threadsafe if needed
            finally:
                await queue.put(None)           # sentinel: stream complete
        producer_task = asyncio.create_task(_produce())   # tracked inside the request's TaskGroup, §3.2
        while (chunk := await queue.get()) is not None:
            yield chunk
        await producer_task   # propagate any exception from the producer
```

### 3.2 `pipeline.py` — one `TaskGroup`-scoped coroutine per request
```python
async def handle_request(request: IncomingRequest) -> FinalResponse:
    async with asyncio.TaskGroup() as tg:
        window_queue: asyncio.Queue = asyncio.Queue(maxsize=WINDOW_BUFFER_SIZE)

        generation_task = tg.create_task(
            _produce_windows(adapter, request, window_queue))          # §3.1's producer
        evaluation_task = tg.create_task(
            _consume_and_evaluate(risk_engine, window_queue, session_state, control_policy))
                                                                          # §2.2's consumer; internally
                                                                          # still uses SPEC_10's asyncio.gather
                                                                          # + executor pool across checkers
        # MODIFY / REGENERATE / action-gate calls happen INSIDE _consume_and_evaluate,
        # as nested awaits within the same TaskGroup scope — not separate top-level tasks —
        # so a circuit-breaker cancellation (SPEC_11) or client disconnect tears down the
        # whole in-flight chain cleanly, per §2.1's guarantee.

        audit_task = tg.create_task(_flush_audit_log(request, evaluation_task))
        # fire-and-forget-but-tracked: doesn't add latency to the user-facing response path,
        # but TaskGroup guarantees it completes (or is cancelled) before handle_request returns —
        # no dropped audit entries on process exit, per §2.1.

    return await evaluation_task_result(...)   # TaskGroup has already awaited everything by this point
```
This is the concrete shape that answers the upgrade literally: adapters are async (§3.1), checkers/retries/repairs run inside a shared, cancellable scope instead of blocking the whole thread (§3.2), and nothing about SPEC_09–14's internal logic needs to change — they're being *composed* correctly now, not rewritten.

### 3.3 Circuit breaker integration (ties SPEC_11 to real cancellation, not just timeout-and-ignore)
SPEC_11's `asyncio.wait_for`-based circuit breaker should be upgraded to `asyncio.timeout()` (the 3.11 structured-concurrency-friendly form) wrapping the `evaluation_task`'s work specifically — when it fires, per §2.1's guarantee, everything nested inside (in-flight Tier-1 checker calls, an in-progress REGENERATE diagnose/verify/resample chain) is actually cancelled, not just abandoned-but-still-running-in-the-background consuming resources for a response that's already been marked `under_verified` and returned.

### 3.4 Audit logger becomes async-safe (sets up, doesn't require, Upgrade #10's DB migration)
`_flush_audit_log` should be written against an async-compatible interface from the start (`await audit_logger.write(...)`), even if today's Upgrade #10 migration to SQLite/Postgres hasn't landed yet — using `aiosqlite` or `asyncpg` (the async drivers for those two specific databases) once it does, rather than a synchronous DB call inside an `async def` that would silently reintroduce the exact blocking-call anti-pattern this whole spec exists to fix. Note this explicitly in the PR so whoever implements Upgrade #10 doesn't accidentally wire in a sync driver.

---

## 4. Step-by-step implementation guide

1. **Confirm which case applies at the adapter boundary (§2.3)** — check whether the installed `google-genai` SDK version ships an async client. This single fact determines whether `GeminiAdapter` is "really" async or executor-wrapped; do this first since it affects §3.1's implementation, not just its docstring.
2. **Rewrite `base_adapter.py`/`gemini_adapter.py`** per §3.1 — `generate_once` as a proper `async def`, `generate_stream` as an `AsyncIterator` backed by an internal `asyncio.Queue` producer/consumer pair.
3. **Rewrite `pipeline.py`'s top-level request handler** as a single `TaskGroup`-scoped coroutine per §3.2, replacing the current synchronous sequential loop.
4. **Update SPEC_11's circuit breaker** to `asyncio.timeout()` wrapping the evaluation task specifically (§3.3), confirming cancellation actually propagates into nested REGENERATE/action-gate calls (this needs an explicit test — cancellation propagation bugs are exactly the kind of thing that looks fine in a quick demo and breaks under real concurrent load).
5. **Confirm `RiskEngine.evaluate` (SPEC_10), `RegenerationEngine.regenerate` (SPEC_09), and `ActionRiskChecker.run` (SPEC_14) are called via `await` from inside `_consume_and_evaluate`**, not spawned as separate untracked tasks — they should be nested *within* the evaluation task's scope, not siblings of it, so they inherit cancellation correctly per §2.1.
6. **Wire `_flush_audit_log`** per §3.4, using an async-safe write interface even ahead of Upgrade #10's DB migration.
7. **Confirm `FeedbackConsumer` (SPEC_13), already async, shares the same event loop cleanly** — it should run as a long-lived background task started once at process startup (not per-request, unlike everything else in this section), so this step is mostly a verification pass, not new code.

---

## 5. Testing checklist (this is where the real payoff gets proven, per §2.4)
- **Concurrent-request interleaving test**: fire N simultaneous requests, at least one of which triggers a REGENERATE loop (deliberately slow); assert the other N-1 requests complete without waiting for the slow one — this is the direct test of §2.4's actual claim, and the single most important test in this spec.
- **Cancellation propagation test**: trigger SPEC_11's circuit breaker mid-REGENERATE; assert the nested diagnose/verify/resample calls are actually cancelled (e.g., via a mock adapter that records whether it was awaited to completion or cancelled), not merely that the outer function returned early while the inner call kept running.
- **Backpressure test**: a slow consumer (risk engine mid-Tier-1) should cause the producer (adapter) to block on `queue.put()` rather than unboundedly buffering — assert queue size never exceeds `WINDOW_BUFFER_SIZE` under a deliberately slow-consumer test double.
- **Audit-completeness test**: even under a forced cancellation/exception mid-request, assert the audit task either completes or is explicitly and loggably cancelled — no silent drops (per §2.1/§3.4).
- **Regression test against SPEC_10's checker cascade**: confirm the existing parallel-dispatch-plus-executor-pool behavior inside `RiskEngine` still works correctly when called from within the new outer `TaskGroup` scope — nesting an executor-based `asyncio.gather` inside a `TaskGroup` is a reasonable pattern but worth an explicit regression test given how much machinery is now layered.

---

## 6. Metrics to prove this worked (extends the dashboard, Upgrade #8)
- **Concurrent request throughput** (requests/sec sustained with N simultaneous clients) — before this spec, expect throughput to collapse toward ~1 request's worth of work regardless of N, since everything serializes on the single blocking thread; after, expect near-linear scaling up to the point where CPU/GPU-bound checker work (still real work, still bounded by SPEC_10's thread-pool size) becomes the limiting factor, not orchestration blocking.
- **p95/p99 latency under concurrent load specifically** (distinct from SPEC_10/11's single-request latency metrics) — this is the number that most directly demonstrates this spec's payoff and should be presented separately from the earlier specs' latency wins, per §2.4's framing.
- **Cancellation success rate** — of circuit-breaker-triggered cancellations, what fraction actually stopped in-flight work versus let it run to completion in the background (should be ~100% after this spec; worth showing the before/after if you can instrument the "old" synchronous version for comparison).

---

## 7. Reference list

- Python 3.11 `asyncio.TaskGroup` and structured concurrency — background from Nathaniel J. Smith's Trio/nursery concept, PEP 654 (exception groups), and the `quattro` backport implementing the same pattern for pre-3.11 Python (pypi.org/project/quattro)
- NVIDIA NeMo Guardrails `StreamingHandler` — `AsyncIterator`-based buffered token streaming, direct design reference for §3.1 — docs.nvidia.com/nemo/guardrails/streaming
- General asyncio I/O-bound vs. CPU-bound concurrency guidance and common anti-patterns (blocking calls inside coroutines, untracked/un-awaited tasks) — consistent with the same sourcing already used in SPEC_10 §2.3, applied here one layer up at the orchestration level
