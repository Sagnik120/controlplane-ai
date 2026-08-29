import pytest
import os
import json
import asyncio
from datetime import datetime
from src.policy.adaptive_calibration import AdaptiveCalibrator
from src.feedback.feedback_consumer import FeedbackConsumer

@pytest.fixture
def mock_calibrator():
    calibrator = AdaptiveCalibrator(step_size=0.05, min_alpha=0.01, max_alpha=0.5)
    # Clear out any previous state to ensure clean test
    calibrator.alphas = {}
    calibrator.alphas_target = {}
    calibrator.active_thresholds = {}
    return calibrator

def test_aci_update_equation_exact(mock_calibrator):
    """
    Test that AdaptiveCalibrator.update matches the ACI equation exactly:
    alpha_new = alpha_t + gamma * (target - I[was_miscovered])
    """
    use_case = "test_bot"
    dim = "safety"
    target = 0.05
    gamma = 0.05
    
    # Initialize
    mock_calibrator.alphas[(use_case, dim)] = target
    mock_calibrator.alphas_target[(use_case, dim)] = target
    
    # 1. Coverage (was_miscovered=False) -> I=0
    # Expected: 0.05 + 0.05 * (0.05 - 0) = 0.0525
    mock_calibrator.update(use_case, dim, was_miscovered=False)
    assert abs(mock_calibrator.alphas[(use_case, dim)] - 0.0525) < 1e-6
    
    # 2. Miscoverage (was_miscovered=True) -> I=1
    # Expected: 0.0525 + 0.05 * (0.05 - 1) = 0.0525 - 0.0475 = 0.005
    # Wait, 0.005 is below min_alpha (0.01). So it should clip to 0.01!
    mock_calibrator.update(use_case, dim, was_miscovered=True)
    assert mock_calibrator.alphas[(use_case, dim)] == 0.01

def test_aci_floor_ceiling_clipping(mock_calibrator):
    use_case = "test_bot"
    dim = "pii"
    target = 0.05
    mock_calibrator.alphas[(use_case, dim)] = target
    mock_calibrator.alphas_target[(use_case, dim)] = target
    
    # Adversarial sequence of overrides (miscoverages) pushing alpha down to the floor
    for _ in range(10):
        mock_calibrator.update(use_case, dim, was_miscovered=True)
        
    assert mock_calibrator.alphas[(use_case, dim)] == mock_calibrator.min_alpha
    
    # Adversarial sequence of likes (coverages) pushing alpha up to the ceiling
    for _ in range(300):
        mock_calibrator.update(use_case, dim, was_miscovered=False)
        
    assert mock_calibrator.alphas[(use_case, dim)] == mock_calibrator.max_alpha

def test_abstain_excluded_from_update(mock_calibrator):
    use_case = "test_bot"
    dim = "bias"
    target = 0.05
    mock_calibrator.alphas[(use_case, dim)] = target
    mock_calibrator.alphas_target[(use_case, dim)] = target
    
    consumer = FeedbackConsumer(calibrator=mock_calibrator)
    
    # Simulated queue entry for abstain
    abstain_entry = {
        "metadata": {
            "human_verdict": "abstain",
            "use_case": use_case,
            "triggering_dimension": dim
        }
    }
    
    consumer._process_entry(abstain_entry)
    
    # Should not have moved
    assert mock_calibrator.alphas[(use_case, dim)] == target

@pytest.mark.anyio
async def test_feedback_consumer_integration(mock_calibrator, tmp_path):
    use_case = "test_bot"
    dim = "performance"
    target = 0.05
    mock_calibrator.alphas[(use_case, dim)] = target
    mock_calibrator.alphas_target[(use_case, dim)] = target
    
    consumer = FeedbackConsumer(calibrator=mock_calibrator)
    # Point consumer to temporary file
    queue_file = tmp_path / "human_review_queue.jsonl"
    consumer.queue_file = str(queue_file)
    
    # Write an initial line
    with open(queue_file, "w") as f:
        f.write("{}\n")
        
    consumer.last_processed_line = 1
    
    task = asyncio.create_task(consumer.start())
    
    # Wait for consumer to start
    await asyncio.sleep(0.1)
    
    # Write an override
    override_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metadata": {
            "human_verdict": "override",
            "use_case": use_case,
            "triggering_dimension": dim
        }
    }
    
    with open(queue_file, "a") as f:
        f.write(json.dumps(override_entry) + "\n")
        
    # Wait for consumer to poll and process (default sleep is 2s, we wait 2.5s)
    await asyncio.sleep(2.5)
    
    # Alpha should have dropped to min_alpha (since 0.05 - 0.0475 = 0.0025 < 0.01)
    assert mock_calibrator.alphas[(use_case, dim)] == mock_calibrator.min_alpha
    
    await consumer.stop()
