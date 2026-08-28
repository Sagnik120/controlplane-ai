# SPEC_05 — Upgrade `risk_engine.py` with Dynamic Severity-Weighted Overlap Scoring

**Status:** Ready to implement
**Touches:** `src/engine/risk_engine.py`, `configs/use_case_policies.yaml`
**Independent of:** all other specs — this only changes how already-produced `CheckerResult`
objects get combined, regardless of which detection method produced them. Safe to implement
whether SPEC_02/04 are done or still using older logic.

---

## 1. Why the current logic is weak

Per `codebase_analysis_and_roadmap.md`: the Risk Engine detects overlaps by checking whether
flagged character spans from different checkers intersect, then applies a **static +0.15 penalty**
regardless of which categories overlapped or how severe each one was individually. This means:
- A low-confidence Bias flag (0.3) overlapping a low-confidence Safety flag (0.3) gets the same
  +0.15 bump as a high-confidence PII flag (0.9) overlapping a high-confidence Performance/
  hallucination flag (0.9) — even though the second case is a fabricated fact about a real person,
  arguably the single most liability-heavy overlap category the PS explicitly names: *"a fabricated
  detail about a person can simultaneously be a hallucination and a privacy concern."*
- The penalty is additive and unbounded in principle, with no theoretical grounding for why 0.15
  specifically, and no distinction between overlap **types**.

## 2. The research this is based on

There is no single canonical "overlap scoring" paper — this is a genuine gap in the literature
(most safety-checker research treats risk categories independently). Instead, synthesize from two
adjacent, well-established ideas so the design is principled rather than another arbitrary constant:

1. **Noisy-OR combination for correlated risk signals** — the same technique used in SPEC_02 for
   combining multiple PII entities within one checker. This is a standard, well-understood
   probabilistic combination rule (used throughout Bayesian network literature for combining
   multiple independent "causes" of a single outcome) and is directly reusable here: treat each
   flagged checker as an independent "cause" of the response being untrustworthy, and combine via
   `1 - Π(1 - risk_i)` **per overlapping span**, instead of a flat additive bump. This alone fixes
   the "same penalty regardless of severity" problem, because noisy-OR is a function of the actual
   input risk scores, not a constant.

2. **Category-pair severity weighting, informed by the PS's own stated example** — the PS explicitly
   flags **hallucination × PII** ("fabricated detail about a person") as the paradigm case of
   dangerous overlap. Build an explicit, editable severity-multiplier matrix over category pairs
   rather than treating all overlaps as equal — this is the same "config over hard-coded logic"
   principle used throughout your other specs (taxonomy-in-prompt for SPEC_04, calibrated alpha
   for SPEC_03), applied here to overlap severity. This is a design choice you can defend to judges
   as "informed by the problem statement's own example," not an arbitrary matrix.

**Concrete finding worth citing for credibility:** CAMP (Panjwani, 2025, arXiv:2604.16521)
formalizes a related idea — "Cumulative [Risk] Exposure" as a metric that measures how multiple
individually-sub-threshold signals combine into a materially higher combined risk, specifically for
PII, and shows that per-signal thresholding (checking each checker in isolation) systematically
misses these compounding cases. Same principle, applied within a single response instead of across
turns (that cross-turn version is SPEC_06). Cite this as validating the general shape of the
problem ("individually low-risk signals can combine into materially higher risk") even though this
spec's specific formula is your own synthesis, not lifted verbatim from the paper.

## 3. Design

### 3.1 Severity multiplier matrix (config, not code)
```yaml
# configs/overlap_severity_matrix.yaml (new file)
overlap_multipliers:
  performance_pii: 1.8        # PS's paradigm example: fabricated fact about a real person
  performance_safety: 1.5
  safety_pii: 1.6
  bias_pii: 1.4
  performance_bias: 1.2
  bias_safety: 1.3
  default: 1.1                # any other/unlisted pair
```
These are starting values you state plainly as **design choices**, not statistically calibrated
(don't conflate this with SPEC_03's conformal calibration — be precise about which numbers in your
system are calibrated vs. reasoned defaults, judges may probe this distinction).

