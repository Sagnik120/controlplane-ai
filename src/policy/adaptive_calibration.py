import os
import json
import yaml
import math
from datetime import datetime
from threading import Lock

def get_conformal_quantile(scores, alpha):
    """
    Given a list of calibration scores from *known-bad* examples, 
    compute the conformal prediction quantile threshold for error rate alpha.
    """
    n = len(scores)
    if n == 0:
        return 1.0 # Safe fallback
    sorted_scores = sorted(scores)
    # ⌈(n+1)(1-α)⌉-th smallest score
    idx = math.ceil((n + 1) * (1 - alpha)) - 1
    # Bound the index
    idx = max(0, min(idx, n - 1))
    return sorted_scores[idx]

class AdaptiveCalibrator:
    """
    Live HUMAN Feedback Loop via Adaptive Conformal Inference (ACI).
    Updates alpha target dynamically based on human overrides to shift thresholds.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AdaptiveCalibrator, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, step_size: float = 0.05, min_alpha: float = 0.001, max_alpha: float = 0.5):
        with self._lock:
            if self._initialized:
                return
            self._initialized = True
            
            self.gamma = step_size
            self.min_alpha = min_alpha
            self.max_alpha = max_alpha
            
            # (use_case, dimension) -> current live alpha_high
            self.alphas = {}
            # (use_case, dimension) -> original target alpha_high
            self.alphas_target = {}
            
            # dimension -> list of floats
            self.calibration_data = self._load_calibration_data()
            
            # (use_case, dimension) -> {"tau_low": float, "tau_high": float}
            self.active_thresholds = {}
            
            # (use_case) -> float (since alpha_low isn't driven by HUMAN feedback, we keep it static)
            self.base_alpha_lows = {}
            
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
            self.audit_log_path = os.path.join(project_root, 'data', 'aci_audit_log.jsonl')
            self.config_path = os.path.join(project_root, "configs", "use_case_policies.yaml")
            
            self._init_from_config()

    def _load_calibration_data(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        cal_file = os.path.join(project_root, 'data', 'calibration_set.jsonl')
        
        data = {"performance": [], "safety": [], "bias": [], "pii": []}
        if os.path.exists(cal_file):
            with open(cal_file, 'r') as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        scores = item.get("scores", {})
                        for dim in data.keys():
                            if dim in scores:
                                data[dim].append(scores[dim])
        
        # Fallback seeded data just in case it's empty to prevent math errors
        for dim, scores in data.items():
            if not scores:
                data[dim] = [0.1] * 64
        return data

    def _init_from_config(self):
        with open(self.config_path, "r") as f:
            configs = yaml.safe_load(f)
            
        for use_case, policy in configs.items():
            alpha_low = policy.get("alpha_low", 0.10)
            alpha_high = policy.get("alpha_high", 0.02)
            
            self.base_alpha_lows[use_case] = alpha_low
            
            for dim in self.calibration_data.keys():
                key = (use_case, dim)
                self.alphas_target[key] = alpha_high
                self.alphas[key] = alpha_high
                self._recompute_tau(key)

    def _recompute_tau(self, key):
        """Recompute tau_high and tau_low for a specific use_case and dimension"""
        use_case, dim = key
        alpha_high_live = self.alphas[key]
        alpha_low = self.base_alpha_lows.get(use_case, 0.10)
        
        scores = self.calibration_data.get(dim, [])
        
        tau_low = get_conformal_quantile(scores, alpha_low)
        tau_high = get_conformal_quantile(scores, alpha_high_live)
        
        if tau_low > tau_high:
            tau_low = max(0.0, tau_high - 0.05)
            
        self.active_thresholds[key] = {
            "tau_low": round(tau_low, 3),
            "tau_high": round(tau_high, 3)
        }

    def update(self, use_case: str, risk_dimension: str, was_miscovered: bool):
        """
        Applies the Adaptive Conformal Inference gradient step.
        alpha_t+1 = alpha_t + gamma * (alpha_target - I[was_miscovered])
        """
        key = (use_case, risk_dimension)
        with self._lock:
            # If we don't track this dimension, initialize it safely
            if key not in self.alphas:
                base_high = self.alphas_target.get(key, 0.02)
                self.alphas[key] = base_high
                self.alphas_target[key] = base_high
                
            alpha_t = self.alphas[key]
            target = self.alphas_target[key]
            
            # ACI Update Rule
            alpha_new = alpha_t + self.gamma * (target - int(was_miscovered))
            
            # Safety rails clipping
            alpha_new = max(self.min_alpha, min(alpha_new, self.max_alpha))
            
            self.alphas[key] = alpha_new
            self._recompute_tau(key)
            
            self._log_audit(key, alpha_t, alpha_new, was_miscovered)

    def _log_audit(self, key, old_alpha, new_alpha, was_miscovered):
        use_case, dim = key
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "use_case": use_case,
            "risk_dimension": dim,
            "event": "miscoverage" if was_miscovered else "coverage",
            "old_alpha": old_alpha,
            "new_alpha": new_alpha,
            "active_tau_high": self.active_thresholds[key]["tau_high"]
        }
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_active_thresholds(self, use_case: str, dimension: str) -> dict:
        """Returns the live {"tau_low": float, "tau_high": float} for the dimension."""
        key = (use_case, dimension)
        # Fallback if somehow not initialized
        if key not in self.active_thresholds:
            with self._lock:
                if key not in self.alphas:
                    self.alphas[key] = self.alphas_target.get(key, 0.02)
                    self.alphas_target[key] = self.alphas.get(key, 0.02)
                self._recompute_tau(key)
                
        return self.active_thresholds[key]
