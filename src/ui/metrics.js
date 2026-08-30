/**
 * ControlPlane-AI: Trust & Calibration Ledger Renderer
 */

document.addEventListener('DOMContentLoaded', async () => {
    const root = document.getElementById('metrics-container');
    
    try {
        const response = await fetch('/api/metrics');
        if (!response.ok) throw new Error("Failed to fetch metrics from server");
        const data = await response.json();
        
        if (!data.use_cases || Object.keys(data.use_cases).length === 0) {
            renderEmptyState();
            return;
        }

        renderMetrics(data);
        
    } catch (e) {
        console.warn("Could not retrieve telemetry from /api/metrics:", e);
        renderEmptyState();
    }

    function renderEmptyState() {
        root.innerHTML = `
            <div class="use-case-card" style="text-align: center; padding: 48px 24px;">
                <span class="mono text-muted" style="font-size: 0.8rem; letter-spacing: 1px;">LEDGER STATUS: NO TELEMETRY ACCUMULATED YET</span>
                <div style="font-family: var(--font-heading); font-size: 1.6rem; font-weight: 700; color: #FFF; margin: 12px 0 8px 0;">
                    Run Prompts in the Testbench to Generate Audit Data
                </div>
                <p style="color: var(--text-secondary); font-size: 0.9rem; max-width: 520px; margin: 0 auto 24px auto; line-height: 1.5;">
                    Metrics are computed dynamically from <code class="mono" style="color: var(--lime);">data/metrics_log.jsonl</code>. 
                    Execute test prompts in the Live Testbench or run the evaluation script to populate live statistical coverage.
                </p>
                <a href="index.html#pipeline-section" class="btn btn-lime" style="display: inline-flex; align-items: center; gap: 8px; text-decoration: none; padding: 10px 20px; border-radius: 4px; font-weight: 600;">
                    <span>Open Live Testbench</span>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M1 7H13M13 7L7 1M13 7L7 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </a>
            </div>
        `;
    }

    function renderMetrics(data) {
        let totalCoverage = 0;
        let totalGuaranteed = 0;
        let ucCount = 0;
        
        for (const [uc, s] of Object.entries(data.use_cases)) {
            if (typeof s.empirical_coverage === 'number') {
                totalCoverage += s.empirical_coverage;
                totalGuaranteed += s.guaranteed_coverage || 95.0;
                ucCount++;
            }
        }
        
        const avgCoverage = ucCount > 0 ? (totalCoverage / ucCount).toFixed(1) : "95.0";
        const avgGuaranteed = ucCount > 0 ? (totalGuaranteed / ucCount).toFixed(1) : "95.0";

        let html = `
            <!-- Top Aggregate Ledger Summary -->
            <div class="use-case-card" style="border-color: rgba(200, 244, 90, 0.3); background: rgba(200, 244, 90, 0.02); margin-bottom: 36px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 20px;">
                    <div>
                        <span class="mono text-lime" style="font-size: 0.75rem; letter-spacing: 1px;">STATISTICAL CONFORMAL EVALUATION</span>
                        <div style="font-family: var(--font-heading); font-size: 2.4rem; font-weight: 700; color: #FFF; margin: 4px 0;">
                            ${avgCoverage}% <span style="font-size: 1.1rem; color: var(--text-muted); font-weight: 400;">empirical coverage (${avgGuaranteed}% bound)</span>
                        </div>
                        <p style="color: var(--text-secondary); font-size: 0.85rem; max-width: 580px;">
                            Calculated from real logged events in <code class="mono" style="color: var(--lime);">data/metrics_log.jsonl</code>.
                        </p>
                    </div>
                </div>
            </div>
        `;

        for (const [uc, s] of Object.entries(data.use_cases)) {
            const tiers = s.tier_distribution || {};
            let totalTiers = Object.values(tiers).reduce((a, b) => a + b, 0);
            if (totalTiers === 0) totalTiers = 1;

            const fpos = typeof s.false_positive_rate === 'number' ? s.false_positive_rate.toFixed(1) : "0.0";
            const fneg = typeof s.false_negative_rate === 'number' ? s.false_negative_rate.toFixed(1) : "0.0";
            const lat = (s.avg_latency_ms && s.avg_latency_ms.ALLOW) ? s.avg_latency_ms.ALLOW : 0;
            const empCov = typeof s.empirical_coverage === 'number' ? `${s.empirical_coverage.toFixed(1)}%` : "N/A";

            html += `
                <div class="use-case-card">
                    <div class="use-case-header">
                        <div>
                            <span class="mono text-muted" style="font-size: 0.72rem;">USE-CASE POLICY</span>
                            <div class="uc-title">${uc.replace(/_/g, ' ')}</div>
                        </div>
                        <span class="mono-meta">RECORDED RUNS: ${s.total_requests || 0}</span>
                    </div>

                    <div class="metrics-stats-grid">
                        <div class="stat-box">
                            <span class="stat-label mono">EMPIRICAL COVERAGE</span>
                            <span class="stat-val text-lime">${empCov}</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-label mono">FALSE POSITIVE RATE</span>
                            <span class="stat-val">${fpos}%</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-label mono">FALSE NEGATIVE RATE</span>
                            <span class="stat-val">${fneg}%</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-label mono">AVG ALLOW LATENCY</span>
                            <span class="stat-val mono" style="color: var(--text-secondary)">${lat}ms</span>
                        </div>
                    </div>

                    <span class="chart-section-title mono">RECORDED ACTION TIER DISTRIBUTION (N=${s.total_requests || 0})</span>
                    <div style="margin-top: 8px;">
            `;

            for (const tier of ["ALLOW", "MODIFY", "REGENERATE", "HUMAN", "BLOCK"]) {
                const count = tiers[tier] || 0;
                const pct = ((count / totalTiers) * 100).toFixed(1);

                html += `
                    <div class="bar-row">
                        <div class="bar-lbl">${tier}</div>
                        <div class="bar-track">
                            <div class="bar-fill-bar bar-${tier.toLowerCase()}" style="width: ${pct}%"></div>
                        </div>
                        <div class="bar-num">${count} (${pct}%)</div>
                    </div>
                `;
            }

            html += `
                    </div>
                </div>
            `;
        }

        root.innerHTML = html;
    }
});