### 3.2 Combination formula
For a span where checkers `{c_1, c_2, ..., c_n}` all flag overlapping text with risk scores
`{r_1, ..., r_n}`:

```
base_combined = 1 - Π(1 - r_i)                       # noisy-OR across all overlapping checkers
pair_multiplier = max(overlap_multipliers[pair] for each pair (c_i, c_j) present in the overlap)
final_span_risk = min(1.0, base_combined * pair_multiplier)
```

Using `max` over all pairs present (not sum/average) means a 3-way overlap that includes the
dangerous `performance_pii` pair gets that multiplier even if other pairs in the same overlap are
less severe — you don't want a severe pairing "diluted" by averaging with milder ones.

### 3.3 Output — retain full transparency (do not collapse to one number)
```
OverlapRecord:
    span_start: int
    span_end: int
    overlapping_checkers: List[str]
    individual_scores: Dict[str, float]        # unchanged, keep raw scores visible
    base_noisy_or: float
    multiplier_applied: float
    multiplier_reason: str                     # e.g. "performance+pii pair detected (1.8x)"
    final_span_risk: float
```
This satisfies the PS's audit-trail requirement even better than the current static-penalty
version — a stakeholder can see exactly *why* an overlap was escalated, not just that a flat bump
was applied.

## 4. Step-by-step implementation plan

**Step 1 — Create `configs/overlap_severity_matrix.yaml`** with the starting values in §3.1.
Load it once at startup in `risk_engine.py`'s constructor (or via `dependencies.py`, matching how
other configs are loaded per `02_Architecture.md`).

**Step 2 — Rewrite the overlap-detection block in `risk_engine.py`**
- Keep the existing span-intersection detection logic (already works, per the roadmap doc — don't
  rewrite what isn't broken).
- Replace the static `+0.15` block with the noisy-OR + multiplier formula from §3.2.
- Build the `OverlapRecord` objects from §3.3 and attach them to `FinalRiskReport` (extend that
  schema, do not create a parallel structure).

**Step 3 — Handle pair-key normalization**
- Category pairs are unordered (`performance_pii` == `pii_performance`) — normalize by sorting
  category names alphabetically before matrix lookup, so the YAML only needs one direction per
  pair. Implement this as a small helper, not duplicated inline logic.

**Step 4 — Wire `final_span_risk` into the overall risk profile**
- The Risk Engine's existing aggregate `FinalRiskReport` risk-per-dimension values should use
  `final_span_risk` (post-multiplier) wherever a span belongs to a detected overlap, and the raw
  per-checker score otherwise — don't apply the multiplier to non-overlapping spans.

## 5. Definition of Done

- [ ] Static `+0.15` constant is fully removed from `risk_engine.py`.
- [ ] `configs/overlap_severity_matrix.yaml` exists, is loaded at startup, and is editable without
      code changes.
- [ ] `OverlapRecord` objects retain individual checker scores, the noisy-OR base, the multiplier
      applied, and a human-readable reason — visible in the audit log.
- [ ] Diagnostic script includes: a no-overlap clean case, a low-severity overlap (e.g. bias+safety
      both at ~0.3), and the PS's paradigm case — a fabricated (Performance-flagged) detail about a
      named person that is also PII-flagged — confirming it receives the highest multiplier
      (1.8x) and a materially higher final risk than either checker's individual score.
- [ ] Pitch deck slide: state clearly that the overlap detection mechanism (span intersection,
      noisy-OR combination) is a principled probabilistic technique, and the severity-multiplier
      values are stated design assumptions directly informed by the PS's own example — do not
      overclaim these specific numbers as "research-backed," only the combination *method* is.
      Optionally cite CAMP (arXiv:2604.16521) as supporting evidence that compounding/cumulative
      risk from individually-sub-threshold signals is a real, documented phenomenon.
