document.addEventListener('DOMContentLoaded', async () => {
    const root = document.getElementById('metrics-root');
    
    try {
        const response = await fetch('/api/metrics');
        if (!response.ok) throw new Error("Failed to fetch metrics");
        const data = await response.json();
        
        if (!data.use_cases || Object.keys(data.use_cases).length === 0) {
            root.innerHTML = '<div style="text-align: center; color: #ffab57;">No metrics data found. Run the demo and compute script.</div>';
            return;
        }

        let html = '';
        
        // Aggregate headline
        let totalAllowed = 0;
        let totalCoverage = 0;
        let totalSaved = 0;
        let totalGuaranteed = 0;
        let ucCount = 0;
        
        for (const [uc, s] of Object.entries(data.use_cases)) {
            totalCoverage += s.empirical_coverage;
            totalGuaranteed += s.guaranteed_coverage;
            totalSaved += s.cost_saved_usd;
            ucCount++;
        }
        
        const avgCoverage = ucCount > 0 ? (totalCoverage / ucCount).toFixed(1) : "0.0";
        const avgGuaranteed = ucCount > 0 ? (totalGuaranteed / ucCount).toFixed(1) : "95.0";
        
        html += `
            <div class="headline-section glass-panel">
                <div class="headline-title">Empirical vs Guaranteed Coverage</div>
                <div class="headline-val">${avgCoverage}% <span style="font-size: 1.2rem; color: #8b949e; font-weight: 400;">/ ${avgGuaranteed}% guaranteed</span></div>
                <div class="headline-sub">Actual safety rate of allowed responses vs conformal prediction statistical guarantee</div>
                <div style="margin-top: 16px; font-weight: 600; color: #57a6ff;">Total Cost Saved: $${totalSaved.toFixed(2)} USD</div>
            </div>
            <div class="metrics-container">
        `;

        for (const [uc, s] of Object.entries(data.use_cases)) {
            let totalTiers = Object.values(s.tier_distribution).reduce((a, b) => a + b, 0);
            if (totalTiers === 0) totalTiers = 1; // prevent div by zero
            
            html += `
                <div class="use-case-section">
                    <div class="use-case-title">Use Case: ${uc.replace('_', ' ')}</div>
                    
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <h4>Empirical Coverage</h4>
                            <div class="val ${s.empirical_coverage >= s.guaranteed_coverage ? 'good' : 'warn'}">${s.empirical_coverage}%</div>
                        </div>
                        <div class="metric-box">
                            <h4>False Positive Rate</h4>
                            <div class="val ${s.false_positive_rate > 20 ? 'bad' : 'good'}">${s.false_positive_rate}%</div>
                        </div>
                        <div class="metric-box">
                            <h4>False Negative Rate</h4>
                            <div class="val ${s.false_negative_rate > 5 ? 'bad' : 'good'}">${s.false_negative_rate}%</div>
                        </div>
                        <div class="metric-box">
                            <h4>Avg Latency (ALLOW)</h4>
                            <div class="val" style="color: #c9d1d9;">${s.avg_latency_ms.ALLOW}ms</div>
                        </div>
                    </div>
                    
                    <h4 style="color: #8b949e; margin-bottom: 12px; font-weight: 500;">Action Tier Distribution (N=${s.total_requests})</h4>
                    <div class="bar-chart-container">
            `;
            
            for (const tier of ["ALLOW", "MODIFY", "REGENERATE", "HUMAN", "BLOCK"]) {
                const count = s.tier_distribution[tier] || 0;
                const pct = ((count / totalTiers) * 100).toFixed(1);
                
                html += `
                    <div class="bar-row">
                        <div class="bar-label">${tier}</div>
                        <div class="bar-wrapper">
                            <div class="bar-fill bar-${tier}" style="width: ${pct}%"></div>
                        </div>
                        <div style="width: 50px; text-align: right;">${pct}%</div>
                    </div>
                `;
            }
            
            html += `
                    </div>
                </div>
            `;
        }
        
        html += `</div>`;
        root.innerHTML = html;
        
    } catch (e) {
        root.innerHTML = `<div style="text-align: center; color: #ff5757;">Error loading metrics: ${e.message}</div>`;
    }
});
