import asyncio
import os
import json
from src.policy.adaptive_calibration import AdaptiveCalibrator

class FeedbackConsumer:
    """
    Asynchronous consumer that tails human_review_queue.jsonl for new human verdicts,
    and feeds them into the live AdaptiveCalibrator.
    """
    def __init__(self, calibrator: AdaptiveCalibrator):
        self.calibrator = calibrator
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        self.queue_file = os.path.join(project_root, 'data', 'human_review_queue.jsonl')
        self.last_processed_line = 0
        self._running = False
        self._task = None
        
        # Determine current file size on startup to not re-process history
        if os.path.exists(self.queue_file):
            with open(self.queue_file, 'r') as f:
                self.last_processed_line = sum(1 for _ in f)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self):
        while self._running:
            if os.path.exists(self.queue_file):
                lines_read = 0
                new_entries = []
                with open(self.queue_file, 'r') as f:
                    for i, line in enumerate(f):
                        if i >= self.last_processed_line:
                            if line.strip():
                                try:
                                    entry = json.loads(line)
                                    new_entries.append(entry)
                                except json.JSONDecodeError:
                                    pass
                            lines_read += 1
                            
                self.last_processed_line += lines_read
                
                for entry in new_entries:
                    self._process_entry(entry)
                    
            await asyncio.sleep(2.0) # Poll every 2 seconds

    def _process_entry(self, entry):
        metadata = entry.get("metadata", {})
        verdict = metadata.get("human_verdict")
        use_case = metadata.get("use_case")
        triggering_dim = metadata.get("triggering_dimension")
        
        # Taxonomy: like, override, abstain
        if verdict in ["like", "override"] and use_case and triggering_dim:
            was_miscovered = (verdict == "override")
            # Feed into ACI calibrator
            self.calibrator.update(use_case, triggering_dim, was_miscovered)
