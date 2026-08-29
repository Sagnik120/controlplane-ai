import json
import os
from typing import Dict, Any, List

class FeedbackStore:
    def __init__(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        self.queue_file = os.path.join(project_root, 'data', 'human_review_queue.jsonl')
        self.calibration_file = os.path.join(project_root, 'data', 'calibration_set.jsonl')
        
    def _read_jsonl(self, filepath: str) -> List[Dict[str, Any]]:
        data = []
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        return data
        
    def harvest_new_examples(self) -> int:
        """
        Reads human_review_queue.jsonl. Extracts items marked with human_verdict="confirm_risk",
        adds them to calibration_set.jsonl if they aren't already there.
        Returns the number of freshly harvested examples.
        """
        queue_data = self._read_jsonl(self.queue_file)
        existing_cal_data = self._read_jsonl(self.calibration_file)
        
        # Dedupe set by timestamp for this prototype
        existing_timestamps = {item.get('timestamp') for item in existing_cal_data if item.get('timestamp')}
        
        new_examples = []
        for item in queue_data:
            verdict = item.get("metadata", {}).get("human_verdict")
            ts = item.get("timestamp")
            
            # We only append confirmed risks to the known-bad distribution.
            # In the NPO taxonomy, a "like" on an escalation means the human confirms it was indeed a risk.
            if verdict == "like" and ts not in existing_timestamps:
                # Extract risk scores directly from the report
                report = item.get("risk_report", {})
                checker_results = report.get("checker_results", [])
                
                scores = {}
                for cr in checker_results:
                    if "checker_name" in cr and "risk_score" in cr:
                        name = cr["checker_name"]
                        if name in ["performance", "safety", "bias", "pii"]:
                            scores[name] = cr["risk_score"]
                
                # If we got valid scores, format as a calibration example
                if scores:
                    example = {
                        "timestamp": ts,
                        "source": "human_feedback",
                        "scores": scores
                    }
                    new_examples.append(example)
                    existing_timestamps.add(ts)
                    
        if new_examples:
            os.makedirs(os.path.dirname(self.calibration_file), exist_ok=True)
            with open(self.calibration_file, 'a') as f:
                for ex in new_examples:
                    f.write(json.dumps(ex) + "\n")
                    
        return len(new_examples)
