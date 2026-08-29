import pytest
from src.checkers.safety_checker import SafetyChecker
from src.checkers.base import CheckerResult
from unittest.mock import MagicMock

def test_checker_api_failure_handling():
    # Setup checker
    checker = SafetyChecker()
    
    # Mock adapter to raise an exception simulating API 404
    mock_adapter = MagicMock()
    mock_adapter.generate_once.side_effect = Exception("404 NOT_FOUND: Model no longer available")
    
    context = {
        "adapter": mock_adapter,
        "safety_flagged_span": None
    }
    
    # Run tier 1 explicitly
    result = checker.tier1_check("Some input text", context)
    
    # Verify the error was trapped gracefully and is_error flag is set
    assert isinstance(result, CheckerResult)
    assert result.is_error is True
    assert result.risk_score == 1.0
    assert "Checker failed" in result.explanation
    assert "404 NOT_FOUND" in result.explanation
