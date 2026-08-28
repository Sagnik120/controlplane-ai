import sys
import os
import json

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.checkers.pii_checker import PiiChecker
from src.policy.schemas import UseCasePolicy

def print_header(title):
    print("\n" + "="*70)
    print(f"🔒 {title}")
    print("="*70)

def main():
    print_header("Initializing Hybrid Presidio PII Checker (this may take a few seconds)...")
    checker = PiiChecker()
    print("✅ Initialization Complete!")
    
    # We'll use the customer support policy which checks for everything
    policy = UseCasePolicy(
        name="test_policy",
        pii_entity_allowlist=["EMAIL", "EMAIL_ADDRESS", "PHONE_NUMBER", "PHONE", "CREDIT_CARD", "SSN", "US_SSN", "PERSON", "LOCATION"],
        pii_min_confidence=0.5
    )

    test_cases = [
        {
            "name": "Clean Text (Low Risk)",
            "text": "The quick brown fox jumps over the lazy dog. Please review the attached document.",
            "expected_flag": False
        },
        {
            "name": "Structured PII (SSN & Email)",
            "text": "You can contact John Doe at john.doe@example.com or his SSN is 123-45-6789.",
            "expected_flag": True
        },
        {
            "name": "Unstructured PII (Person Name & Location)",
            "text": "Sagnik went to the Accenture office in San Francisco.",
            "expected_flag": True
        },
        {
            "name": "Obfuscated PII (Context-Boosted Phone Number)",
            "text": "My phone number is 5 five 5 one two 3 four 5 six 7. Please call me.",
            "expected_flag": True
        }
    ]

    print_header("Running Diagnostics")
    
    for case in test_cases:
        print(f"\n▶️ Running: {case['name']}")
        print(f"  Text: '{case['text']}'")
        
        result = checker.evaluate(case['text'], policy=policy)
        
        print(f"  Risk Score: {result.risk_score}")
        if result.risk_score > 0:
            print(f"  Explanation: {result.explanation}")
            print("  Detected Entities:")
            for ent in result.entities:
                print(f"    - Type: {ent['entity_type']} | Text: '{ent['text']}' | Confidence: {ent['confidence']:.2f}")
                
        is_flagged = result.risk_score > 0
        
        if is_flagged == case['expected_flag']:
            print("  ✅ PASS")
        else:
            print(f"  ❌ FAIL (Expected flagged={case['expected_flag']}, got {is_flagged})")

if __name__ == "__main__":
    main()
