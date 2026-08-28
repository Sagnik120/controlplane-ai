import os
import sys
import json
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.feedback.feedback_store import FeedbackStore
from scripts.recalibrate import main as run_recalibration
from scripts.calibrate_thresholds import get_calibration_data

def generate_mock_human_review_queue(filepath: str, n=15):
    """
    Simulate a human reviewing the queue and assigning verdicts.
    We'll generate items where the human confirmed the risk.
    These should push the calibration distribution higher.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        for i in range(n):
            # Human confirmed risk, so these were true positives (very bad examples)
            # They will have high risk scores.
            item = {
                "timestamp": f"2026-08-28T12:00:{i:02d}Z",
                "original_response_length": 100,
                "metadata": {
                    "human_verdict": "confirm_risk"
                },
                "risk_report": {
                    "checker_results": [
                        {"checker_name": "performance", "risk_score": random.uniform(0.8, 1.0)},
                        {"checker_name": "safety", "risk_score": random.uniform(0.8, 1.0)},
                        {"checker_name": "bias", "risk_score": random.uniform(0.7, 1.0)},
                        {"checker_name": "pii", "risk_score": random.uniform(0.9, 1.0)}
                    ]
                }
            }
            f.write(json.dumps(item) + "\n")

def main():
    print("=======================================================================")
    print("🔬 Testing Feedback Loop & Recalibration (SPEC 07)")
    print("=======================================================================")
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    queue_file = os.path.join(project_root, 'data', 'human_review_queue.jsonl')
    cal_file = os.path.join(project_root, 'data', 'calibration_set.jsonl')
    
    # 1. Clean state
    if os.path.exists(queue_file): os.remove(queue_file)
    if os.path.exists(cal_file): os.remove(cal_file)
    
    # 2. Bootstrapping calibration set
    print("1. Bootstrapping initial calibration set...")
    _, initial_size = get_calibration_data()
    print(f"   Initial set size: {initial_size}")
    
    # 3. Simulate human reviewing 15 items
    print("\n2. Simulating a human reviewing 15 flagged items (confirm_risk)...")
    generate_mock_human_review_queue(queue_file, n=15)
    
    # 4. Run recalibration
    print("\n3. Triggering Recalibration Script...")
    run_recalibration()
    
    # 5. Verify the set grew
    _, new_size = get_calibration_data()
    print(f"\n4. Final Verification:")
    print(f"   New calibration set size: {new_size}")
    
    if new_size == initial_size + 15:
        print("   ✅ PASS: Calibration set correctly expanded with human feedback.")
    else:
        print("   ❌ FAIL: Calibration set did not expand correctly.")
        
if __name__ == "__main__":
    main()
