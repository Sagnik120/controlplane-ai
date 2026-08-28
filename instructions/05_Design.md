# 05_Design.md — Visual Design Guidelines

## STATUS: AUTHORITATIVE for the dashboard UI (Phase 7). Functionality always takes priority over
## visual polish — do not spend build time here until Phases 0–6 are working and confirmed.

---

## 1. Design Goal

The dashboard exists to make ControlPlane's decision-making **visible and trustworthy** in a live
demo. It is a judge-facing tool, not a consumer product. Prioritize clarity and legibility over
decoration.

## 2. Layout

Three-panel layout (matches the demo narrative):
- **Left panel**: Input controls — prompt textbox, use-case dropdown, LLM provider dropdown, Submit
  button.
- **Center panel**: Live response stream + live checker score bars (Performance, Safety, Bias, PII,
  Cost) updating as generation proceeds.
- **Right panel**: Final decision badge (ALLOW/MODIFY/REGENERATE/HUMAN) with the reason string, plus
  a collapsible audit log table below showing recent past decisions.

## 3. Color System (use CSS variables, do not hardcode hex values inline)

- **Background**: near-black or very dark neutral (`--bg: #0f1115`) for a "control room / monitoring
  dashboard" feel — this is a governance tool, not a playful consumer app.
- **Text**: off-white (`--text: #e8e8ea`)
- **Decision colors** (use consistently everywhere a decision appears):
  - ALLOW → green (`--allow: #2ecc71`)
  - MODIFY → amber/yellow (`--modify: #f1c40f`)
  - REGENERATE → orange (`--regenerate: #e67e22`)
  - HUMAN → red (`--human: #e74c3c`)
- **Risk score bars**: gradient from green (low risk) to red (high risk), driven by the numeric score,
  not by fixed category color.
- **Accent**: a single accent color for interactive elements (buttons, active dropdown) — a calm blue
  (`--accent: #3b82f6`) is a safe default.

## 4. Typography

- Use a monospace or semi-monospace font for anything showing scores, JSON, or logs (e.g., `JetBrains
  Mono`, `Roboto Mono`, or system `monospace` fallback) — reinforces the "technical monitoring tool"
  feel.
- Use a clean sans-serif (system font stack is fine: `-apple-system, Segoe UI, Roboto, sans-serif`)
  for labels and body text.
- Keep font sizes readable at a distance for a live demo/screen share — nothing below 14px for body
  text, decision badges should be large and bold (24px+).

## 5. Interaction Behavior

- Checker score bars should visibly animate/update as a response streams, not just snap to a final
  value — this is the core "live monitoring" visual proof and matters more than any other visual
  detail.
- The decision badge should visually pulse or highlight briefly when it changes, so it's obvious in
  a recorded demo.
- Switching the use-case dropdown and re-submitting the same prompt should make it obvious that the
  decision changed — consider showing the previous decision struck through or side-by-side for the
  demo recording.

## 6. Explicit Non-Goals for Design

- No dark/light theme toggle — pick the dark "control room" theme and commit to it.
- No animations beyond what's described above — do not spend time on decorative motion.
- No component library unless already approved in `03_Rules.md` — plain CSS or minimal utility
  classes are sufficient.
- No mobile-responsive design required — this is demoed on a laptop/desktop screen recording.
