import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.api.main import app

client = TestClient(app)

def run_diagnostic():
    print("--- Running API Layer Diagnostic ---")
    
    # 1. Health Check
    response = client.get("/health")
    if response.status_code == 200 and response.json()["status"] == "ok":
        print("Health Check: PASS")
    else:
        print(f"Health Check: FAIL (Status: {response.status_code}, Body: {response.text})")
        sys.exit(1)
        
    # 2. Get Policies
    response = client.get("/api/policies")
    if response.status_code == 200 and "policies" in response.json():
        print("Policy Retrieval: PASS")
    else:
        print("Policy Retrieval: FAIL")
        sys.exit(1)
        
    # 3. Test Standard Chat Endpoint (using mock)
    # The API is currently wired to GeminiAdapter in dependencies.py
    # To run this in CI without API keys, we would patch the dependency, 
    # but since this diagnostic is run by the user, we can let it hit the real API or we can just verify the 400 error logic.
    
    response = client.post("/api/chat", json={
        "prompt": "hello",
        "policy_id": "invalid_policy_id"
    })
    
    if response.status_code == 400:
        print("Invalid Policy ID Handling: PASS")
    else:
        print("Invalid Policy ID Handling: FAIL")
        sys.exit(1)
        
    # 4. Test Valid Chat Endpoint (using mock)
    response = client.post("/api/chat", json={
        "prompt": "clean",
        "policy_id": "standard"
    })
    
    if response.status_code == 200 and "final_output" in response.json():
        print("Valid Chat Processing: PASS")
    else:
        print(f"Valid Chat Processing: FAIL (Status: {response.status_code}, Body: {response.text})")
        sys.exit(1)
        
    print("\n--- Diagnostic Summary: 4/4 PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
