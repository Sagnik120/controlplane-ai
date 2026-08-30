<div align="center">

# 🛡️ ControlPlane-AI

### *Model-Agnostic Runtime Governance Middleware for Enterprise GenAI*

<br/>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-3.6_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge&logo=opensourceinitiative&logoColor=black)](https://opensource.org/licenses/MIT)
[![Build](https://img.shields.io/badge/Build-Passing-00C853?style=for-the-badge&logo=githubactions&logoColor=white)]()
[![Status](https://img.shields.io/badge/Status-Hackathon_Prototype-FF6D00?style=for-the-badge&logo=rocket&logoColor=white)]()

<br/>

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-Visit_Now-6C63FF?style=for-the-badge)](https://controlplane-ai-zajs.onrender.com)
[![Demo Video](https://img.shields.io/badge/🎬_Demo_Video-Watch_Walkthrough-FF0000?style=for-the-badge)](https://drive.google.com/file/d/1WQlvWAI9PtqViSca-iqVKyRT_4FSIin-/view?usp=drive_link)

<br/>

> **Enterprise GenAI without guardrails is a liability. ControlPlane-AI is the governance plane that changes that.**

</div>

---

## 📋 Table of Contents

- [🧭 Overview](#-overview)
- [🚀 Live Demo](#-live-demo)
- [🏗️ Architecture](#️-architecture)
- [🧩 Key Features](#-key-features)
- [🛠️ Tech Stack](#️-tech-stack)
- [📐 Mathematical Foundation](#-mathematical-foundation)
- [⚙️ Requirements](#️-requirements)
- [💻 Installation & Running Locally](#-installation--running-locally)
- [🎛️ Configuration](#️-configuration)
- [📊 Metrics & Trust Dashboard](#-metrics--trust-dashboard)
- [📁 Project Structure](#-project-structure)
- [🗺️ Roadmap & Known Limitations](#️-roadmap--known-limitations)
- [🐛 Troubleshooting & FAQ](#-troubleshooting--faq)
- [🤝 Maintainers](#-maintainers)
- [📄 License](#-license)

---

## 🧭 Overview

Modern enterprises deploy generative AI across diverse, concurrent business functions — from public customer chatbots to internal developer copilots and regulated clinical/financial assistants. Each use case operates under radically different risk tolerances and latency constraints.

Today, organizations face a **critical blind spot**:

- 🧠 **Hallucinations** that mislead users with confident-sounding falsehoods
- ☢️ **Toxic outputs** that violate brand and regulatory standards
- 👥 **Demographic bias** that creates discriminatory experiences
- 🔐 **PII exfiltration** that violates GDPR, HIPAA, and Indian DPDP Act
- 🤖 **Unauthorized agentic actions** that execute destructive tool calls

All of these are discovered **after** the user or downstream workflow has already consumed them.

**ControlPlane-AI** solves this by inserting a **runtime governance and evaluation plane** directly between the calling application and foundation LLMs. Rather than a rigid binary pass/fail filter, ControlPlane-AI is a model-agnostic runtime control layer that:

- ✅ **Evaluates** responses for performance, cost, and responsibility risks
- ✅ **Decides** whether to `ALLOW`, `MODIFY`, `REGENERATE`, or escalate to a human
- ✅ **Guarantees** mathematical coverage bounds via Conformal Prediction ($1 - \alpha = 95\%$)

> Moving enterprise AI governance from ungrounded heuristics into **provable statistical reliability**.

---

## 🚀 Live Demo

<div align="center">

| Resource | Link |
|:--------:|:----:|
| 🌐 **Deployed Web Console** | **[controlplane-ai-zajs.onrender.com](https://controlplane-ai-zajs.onrender.com)** |
| 🎬 **Demo Video Walkthrough** | **[Watch on Google Drive](https://drive.google.com/file/d/1WQlvWAI9PtqViSca-iqVKyRT_4FSIin-/view?usp=drive_link)** |
| 📦 **GitHub Repository** | **[Sagnik120/controlplane-ai](https://github.com/Sagnik120/controlplane-ai)** |

</div>

> [!TIP]
> No deployment? See [Installation & Running Locally](#-installation--running-locally) to run the full dashboard locally in under 5 minutes.

---

## 🏗️ Architecture

<div align="center">

![ControlPlane-AI Architecture](./architecture_diagram.png)

*Figure 1 — High-level 6-phase orchestration pipeline*

</div>

### 🔄 Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTROLPLANE-AI PIPELINE                      │
├──────────┬──────────────┬────────────┬────────────┬─────────────┤
│  STAGE 1 │   STAGE 2    │  STAGE 3   │  STAGE 4   │   STAGE 5   │
│ Ingestion│  Parallel    │  Semantic  │ Conformal  │ Intervention│
│ & Proxy  │  2-Tier Risk │  Overlap   │ Policy Gate│  Hierarchy  │
│          │    Engine    │ & Noisy-OR │  (ACI)     │  (5 Tiers)  │
└──────────┴──────────────┴────────────┴────────────┴─────────────┘
```

> [!NOTE]
> **Legend & Scope Callout**: Components marked `[Target — Roadmap]` in architectural specs — such as distributed PostgreSQL persistence, Kubernetes horizontal worker pools, and streaming `TaskGroup` proxying — represent production-grade target designs. The active prototype implements local JSONL logging, threaded concurrency pools, and direct FastAPI proxy interception.

---

## 🧩 Key Features

All implemented capabilities match the authoritative specification records in `instructions/specs/`:

### 🔌 Core Pipeline

- **🔌 Model-Agnostic LLM Adapter Layer** `SPEC_01 / SPEC_04`
  - Abstract streaming and synchronous interface
  - Supports Google Gemini (`gemini-3.6-flash`) via the modern `google-genai` SDK
  - Deterministic `MockAdapter` for offline and test execution — **zero API tokens consumed**

- **⚡ Microsecond 2-Tier Risk Gating** `SPEC_02`
  - Fast **Tier-0** regex/heuristic pre-filters executing in `< 2ms`
  - Bypasses heavy Tier-1 semantic models on clean text
  - Latency-preserving design with automatic circuit breaker fallback

### 🔐 Security & Compliance

- **🔒 Hybrid PII & Regional Compliance** `SPEC_02 / Indian PII`
  - Global identifiers: US SSN · Email · Credit Cards · Phone Numbers
  - Indian identifiers: **PAN** and **12-digit Aadhaar UIDAI** numbers
  - Powered by Microsoft Presidio Analyzer + custom regex recognizers

- **🛡️ LLM-as-a-Judge Safety & Bias Rubrics** `SPEC_03`
  - Structured JSON taxonomy evaluators via Google Gemini
  - Checks: Illicit planning · Violence · Hate speech · Demographic stereotyping

### 🧠 Intelligence & Evaluation

- **🤔 SelfCheckGPT Hallucination Detection** `SPEC_01`
  - Zero-resource black-box hallucination scoring
  - Stochastic sample agreement using **DeBERTa-v3 NLI** and **BERTScore** embeddings
  - No labelled training data required — works with any black-box LLM

- **🕸️ Cross-Checker Semantic Overlap Detection** `SPEC_12`
  - Token-level Intersection-over-Union (`char_iou`) clustering
  - `sentence-transformers` (`all-MiniLM-L6-v2`) for semantic co-occurrence
  - **Noisy-OR probability aggregation** for compounding risk penalties

### 📐 Statistical Guarantees

- **📐 Adaptive Conformal Inference (ACI) Policy Gate** `SPEC_03 / SPEC_13`
  - Dynamic quantile drift tracking: $\tau_{\text{low}}, \tau_{\text{high}}$
  - Self-calibrates over human review queues
  - Mathematically preserves error rate bounds under real-world data drift

### 🔧 Intervention & Recovery

- **✂️ Surgical Span Repair** `SPEC_08 / SPEC_09`
  - In-place regex and LLM span splicing
  - Redacts or rewrites **isolated violations** without discarding surrounding valid context
  - Intervention tier: `MODIFY`

- **🔁 Checkpoint-Backtrack-Resample Engine** `SPEC_09`
  - Prefix-preserving regeneration
  - Locks valid tokens $w_1 \dots w_k$ and resamples only contaminated suffixes
  - Avoids full response discard on partial violations

- **🤖 Dual-Plane Agentic Action Gate** `SPEC_14`
  - Separates conversational responses (`ALLOW`) from destructive agent tool executions (`BLOCK`)
  - Prevents unauthorized tool calls from bypassing policy enforcement

- **📋 Audit & Human Review Escalation Queues** `SPEC_16`
  - Structured append-only logging → `data/audit_log.jsonl`
  - High-uncertainty samples routed → `data/human_review_queue.jsonl`

---

## 🛠️ Tech Stack

<div align="center">

| Layer | Technology |
|:------|:-----------|
| 🐍 **Runtime & Language** | Python 3.11 |
| 🌐 **API Framework & Server** | FastAPI · Uvicorn · Pydantic v2 |
| 🤖 **LLM Provider** | Google GenAI SDK (`gemini-3.6-flash`) · Deterministic MockAdapter |
| 🔤 **NLP & Semantic Embeddings** | `sentence-transformers` (`all-MiniLM-L6-v2`) · SpaCy · Microsoft Presidio |
| 🧪 **Hallucination Evaluation** | `selfcheckgpt` — DeBERTa-v3 NLI · BERTScore |
| ⚙️ **Concurrency Model** | `asyncio` event loop + `ThreadPoolExecutor` worker pool |
| 🖥️ **User Interface** | Vanilla HTML5 · Modern CSS (Glassmorphism) · Vanilla JavaScript |
| 💾 **Data Storage (Prototype)** | Local append-only `.jsonl` audit files |
| ☁️ **Deployment** | Render Web Service · Python 3.11 · Lazy ML model loading |

</div>

---

## 📐 Mathematical Foundation

ControlPlane-AI's policy gate is grounded in formal **Conformal Prediction** theory:

### Conformal Coverage Guarantee

Given calibration nonconformity scores $s_1, \dots, s_n$, the threshold:

$$\hat{\tau} = \text{Quantile}\!\left(\{s_i\},\; \frac{\lceil(n+1)(1-\alpha)\rceil}{n}\right)$$

guarantees that for any new sample $X_{n+1}$:

$$\mathbb{P}(s_{n+1} \leq \hat{\tau}) \geq 1 - \alpha$$

### Adaptive Conformal Inference (ACI)

Under distribution shift, ControlPlane-AI tracks an adaptive $\alpha_t$:

$$\alpha_{t+1} = \alpha_t + \gamma\!\left(\alpha - \mathbf{1}\{Y_{t+1} \notin \mathcal{C}_t(X_{t+1})\}\right)$$

where $\gamma$ is a step-size hyperparameter and coverage self-corrects over time.

### Noisy-OR Risk Compounding

For $n$ co-occurring risk signals $p_1, \dots, p_n$:

$$P_{\text{compound}} = 1 - \prod_{i=1}^{n}(1 - p_i)$$

---

## ⚙️ Requirements

| Requirement | Details |
|:------------|:--------|
| 🐍 **Python** | Version `3.11` or higher |
| 📦 **Package Manager** | `pip` or `uv` |
| 🔑 **LLM Credentials** | Google Gemini API key (`GEMINI_API_KEY`) in `.env` |
| 💻 **OS** | macOS · Linux · Windows (PowerShell) |
| 📡 **Network** | Required for Gemini API calls; fully offline with `MockAdapter` |

> [!NOTE]
> **No API key?** Set `GEMINI_API_KEY=""` or omit it from `.env` to automatically use the built-in `MockAdapter` without consuming any live API tokens.

---

## 💻 Installation & Running Locally

### 🍎 macOS (zsh / bash)

```bash
# 1. Clone the repository
git clone https://github.com/Sagnik120/controlplane-ai.git
cd controlplane-ai

# 2. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 4. Set environment variables
cp .env.example .env
export GEMINI_API_KEY="your-gemini-api-key-here"

# 5. Start the server
uvicorn src.api.main:app --reload --port 8000

# 6. Open the dashboard
open http://localhost:8000
```

### 🐧 Linux (Ubuntu / Debian)

```bash
# 1. Clone the repository
git clone https://github.com/Sagnik120/controlplane-ai.git
cd controlplane-ai

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 4. Set environment variables
cp .env.example .env
export GEMINI_API_KEY="your-gemini-api-key-here"

# 5. Start the server
uvicorn src.api.main:app --reload --port 8000

# 6. Open the dashboard
xdg-open http://localhost:8000
```

### 🪟 Windows (PowerShell)

```powershell
# 1. Clone the repository
git clone https://github.com/Sagnik120/controlplane-ai.git
cd controlplane-ai

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 4. Set environment variables
Copy-Item .env.example .env
$env:GEMINI_API_KEY="your-gemini-api-key-here"

# 5. Start the server
uvicorn src.api.main:app --reload --port 8000

# 6. Open the dashboard
Start-Process "http://localhost:8000"
```

---

## 🎛️ Configuration

ControlPlane-AI uses declarative YAML policy configuration in [`configs/use_case_policies.yaml`](./configs/use_case_policies.yaml):

```yaml
use_cases:

  customer_support_chatbot:
    name: "Customer Support Chatbot"
    description: "Balanced risk tolerance for conversational support."
    max_overall_risk: 0.80
    conformal_bounds:
      tau_low: 0.42
      tau_high: 0.85
    block_on_overlap: true

  medical_assistant:
    name: "Medical Assistant"
    description: "Strict zero-tolerance for PII exposure with auto-redaction."
    max_overall_risk: 0.85
    conformal_bounds:
      tau_low: 0.15
      tau_high: 0.60
    checker_thresholds:
      pii: 0.00
    redact_pii: true
```

- 📋 **Full Policy Schema** → [`src/policy/schemas.py`](./src/policy/schemas.py)
- 🔧 **Offline Testing** → Set `GEMINI_API_KEY=""` to use `MockAdapter` without consuming live tokens

---

## 📊 Metrics & Trust Dashboard

The **Trust & Calibration Ledger** is accessible at `/metrics.html`:

| Metric | Description |
|:-------|:------------|
| 📈 **Conformal Coverage** | Empirical vs. guaranteed $95\%$ safety bound |
| ⚖️ **False Positive / Negative Rate** | Over-blocking and under-flagging ratios per policy |
| 🎯 **Action Tier Distribution** | Breakdown: `ALLOW · MODIFY · REGENERATE · HUMAN · BLOCK` |
| 🔌 **API Access** | Programmatic summary at `/api/metrics` |

> [!TIP]
> Run `python tests/demo/test_hackathon_readiness.py` to seed telemetry data into `data/metrics_log.jsonl` and populate the dashboard.

---

## 📁 Project Structure

```
controlplane-ai/
├── 📂 src/
│   ├── 📂 api/              # FastAPI app, routes, dependencies
│   ├── 📂 orchestrator/     # PipelineOrchestrator — central coordinator
│   ├── 📂 checkers/         # Risk evaluators (PII, Bias, Safety, Performance)
│   ├── 📂 engine/           # RiskEngine, SemanticOverlapDetector, EmbeddingRegistry
│   ├── 📂 policy/           # ControlPolicy, ACI calibrator, schemas
│   ├── 📂 audit/            # AuditLogger → JSONL append-only logs
│   ├── 📂 repair/           # SpanRepairEngine — surgical text splicing
│   ├── 📂 regenerate/       # CheckpointManager, RegenerationEngine
│   ├── 📂 agent/            # ActionGate — dual-plane agentic interception
│   ├── 📂 session/          # SessionStore — multi-turn drift tracking
│   ├── 📂 adapters/         # GeminiAdapter, MockAdapter
│   └── 📂 ui/               # Frontend dashboard (HTML5/CSS/JS)
├── 📂 configs/              # Declarative YAML use-case policies
├── 📂 data/                 # Audit logs, metrics, human review queues
├── 📂 tests/                # Diagnostic test suites per spec
├── 📂 docs/                 # Architecture documentation
├── 📄 requirements.txt      # Python dependencies
└── 📄 README.md             # You are here
```

---

## 🗺️ Roadmap & Known Limitations

Clear boundaries are maintained between current prototype constraints and production milestones:

| # | Area | Current Prototype | Production Target |
|:--|:-----|:-----------------|:-----------------|
| 1 | ⚙️ **Orchestration Loop** | Synchronous outer pipeline; checkers run in parallel thread pools | Native async `TaskGroup` proxy loop |
| 2 | 💾 **Persistence Layer** | Local append-only `.jsonl` files | Distributed PostgreSQL / ElasticSearch |
| 3 | 🤖 **Agent Feedback Loop** | `BLOCK` verdict returned to caller | Self-correction prompt injection into agent context |
| 4 | 🌍 **Multi-Jurisdiction** | US + Indian PII (PAN, Aadhaar) | EU AI Act · GDPR Article 22 · CCPA routing |

---

## 🐛 Troubleshooting & FAQ

<details>
<summary><b>❓ I see a [UPSTREAM RATE LIMIT] or 429 RESOURCE_EXHAUSTED error</b></summary>

Google Gemini's free tier enforces a rate limit of **20 requests per minute**. ControlPlane-AI's circuit breaker catches rate limits and halts the pipeline gracefully instead of crashing. Wait 30 seconds or test offline using the `MockAdapter`.

</details>

<details>
<summary><b>❓ Port 8000 is already in use on my machine</b></summary>

Start the server on an alternative port:
```bash
uvicorn src.api.main:app --reload --port 8080
```
Then navigate to `http://localhost:8080`.

</details>

<details>
<summary><b>❓ The Trust Dashboard displays "No metrics data found"</b></summary>

The dashboard computes statistical summaries over logged requests. Run at least one test query, or:
```bash
python tests/demo/test_hackathon_readiness.py
```
to seed telemetry data into `data/metrics_log.jsonl`.

</details>

<details>
<summary><b>❓ SelfCheckGPT / BERTScore is slow on the first request</b></summary>

On the **first hallucination-detection request**, DeBERTa-v3 and BERTScore models are downloaded from HuggingFace Hub (~500MB combined). Subsequent requests use cached models and are significantly faster. This is by design — all heavy ML models use **lazy on-demand loading** to ensure sub-second server boot.

</details>

---

## 🤝 Maintainers

<div align="center">

| Name | Role | GitHub |
|:-----|:-----|:-------|
| **Sagnik Chandra** | Lead Developer | [@Sagnik120](https://github.com/Sagnik120) |

</div>

---

## 📄 License

<div align="center">

This project is submitted for the **Accenture Innovation Challenge**.

[![License: MIT](https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge&logo=opensourceinitiative&logoColor=black)](https://opensource.org/licenses/MIT)

*Copyright © 2026 Sagnik Chandra · Released under the MIT License*

---

*Built with ❤️ for enterprise AI safety · Powered by Google Gemini · Deployed on Render*

</div>
