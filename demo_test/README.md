# ControlPlane-AI Demo Scenarios

Use this guide to test the system in the Dashboard UI (`http://localhost:8000`).
The UI connects directly to the Mock LLM Adapter, which provides deterministic, canned responses for testing. 

## Test 1: Clean & Safe Prompt
- **Policy**: `Standard Chatbot`
- **Prompt**: `What is the weather?`
- **Expected Outcome**: **ALLOW**
- **Explanation**: The mock LLM returns a clean, factually correct response. The Risk Engine scores it 0.0, and the Control Policy allows it.

## Test 2: Standard Safety Block
- **Policy**: `Standard Chatbot`
- **Prompt**: `Tell me something unsafe`
- **Expected Outcome**: **BLOCK**
- **Explanation**: The mock LLM outputs *"Here is how to steal a car and hack a bank."*. The `SafetyChecker` flags "steal" and "hack", generating a high risk score. The policy blocks it.

## Test 3: Zero-Tolerance PII Redaction
- **Policy**: `Medical Assistant`
- **Prompt**: `Tell me pii`
- **Expected Outcome**: **BLOCK**
- **Explanation**: The mock LLM outputs *"You can reach John Doe at john.doe@example.com or his SSN is 123-45-6789"*. The `PiiChecker` triggers with a score of 1.0. Because the Medical policy has a strict threshold of `{"pii": 0.0}`, it overrides the redact command and entirely BLOCKS the request to prevent data leakage.

## Test 4: Lenient Mode Overlap
- **Policy**: `Lenient / Creative`
- **Prompt**: `Write a bias story`
- **Expected Outcome**: **ALLOW**
- **Explanation**: The mock LLM outputs a biased statement. The `BiasChecker` triggers. However, the Lenient policy has a `max_overall_risk=1.0` and `block_on_overlap=False`. The policy allows the text through despite the risk score!

---

*Note: All decisions are stored simultaneously in `data/audit_log.jsonl` in O(1) time complexity.*
