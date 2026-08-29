import json
import os
from datetime import datetime
from typing import Dict, Any

from src.engine.risk_engine import FinalRiskReport
from src.policy.schemas import ControlDecision, ActionDecision

class AuditLogger:
    """
    Local JSON-based logger for persisting AI risk decisions.
    In a real environment, this would push to Elasticsearch, Datadog, or Postgres.
    """
    
    def __init__(self, log_file: str = "data/audit_log.jsonl"):
        # Ensure path is absolute relative to project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        self.log_file = os.path.join(project_root, log_file)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Initialize file if it doesn't exist
        if not os.path.exists(self.log_file):
            with open(self.log_file, "a") as f:
                pass # Just create empty file
                
        self.action_log_file = os.path.join(os.path.dirname(self.log_file), "action_decisions.jsonl")
        if not os.path.exists(self.action_log_file):
            with open(self.action_log_file, "a") as f:
                pass
                
    def log(self, response_text: str, report: FinalRiskReport, decision: ControlDecision, metadata: Dict[str, Any] = None, action_decision: ActionDecision = None) -> bool:
        try:
            # We must convert Pydantic models to serializable dicts
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "original_response_length": len(response_text),
                "risk_report": report.model_dump(),
                "control_decision": decision.model_dump(),
                "metadata": metadata or {}
            }
            
            # Open in append mode (O(1) time complexity) for massive performance boost
            with open(self.log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
            # Spec 03: If escalated to HUMAN, append to review queue
            if decision.action == "HUMAN":
                queue_file = os.path.join(os.path.dirname(self.log_file), "human_review_queue.jsonl")
                with open(queue_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
                    
            if action_decision:
                action_log_entry = {
                    "timestamp": log_entry["timestamp"],
                    "action_decision": action_decision.model_dump(),
                    "metadata": metadata or {}
                }
                with open(self.action_log_file, "a") as f:
                    f.write(json.dumps(action_log_entry) + "\n")
                
            return True
            
        except Exception as e:
            print(f"[AuditLogger Error] Failed to write to log: {str(e)}")
            # In a production system, logging failure might block the request if compliance is strict
            return False
            
    def get_last_entry(self) -> Dict[str, Any]:
        """Utility for diagnostics."""
        try:
            with open(self.log_file, "r") as f:
                lines = f.readlines()
                if lines:
                    return json.loads(lines[-1])
        except:
            pass
        return None
