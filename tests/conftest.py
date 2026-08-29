import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the quota guard plugin to ensure it runs for all test sessions
pytest_plugins = ["tests.gemini_quota_guard"]

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live_gemini: mark test to run against live Gemini API (guarded by quota)"
    )

@pytest.fixture(autouse=True)
def guard_gemini_adapter(monkeypatch):
    from src.adapters.gemini_adapter import GeminiAdapter
    from tests.gemini_quota_guard import guard
    
    orig_generate_once = GeminiAdapter.generate_once
    orig_generate_stream = GeminiAdapter.generate_stream
    
    def wrapped_generate_once(self, *args, **kwargs):
        guard.check_and_increment()
        return orig_generate_once(self, *args, **kwargs)
        
    def wrapped_generate_stream(self, *args, **kwargs):
        guard.check_and_increment()
        return orig_generate_stream(self, *args, **kwargs)
        
    monkeypatch.setattr(GeminiAdapter, "generate_once", wrapped_generate_once)
    monkeypatch.setattr(GeminiAdapter, "generate_stream", wrapped_generate_stream)
