document.addEventListener('DOMContentLoaded', () => {
    const policySelect = document.getElementById('policy-select');
    const policyDesc = document.getElementById('policy-desc');
    const promptInput = document.getElementById('prompt-input');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.querySelector('.btn-text');
    const loader = document.querySelector('.loader');
    const resultsPanel = document.getElementById('results-panel');
    
    let policiesMap = {};

    // Load available policies
    fetch('/api/policies')
        .then(res => res.json())
        .then(data => {
            policySelect.innerHTML = '';
            data.policies.forEach(p => {
                policiesMap[p.id] = p.description;
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                policySelect.appendChild(opt);
            });
            policyDesc.textContent = policiesMap[policySelect.value];
        })
        .catch(err => console.error("Failed to load policies", err));

    policySelect.addEventListener('change', (e) => {
        policyDesc.textContent = policiesMap[e.target.value];
    });

    generateBtn.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) return;

        // UI Loading State
        generateBtn.disabled = true;
        btnText.classList.add('hidden');
        loader.classList.remove('hidden');
        resultsPanel.classList.add('hidden');

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: prompt,
                    policy_id: policySelect.value
                })
            });

            const data = await res.json();
            renderResults(data);
        } catch (error) {
            alert("API Error: " + error.message);
        } finally {
            generateBtn.disabled = false;
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    });

    function renderResults(data) {
        // Unhide results
        resultsPanel.classList.remove('hidden');
        
        // Output text
        document.getElementById('final-output-text').textContent = data.final_output;
        document.getElementById('rationale-text').textContent = data.control_decision.rationale;
        
        // Badge
        const action = data.control_decision.action;
        const badge = document.getElementById('decision-badge');
        badge.textContent = action;
        badge.className = 'badge ' + action.toLowerCase();

        // Risk Report
        const report = data.risk_report;
        
        const riskEl = document.getElementById('overall-risk');
        riskEl.textContent = report.overall_risk_score.toFixed(2);
        riskEl.className = 'metric-value ' + (report.overall_risk_score >= 0.8 ? 'high' : report.overall_risk_score >= 0.4 ? 'med' : 'low');

        const overlapEl = document.getElementById('overlap-status');
        overlapEl.textContent = report.overlap_detected ? "YES" : "NO";
        overlapEl.className = 'metric-value ' + (report.overlap_detected ? 'high' : 'low');

        const overlapExpl = document.getElementById('overlap-expl');
        if (report.overlap_detected) {
            overlapExpl.textContent = report.overlap_explanation;
            overlapExpl.classList.remove('hidden');
        } else {
            overlapExpl.classList.add('hidden');
        }

        // Checkers
        const grid = document.getElementById('checkers-grid');
        grid.innerHTML = '';
        report.checker_results.forEach(cr => {
            const isFlagged = cr.risk_score > 0.0;
            const item = document.createElement('div');
            item.className = `checker-item ${isFlagged ? 'flagged' : 'clean'}`;
            
            item.innerHTML = `
                <div class="checker-info">
                    <span class="checker-name">${cr.checker_name}</span>
                </div>
                <span class="checker-score">${cr.risk_score.toFixed(2)}</span>
            `;
            // Add tooltip if there's an explanation
            if (isFlagged && cr.explanation) {
                item.title = cr.explanation; 
            }
            grid.appendChild(item);
        });
    }
});
