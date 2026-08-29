import os
import json
import datetime
import pytest

# Configurable limits
MAX_GEMINI_CALLS_PER_RUN = int(os.getenv("GEMINI_TEST_CALL_LIMIT_PER_RUN", "15"))
MAX_GEMINI_CALLS_PER_DAY = int(os.getenv("GEMINI_TEST_CALL_LIMIT_PER_DAY", "50"))

QUOTA_FILE = os.path.join(os.path.dirname(__file__), ".gemini_call_budget.json")

def get_today_str():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

class QuotaGuard:
    def __init__(self):
        self.run_calls = 0
        self.load_state()

    def load_state(self):
        self.today = get_today_str()
        self.day_calls = 0
        if os.path.exists(QUOTA_FILE):
            try:
                with open(QUOTA_FILE, "r") as f:
                    data = json.load(f)
                    if data.get("date") == self.today:
                        self.day_calls = data.get("day_calls", 0)
            except Exception:
                pass

    def save_state(self):
        with open(QUOTA_FILE, "w") as f:
            json.dump({"date": self.today, "day_calls": self.day_calls}, f)

    def check_and_increment(self):
        if self.run_calls >= MAX_GEMINI_CALLS_PER_RUN:
            pytest.skip(f"Gemini quota guard: Per-run limit reached ({MAX_GEMINI_CALLS_PER_RUN})")
        if self.day_calls >= MAX_GEMINI_CALLS_PER_DAY:
            pytest.skip(f"Gemini quota guard: Per-day limit reached ({MAX_GEMINI_CALLS_PER_DAY})")
            
        self.run_calls += 1
        self.day_calls += 1
        self.save_state()

# Global guard instance
guard = QuotaGuard()

@pytest.fixture(autouse=True)
def gemini_quota(request):
    """
    Fixture that automatically checks quota before any test marked with 'live_gemini'.
    """
    if "live_gemini" in request.node.keywords:
        # We don't increment here directly, the adapter mock/patch should increment it
        # However, as a fail-safe, we just check the limits before running.
        if guard.run_calls >= MAX_GEMINI_CALLS_PER_RUN:
            pytest.skip(f"Gemini quota guard: Per-run limit reached")
        if guard.day_calls >= MAX_GEMINI_CALLS_PER_DAY:
            pytest.skip(f"Gemini quota guard: Per-day limit reached")
    yield

def pytest_sessionfinish(session, exitstatus):
    print(f"\nGemini live calls used this run: {guard.run_calls}/{MAX_GEMINI_CALLS_PER_RUN} | today: {guard.day_calls}/{MAX_GEMINI_CALLS_PER_DAY}")
