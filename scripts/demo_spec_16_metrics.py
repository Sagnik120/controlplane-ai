import json
import os
import random
from datetime import datetime, timedelta
import uuid

def generate_synthetic_metrics():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    metrics_file = os.path.join(project_root, 'data', 'metrics_log.jsonl')
    
    os.makedirs(os.path.dirname(metrics_file), exist_ok=True)

    use_cases = ["customer_support", "internal_analyst", "coding_copilot"]
    tiers = ["ALLOW", "MODIFY", "REGENERATE", "HUMAN", "BLOCK"]
    
    # Generate ~200 records to make the dashboard look good
    print(f"Generating synthetic metrics log at {metrics_file}...")
    
    with open(metrics_file, "w") as f:
        now = datetime.utcnow()
        for i in range(200):
            uc = random.choice(use_cases)
            
            # Weighted random for tiers
            if uc == "customer_support":
                tier = random.choices(tiers, weights=[60, 20, 10, 8, 2])[0]
            else:
                tier = random.choices(tiers, weights=[80, 10, 5, 3, 2])[0]
                
            latency = random.randint(150, 400)
            if tier == "MODIFY": latency += random.randint(300, 800)
            if tier == "REGENERATE": latency += random.randint(1000, 2500)
            
            # Synthetic human verdicts for coverage calculation
            verdict = None
            if random.random() < 0.4:  # 40% of cases are reviewed
                if tier == "ALLOW":
                    verdict = "SAFE" if random.random() < 0.96 else "UNSAFE" # 96% empirical coverage
                elif tier in ["MODIFY", "REGENERATE", "HUMAN"]:
                    verdict = "SAFE" if random.random() < 0.15 else "UNSAFE" # 15% false positive rate
                elif tier == "BLOCK":
                    verdict = "UNSAFE"
                    
            entry = {
                "request_id": str(uuid.uuid4()),
                "timestamp": (now - timedelta(minutes=i*15)).isoformat() + "Z",
                "use_case": uc,
                "decision_tier": tier,
                "risk_scores": {
                    "performance": random.uniform(0.1, 0.9) if tier != "ALLOW" else random.uniform(0.01, 0.4),
                    "pii": random.uniform(0.1, 0.9) if tier != "ALLOW" else random.uniform(0.01, 0.4)
                },
                "overlap_flag": random.random() < 0.1,
                "coverage_pct": 95.0,
                "latency_ms": latency,
                "human_verdict": verdict
            }
            f.write(json.dumps(entry) + "\n")
            
    print("Generation complete! Run `python scripts/compute_metrics.py` next.")

if __name__ == "__main__":
    generate_synthetic_metrics()
