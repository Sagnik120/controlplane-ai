import os
import sys
import json
import random
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.feedback.feedback_store import FeedbackStore
from scripts.recalibrate import main as run_recalibration
from scripts.calibrate_thresholds import get_calibration_data

def setup_clean_state(queue_file, cal_file):
    if os.path.exists(queue_file): os.remove(queue_file)
    if os.path.exists(cal_file): os.remove(cal_file)
    # Ensure directory exists
    os.makedirs(os.path.dirname(queue_file), exist_ok=True)

def write_queue_items(filepath, items):
    with open(filepath, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")

def print_header(title):
    print("\n" + "="*80)
    print(f"🔬 {title}")
    print("="*80)

def main():
    print_header("Deep Integration & Edge Case Tests for SPEC 07 (Active Learning)")
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    queue_file = os.path.join(project_root, 'data', 'human_review_queue.jsonl')
    cal_file = os.path.join(project_root, 'data', 'calibration_set.jsonl')
    
    store = FeedbackStore()
    
    total = 0
    passed = 0

    # -------------------------------------------------------------------------
    # Scenario 1: Empty Queue (No human action taken)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 1: Empty Queue (No Crashing)")
    setup_clean_state(queue_file, cal_file)
    
    # Run harvest on empty queue
    try:
        count = store.harvest_new_examples()
        if count == 0:
            print("  ✅ PASS: Harvested 0 examples safely without crashing.")
            passed += 1
        else:
            print(f"  ❌ FAIL: Expected 0, got {count}")
    except Exception as e:
        print(f"  ❌ FAIL: System crashed on empty queue. Error: {e}")

    # -------------------------------------------------------------------------
    # Scenario 2: Malformed Reports (Missing fields)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 2: Malformed Risk Reports (Missing scores)")
    setup_clean_state(queue_file, cal_file)
    
    malformed_items = [
        # Missing risk_report entirely
        {"timestamp": "2026-08-28T12:00:00Z", "metadata": {"human_verdict": "confirm_risk"}},
        # Missing checker_results
        {"timestamp": "2026-08-28T12:00:01Z", "metadata": {"human_verdict": "confirm_risk"}, "risk_report": {}},
        # Missing risk_score inside checker_result
        {"timestamp": "2026-08-28T12:00:02Z", "metadata": {"human_verdict": "confirm_risk"}, 
         "risk_report": {"checker_results": [{"checker_name": "safety"}]}}
    ]
    write_queue_items(queue_file, malformed_items)
    
    try:
        count = store.harvest_new_examples()
        if count == 0:
            print("  ✅ PASS: Safely ignored malformed records without crashing.")
            passed += 1
        else:
            print(f"  ❌ FAIL: Expected 0 harvested, got {count}.")
    except Exception as e:
        print(f"  ❌ FAIL: System crashed on malformed records. Error: {e}")

    # -------------------------------------------------------------------------
    # Scenario 3: Deduplication (Running harvest twice)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 3: Deduplication (Idempotency check)")
    setup_clean_state(queue_file, cal_file)
    
    valid_item = {
        "timestamp": "2026-08-28T12:00:05Z", 
        "metadata": {"human_verdict": "confirm_risk"},
        "risk_report": {
            "checker_results": [{"checker_name": "performance", "risk_score": 0.99}]
        }
    }
    
    # Write the item multiple times to simulate human clicking twice, or queue duplicates
    write_queue_items(queue_file, [valid_item, valid_item, valid_item])
    
    # Harvest Pass 1
    count1 = store.harvest_new_examples()
    # Harvest Pass 2 (should be 0 since it's already in calibration_set.jsonl)
    count2 = store.harvest_new_examples()
    
    if count1 == 1 and count2 == 0:
        print("  ✅ PASS: Correctly deduped duplicate timestamps.")
        passed += 1
    else:
        print(f"  ❌ FAIL: Expected 1 then 0. Got {count1} then {count2}.")

    # -------------------------------------------------------------------------
    # Scenario 4: "override_allow" Verdict Handling
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 4: Ignoring 'override_allow' (False Positives)")
    setup_clean_state(queue_file, cal_file)
    
    override_items = [
        {
            "timestamp": "2026-08-28T12:00:10Z", 
            "metadata": {"human_verdict": "override_allow"}, # Human said "this is actually safe"
            "risk_report": {"checker_results": [{"checker_name": "safety", "risk_score": 0.99}]}
        }
    ]
    write_queue_items(queue_file, override_items)
    
    count = store.harvest_new_examples()
    if count == 0:
        print("  ✅ PASS: Correctly ignored 'override_allow' so we don't pollute the known-bad distribution.")
        passed += 1
    else:
        print(f"  ❌ FAIL: Falsely harvested an 'override_allow'. Expected 0, got {count}.")

    # -------------------------------------------------------------------------
    # Scenario 5: Full Recalibration Wrapper Execution Safety
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 5: Recalibration Wrapper (End-to-End Safety)")
    setup_clean_state(queue_file, cal_file)
    
    # We will trigger the recalibrate script, which should output "No new examples" and exit cleanly
    try:
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            run_recalibration()
        out = f.getvalue()
        
        if "Skipping recalibration" in out:
            print("  ✅ PASS: Recalibration wrapper safely skipped without crashing.")
            passed += 1
        else:
            print("  ❌ FAIL: Recalibration wrapper attempted to run on empty data.")
    except Exception as e:
        print(f"  ❌ FAIL: Recalibration wrapper crashed. Error: {e}")

    print_header(f"Active Learning Edge Case Summary: {passed}/{total} Passed")

if __name__ == "__main__":
    main()
