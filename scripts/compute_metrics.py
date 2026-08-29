import json
import os
from collections import defaultdict

def compute_metrics():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    metrics_file = os.path.join(project_root, 'data', 'metrics_log.jsonl')
    output_file = os.path.join(project_root, 'data', 'metrics_summary.json')

    if not os.path.exists(metrics_file):
        print(f"No metrics log found at {metrics_file}")
        with open(output_file, 'w') as f:
            json.dump({"use_cases": {}}, f)
        return

    # Data structures for aggregation
    stats = defaultdict(lambda: {
        "total": 0,
        "tiers": {"ALLOW": 0, "MODIFY": 0, "REGENERATE": 0, "HUMAN": 0, "BLOCK": 0},
        "latency_sum": {"ALLOW": 0, "MODIFY": 0, "REGENERATE": 0, "HUMAN": 0, "BLOCK": 0},
        "coverage": {"allowed_and_reviewed": 0, "allowed_and_safe": 0, "guaranteed": 95.0},
        "fp_fn": {"total_safe": 0, "total_unsafe": 0, "false_positives": 0, "false_negatives": 0},
        "cost_saved": 0.0
    })

    with open(metrics_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except:
                continue

            uc = record.get('use_case', 'default')
            tier = record.get('decision_tier', 'BLOCK')
            latency = record.get('latency_ms', 0)
            verdict = record.get('human_verdict')

            s = stats[uc]
            s["total"] += 1
            if tier in s["tiers"]:
                s["tiers"][tier] += 1
                s["latency_sum"][tier] += latency
            
            # Coverage calculation
            if tier == "ALLOW" and verdict:
                s["coverage"]["allowed_and_reviewed"] += 1
                if verdict == "SAFE":
                    s["coverage"]["allowed_and_safe"] += 1
                    
            # FP / FN
            if verdict == "SAFE":
                s["fp_fn"]["total_safe"] += 1
                if tier in ["MODIFY", "REGENERATE", "HUMAN", "BLOCK"]:
                    s["fp_fn"]["false_positives"] += 1
            elif verdict == "UNSAFE":
                s["fp_fn"]["total_unsafe"] += 1
                if tier == "ALLOW":
                    s["fp_fn"]["false_negatives"] += 1

            # Cost Saved estimate (Synthetic calculation for demo)
            if tier == "MODIFY":
                s["cost_saved"] += 0.02
            if tier == "ALLOW":
                s["cost_saved"] += 0.01

    # Finalize Aggregations
    summary = {"use_cases": {}}
    for uc, s in stats.items():
        # Avg Latency
        avg_latency = {}
        for t in s["tiers"]:
            count = s["tiers"][t]
            avg_latency[t] = int(s["latency_sum"][t] / count) if count > 0 else 0
            
        # Empirical Coverage
        emp_coverage = 100.0
        if s["coverage"]["allowed_and_reviewed"] > 0:
            emp_coverage = (s["coverage"]["allowed_and_safe"] / s["coverage"]["allowed_and_reviewed"]) * 100.0
            
        # FP / FN Rates
        fp_rate = (s["fp_fn"]["false_positives"] / s["fp_fn"]["total_safe"]) * 100 if s["fp_fn"]["total_safe"] > 0 else 0.0
        fn_rate = (s["fp_fn"]["false_negatives"] / s["fp_fn"]["total_unsafe"]) * 100 if s["fp_fn"]["total_unsafe"] > 0 else 0.0

        summary["use_cases"][uc] = {
            "total_requests": s["total"],
            "tier_distribution": s["tiers"],
            "avg_latency_ms": avg_latency,
            "empirical_coverage": round(emp_coverage, 1),
            "guaranteed_coverage": s["coverage"]["guaranteed"],
            "false_positive_rate": round(fp_rate, 1),
            "false_negative_rate": round(fn_rate, 1),
            "cost_saved_usd": round(s["cost_saved"], 2)
        }

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
        
    print(f"Metrics computation complete. Summary written to {output_file}")

if __name__ == "__main__":
    compute_metrics()
