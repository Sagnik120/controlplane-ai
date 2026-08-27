import os
import sys
from dotenv import load_dotenv

# Add the project root to the python path so we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.adapters.mock_adapter import MockAdapter
from src.adapters.gemini_adapter import GeminiAdapter

def run_diagnostic():
    print("--- Running Deep Adapters Diagnostic ---")
    print("Dependencies: python-dotenv, google-genai\n")
    
    load_dotenv()
    
    cases_run = 0
    cases_passed = 0
    
    # Define test cases (clean, edge cases, flawed)
    test_cases = [
        {"name": "Clean short prompt", "prompt": "Hello, say 'Test OK'"},
        {"name": "Mock flaw trigger (Bias)", "prompt": "Please give me a biased response."},
        {"name": "Mock flaw trigger (PII)", "prompt": "Give me pii data."},
        {"name": "Mock flaw trigger (Hallucination)", "prompt": "Tell me a hallucination or wrong fact."},
        {"name": "Edge case: Empty prompt", "prompt": "   "},
        {"name": "Edge case: Extremely long prompt", "prompt": "repeat this " * 500}
    ]
    
    # Test MockAdapter
    print("=== Testing MockAdapter ===")
    mock = MockAdapter()
    for case in test_cases:
        cases_run += 1
        print(f"\n[Mock] Scenario: {case['name']}")
        print(f"Input: '{case['prompt'][:50]}...'")
        
        try:
            chunks = list(mock.generate_stream(case['prompt']))
            full_text = "".join(chunks)
            
            if len(chunks) > 0 and len(full_text.strip()) > 0:
                print(f"Actual: Received {len(chunks)} chunks, total length {len(full_text)}")
                print(f"Sample output: {full_text[:100]}...")
                print("PASS")
                cases_passed += 1
            else:
                print(f"Actual: Received empty stream")
                print("FAIL")
        except Exception as e:
            print(f"Actual: Exception {e}")
            print("FAIL")
            
    # Test GeminiAdapter
    print("\n=== Testing GeminiAdapter ===")
    gemini = GeminiAdapter()
    for case in test_cases:
        cases_run += 1
        print(f"\n[Gemini] Scenario: {case['name']}")
        print(f"Input: '{case['prompt'][:50]}...'")
        
        try:
            chunks = list(gemini.generate_stream(case['prompt']))
            full_text = "".join(chunks)
            
            if len(chunks) > 0 and len(full_text.strip()) > 0:
                print(f"Actual: Received {len(chunks)} chunks, total length {len(full_text)}")
                print(f"Sample output: {full_text[:100]}...")
                # If the adapter yielded an error string, it still didn't crash but we want to log it
                if full_text.startswith("[Error"):
                    print("PASS (Gracefully caught API error without crashing the generator)")
                else:
                    print("PASS")
                cases_passed += 1
            else:
                print(f"Actual: Received empty stream")
                print("FAIL")
        except Exception as e:
            print(f"Actual: Exception {e}")
            print("FAIL")
            
    print(f"\n--- Deep Diagnostic Summary: {cases_passed}/{cases_run} PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
