import sys
import os
import time

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.checkers.pii_checker import PiiChecker
from src.policy.schemas import UseCasePolicy

def print_header(title):
    print("\n" + "="*80)
    print(f"🔒 {title}")
    print("="*80)

def main():
    print_header("Initializing Hybrid Presidio PII Checker (Deep Real-World Diagnostics)...")
    start_init = time.time()
    checker = PiiChecker()
    init_time = time.time() - start_init
    print(f"✅ Initialization Complete in {init_time:.2f} seconds!")
    
    # Policy 1: Customer Support (Strict - catches almost everything)
    policy_customer = UseCasePolicy(
        name="customer_support",
        pii_entity_allowlist=["EMAIL", "EMAIL_ADDRESS", "PHONE_NUMBER", "PHONE", "CREDIT_CARD", "SSN", "US_SSN", "PERSON", "LOCATION"],
        pii_min_confidence=0.6  # Standard customer-facing threshold
    )

    # Policy 2: Internal Assistant (Loose - allows internal employee names/locations, flags critical data)
    policy_internal = UseCasePolicy(
        name="internal_assistant",
        pii_entity_allowlist=["SSN", "US_SSN", "CREDIT_CARD", "PASSWORD"],
        pii_min_confidence=0.75
    )

    test_cases = [
        # 1. False Positive Resistance
        {
            "name": "False Positive Resistance (Non-PII ID)",
            "text": "The router issue was logged under ticket number 892-41-9921.",
            "policy": policy_customer,
            "expected_flag": False,
            "desc": "Similar structure to SSN but missing context words. Should NOT be flagged if context boosting is working correctly, or at least low confidence."
        },
        # 2. Obfuscated PII WITHOUT context (Should fail to reach threshold)
        {
            "name": "Obfuscated PII (Missing Context)",
            "text": "Hey, here is 5 five 5 one two 3 four 5 six 7. See you.",
            "policy": policy_customer,
            "expected_flag": False,
            "desc": "Has obfuscated digits but no 'phone' or 'number' context. Base score is 0.2, should NOT cross 0.5 threshold."
        },
        # 3. Policy Switching (Internal vs External)
        {
            "name": "Policy Switch: Internal (Allows Names)",
            "text": "Project Phoenix is being led by Sagnik Chandra in the New York office.",
            "policy": policy_internal,
            "expected_flag": False,
            "desc": "Internal policy excludes PERSON and LOCATION from the allowlist."
        },
        {
            "name": "Policy Switch: External (Flags Names)",
            "text": "Project Phoenix is being led by Sagnik Chandra in the New York office.",
            "policy": policy_customer,
            "expected_flag": True,
            "desc": "External policy INCLUDES PERSON and LOCATION, so it should flag."
        },
        # 4. Multi-Entity Noisy OR Aggregation
        {
            "name": "Multiple Medium-Confidence Hits",
            "text": "Send the package to Jane. Also contact 555-0199 for billing issues.",
            "policy": policy_customer,
            "expected_flag": True,
            "desc": "Should detect PERSON and PHONE_NUMBER. The aggregated risk score should be higher than the max individual score."
        },
        # 5. Multilingual / Foreign Names
        {
            "name": "Foreign Names / Diverse Entities",
            "text": "Monsieur Guillaume Dubois will be arriving from Paris. Email him at g.dubois@entreprise.fr.",
            "policy": policy_customer,
            "expected_flag": True,
            "desc": "Transformer NER should easily catch non-English names and locations."
        },
        # 6. Stress Test / Long Document
        {
            "name": "Stress Test (Long Document with scattered PII)",
            "text": "We are reviewing the Q3 earnings. " * 50 + " Oh, by the way, John's SSN is 000-12-3456. " + "We need to ensure compliance. " * 50,
            "policy": policy_customer,
            "expected_flag": True,
            "desc": "Ensures the checker doesn't time out or truncate long texts before finding the hidden PII."
        }
    ]

    print_header("Running Deep Diagnostics")
    
    passed = 0
    total = len(test_cases)

    for case in test_cases:
        print(f"\n▶️ Running: {case['name']}")
        print(f"  Description: {case['desc']}")
        # Truncate text for display if too long
        display_text = case['text'] if len(case['text']) < 100 else case['text'][:100] + "..."
        print(f"  Text: '{display_text}'")
        
        start_eval = time.time()
        result = checker.evaluate(case['text'], policy=case['policy'])
        eval_time = time.time() - start_eval
        
        print(f"  Eval Time: {eval_time:.4f} seconds")
        print(f"  Risk Score: {result.risk_score}")
        
        if result.risk_score > 0:
            print("  Detected Entities:")
            for ent in result.entities:
                print(f"    - Type: {ent['entity_type']} | Text: '{ent['text']}' | Confidence: {ent['confidence']:.2f}")
                
        is_flagged = result.risk_score > 0
        
        if is_flagged == case['expected_flag']:
            print("  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL (Expected flagged={case['expected_flag']}, got {is_flagged})")

    print_header(f"Diagnostic Summary: {passed}/{total} Passed")
    if passed == total:
        print("🎉 ALL EDGE CASES PASSED! The hybrid pipeline is robust and policy-aware.")
    else:
        print("⚠️ SOME TESTS FAILED. Review the edge cases above.")

if __name__ == "__main__":
    main()
