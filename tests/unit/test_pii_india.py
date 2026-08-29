import pytest
from src.checkers.pii_checker import PiiChecker
from src.policy.schemas import UseCasePolicy

def test_india_pan_detection():
    checker = PiiChecker()
    policy = UseCasePolicy(name="india_policy", max_overall_risk=1.0)
    policy.pii_entity_allowlist = ["IN_PAN", "IN_AADHAAR"]
    policy.pii_min_confidence = 0.5
    
    text = "My PAN number for tax filing in India is ABCDE1234F."
    result = checker.evaluate(text, policy=policy)
    
    assert result.risk_score > 0
    assert any(ent["entity_type"] == "IN_PAN" for ent in result.entities)
    assert any("ABCDE1234F" in ent["text"] for ent in result.entities)

def test_india_aadhaar_detection():
    checker = PiiChecker()
    policy = UseCasePolicy(name="india_policy", max_overall_risk=1.0)
    policy.pii_entity_allowlist = ["IN_PAN", "IN_AADHAAR"]
    policy.pii_min_confidence = 0.5
    
    text = "My Aadhaar id in India is 1234 5678 9012."
    result = checker.evaluate(text, policy=policy)
    
    assert result.risk_score > 0
    assert any(ent["entity_type"] == "IN_AADHAAR" for ent in result.entities)
    assert any("1234 5678 9012" in ent["text"] for ent in result.entities)
