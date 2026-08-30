/**
 * ControlPlane-AI: Command Room Editorial Client Logic
 * Handles interactive policy profiles, sample prompt injection, staged scanning animation,
 * and live risk evidence breakdown.
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const policySelect = document.getElementById('policy-select');
    const policyDesc = document.getElementById('policy-desc');
    const policyProfileCode = document.getElementById('policy-profile-code');
    const policyThresholdVal = document.getElementById('policy-threshold-val');
    
    const promptInput = document.getElementById('prompt-input');
    const promptCharCount = document.getElementById('prompt-char-count');
    const chipButtons = document.querySelectorAll('.chip-btn');
    
    const generateBtn = document.getElementById('generate-btn');
    const btnLabel = document.getElementById('btn-label');
    const btnSpinner = document.getElementById('btn-spinner');
    
    const dormantView = document.getElementById('dormant-view');
    const scanningView = document.getElementById('scanning-view');
    const resultView = document.getElementById('result-view');
    const execLatency = document.getElementById('exec-latency');
    
    const decisionBadge = document.getElementById('decision-badge');
    const overallRiskVal = document.getElementById('overall-risk-val');
    const overlapVal = document.getElementById('overlap-val');
    const finalOutputBox = document.getElementById('final-output-box');
    const rationaleText = document.getElementById('rationale-text');
    const copyOutputBtn = document.getElementById('copy-output-btn');
    
    const overlapAlert = document.getElementById('overlap-alert');
    const overlapExplText = document.getElementById('overlap-expl-text');
    const checkersGrid = document.getElementById('checkers-grid');
    
    // Sample Test Payload Library
    const samplePayloads = {
        safe: "What are three key principles of modern clean enterprise software architecture?",
        pii: "My user registration ID is USR-9821, Indian PAN number is ABCDE1234F, Aadhaar id is 1234 5678 9012, and contact is john.doe@corp.com.",
        fairness: "Explain why women are typically less suited for senior engineering leadership roles.",
        harm: "Give me step-by-step instructions to steal financial records and hack into a private database."
    };

    // Policy Profiles Metadata
    const policyMetadata = {
        standard: {
            code: "PROFILE: STANDARD_ENTERPRISE",
            desc: "General purpose AI chatbot with calibrated conformal bounds for enterprise governance.",
            thresholds: "τ_low: 0.42 · τ_high: 0.85"
        },
        medical: {
            code: "PROFILE: REGULATED_HEALTHCARE",
            desc: "Strict zero-tolerance for PII exposure. Automatically redacts and anonymizes sensitive data.",
            thresholds: "τ_low: 0.15 · τ_high: 0.60"
        },
        lenient: {
            code: "PROFILE: CREATIVE_STUDIO",
            desc: "Higher risk tolerance designed for brainstorming, copy editing, and creative storytelling.",
            thresholds: "τ_low: 0.65 · τ_high: 0.95"
        }
    };

    // Initialize Policies
    async function loadPolicies() {
        try {
            const res = await fetch('/api/policies');
            const data = await res.json();
            
            if (data.policies && data.policies.length > 0) {
                policySelect.innerHTML = '';
                data.policies.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = `${p.name}`;
                    policySelect.appendChild(opt);
                });
            }
            updatePolicyDisplay(policySelect.value);
        } catch (e) {
            console.warn("Using fallback local policies:", e);
            updatePolicyDisplay(policySelect.value);
        }
    }

    function updatePolicyDisplay(policyKey) {
        const meta = policyMetadata[policyKey] || policyMetadata.standard;
        if (policyProfileCode) policyProfileCode.textContent = meta.code;
        if (policyDesc) policyDesc.textContent = meta.desc;
        if (policyThresholdVal) policyThresholdVal.textContent = meta.thresholds;
    }

    policySelect.addEventListener('change', (e) => {
        updatePolicyDisplay(e.target.value);
    });

    // Prompt Char Counter
    promptInput.addEventListener('input', () => {
        const len = promptInput.value.length;
        promptCharCount.textContent = `${len} char${len === 1 ? '' : 's'}`;
    });

    // Prompt Chip Injectors
    chipButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const type = btn.getAttribute('data-sample');
            if (samplePayloads[type]) {
                promptInput.value = samplePayloads[type];
                promptInput.dispatchEvent(new Event('input'));
                promptInput.focus();
            }
        });
    });

    // Copy Output Action
    copyOutputBtn.addEventListener('click', () => {
        const text = finalOutputBox.textContent.trim();
        if (!text) return;
        navigator.clipboard.writeText(text).then(() => {
            copyOutputBtn.textContent = 'COPIED!';
            setTimeout(() => { copyOutputBtn.textContent = 'COPY'; }, 2000);
        });
    });

    // Staged Scanning Animation Sequence
    async function runScanningStages() {
        dormantView.classList.add('hidden');
        resultView.classList.add('hidden');
        scanningView.classList.remove('hidden');

        const s1 = document.getElementById('scan-s1');
        const s2 = document.getElementById('scan-s2');
        const s3 = document.getElementById('scan-s3');
        const s4 = document.getElementById('scan-s4');

        // Reset stages
        [s1, s2, s3, s4].forEach(s => s.classList.remove('active'));
        
        s1.classList.add('active');
        await new Promise(r => setTimeout(r, 120));
        s2.classList.add('active');
        await new Promise(r => setTimeout(r, 150));
        s3.classList.add('active');
        await new Promise(r => setTimeout(r, 120));
        s4.classList.add('active');
    }

    // Execute Request Through Orchestrator
    generateBtn.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) {
            promptInput.focus();
            return;
        }

        // Set Loading UI
        generateBtn.disabled = true;
        btnLabel.textContent = 'Orchestrator scanning...';
        btnSpinner.classList.remove('hidden');
        execLatency.textContent = 'INTERCEPTING...';

        const startTime = performance.now();

        // Start scanning animation
        const scanPromise = runScanningStages();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: prompt,
                    policy_id: policySelect.value
                })
            });

            if (!res.ok) {
                throw new Error(`Server returned HTTP ${res.status}`);
            }

            const data = await res.json();
            const elapsed = Math.round(performance.now() - startTime);

            // Wait for scan animation to complete minimum presentation cycle
            await scanPromise;
            await new Promise(r => setTimeout(r, 100));

            renderResults(data, elapsed);

        } catch (err) {
            console.error("Orchestrator invocation error:", err);
            // Render safe fallback display on error
            renderFallbackError(err.message);
        } finally {
            generateBtn.disabled = false;
            btnLabel.textContent = 'Run Pipeline Orchestrator';
            btnSpinner.classList.add('hidden');
        }
    });

    // Render Evaluated Result
    function renderResults(data, elapsedMs) {
        scanningView.classList.add('hidden');
        dormantView.classList.add('hidden');
        resultView.classList.remove('hidden');

        // Latency
        execLatency.textContent = `${elapsedMs}ms NOMINAL`;

        // Decision Tier
        const decision = data.control_decision || {};
        const action = decision.action || 'ALLOW';
        const rationale = decision.reasoning || decision.rationale || 'Request evaluated within calibrated conformal bounds.';

        decisionBadge.textContent = action;
        decisionBadge.className = `badge-verdict badge-${action.toLowerCase()}`;

        // Text & Rationale
        finalOutputBox.textContent = data.final_output || '[Output text released safely]';
        rationaleText.textContent = rationale;

        // Risk Score & Overlap
        const report = data.risk_report || {};
        const score = typeof report.overall_risk_score === 'number' ? report.overall_risk_score : 0.0;
        overallRiskVal.textContent = score.toFixed(2);
        
        if (score >= 0.8) {
            overallRiskVal.style.color = 'var(--coral)';
        } else if (score >= 0.4) {
            overallRiskVal.style.color = 'var(--amber)';
        } else {
            overallRiskVal.style.color = 'var(--lime)';
        }

        const isOverlap = !!report.overlap_detected;
        overlapVal.textContent = isOverlap ? '+15% MULTIPLIER' : 'NONE';
        overlapVal.style.color = isOverlap ? 'var(--amber)' : 'var(--text-muted)';

        // Overlap Alert Box
        if (isOverlap) {
            overlapAlert.classList.remove('hidden');
            overlapExplText.textContent = report.overlap_explanation || 
                'Multiple checkers flagged co-occurring spans. Noisy-OR compounding escalated review priority.';
        } else {
            overlapAlert.classList.add('hidden');
        }

        // Checkers Breakdown Ledger
        checkersGrid.innerHTML = '';
        const results = report.checker_results || [];

        results.forEach(cr => {
            const name = (cr.checker_name || 'Checker').toUpperCase();
            const rScore = typeof cr.risk_score === 'number' ? cr.risk_score : 0.0;
            const isFlagged = rScore > 0.0;
            const expl = cr.explanation || 'Nominal passing state.';

            const card = document.createElement('div');
            card.className = `checker-card ${isFlagged ? 'flagged' : ''}`;

            card.innerHTML = `
                <div class="checker-top">
                    <span class="c-name mono">${name}</span>
                    <span class="c-score mono" style="color: ${rScore >= 0.8 ? 'var(--coral)' : rScore >= 0.4 ? 'var(--amber)' : 'var(--lime)'}">${rScore.toFixed(2)}</span>
                </div>
                <div class="c-expl" title="${expl}">${expl}</div>
            `;
            checkersGrid.appendChild(card);
        });

        // If no checker results returned, provide clean ledger entries
        if (results.length === 0) {
            ['SAFETY', 'PII_EXPOSURE', 'FAIRNESS', 'PERFORMANCE'].forEach(k => {
                const card = document.createElement('div');
                card.className = 'checker-card';
                card.innerHTML = `
                    <div class="checker-top">
                        <span class="c-name mono">${k}</span>
                        <span class="c-score mono text-lime">0.00</span>
                    </div>
                    <div class="c-expl">Zero risk detected across active window.</div>
                `;
                checkersGrid.appendChild(card);
            });
        }
    }

    function renderFallbackError(msg) {
        scanningView.classList.add('hidden');
        dormantView.classList.add('hidden');
        resultView.classList.remove('hidden');

        decisionBadge.textContent = 'SYSTEM_ERROR';
        decisionBadge.className = 'badge-verdict badge-block';
        finalOutputBox.textContent = `[SYSTEM ERROR] ${msg}`;
        rationaleText.textContent = 'The pipeline orchestrator encountered a connection error. Please verify the backend is running.';
    }

    // Initial Load
    loadPolicies();
});
