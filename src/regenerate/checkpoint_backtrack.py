import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.engine.risk_engine import FinalRiskReport
from src.adapters.base_adapter import BaseLLMAdapter
from src.policy.schemas import UseCasePolicy

@dataclass
class Checkpoint:
    turn_id: str
    char_offset: int
    token_offset: int
    risk_snapshot: FinalRiskReport
    prompt_state: str
    timestamp: float

class CheckpointManager:
    def __init__(self):
        self.checkpoints: Dict[str, List[Checkpoint]] = {}

    def commit(self, turn_id: str, char_offset: int, token_offset: int,
               risk_snapshot: FinalRiskReport, prompt_state: str) -> Checkpoint:
        cp = Checkpoint(
            turn_id=turn_id,
            char_offset=char_offset,
            token_offset=token_offset,
            risk_snapshot=risk_snapshot,
            prompt_state=prompt_state,
            timestamp=time.time()
        )
        if turn_id not in self.checkpoints:
            self.checkpoints[turn_id] = []
        self.checkpoints[turn_id].append(cp)
        return cp

    def last_good(self, turn_id: str) -> Optional[Checkpoint]:
        if turn_id in self.checkpoints and self.checkpoints[turn_id]:
            return self.checkpoints[turn_id][-1]
        return None

    def backtrack(self, turn_id: str) -> str:
        """Return the accepted prefix text to resume generation from."""
        cp = self.last_good(turn_id)
        return cp.prompt_state if cp else ""

class RegenerationEngine:
    def __init__(self, adapter: BaseLLMAdapter, checkpoint_mgr: CheckpointManager, retriever=None):
        self.adapter = adapter
        self.checkpoint_mgr = checkpoint_mgr
        self.retriever = retriever

    def _diagnose(self, original_prompt: str, prefix: str, flagged_span: str, risk_reason: str) -> List[str]:
        prompt = f"""SYSTEM: You are a verification assistant. You will be given a PARTIAL response
and the risk signal that flagged it. Generate 2-4 short, independent, checkable
questions that would confirm or refute the flagged concern. Do not answer them.

USER:
Original user request: {original_prompt}
Response so far (accepted, up to checkpoint): {prefix}
Flagged continuation (will be discarded): {flagged_span}
Flagged risk type + evidence: {risk_reason}

Output ONLY the verification questions, one per line."""
        
        # We don't have async generate_once in adapter, so call the sync version
        response = self.adapter.generate_once(prompt, temperature=0.2)
        questions = [q.strip() for q in response.split('\n') if q.strip()]
        return questions

    def _verify(self, questions: List[str]) -> str:
        findings = []
        for q in questions:
            evidence_or_none = "No evidence retrieved."
            prompt = f"""SYSTEM: Answer the following question as accurately and concisely as possible,
using only the provided evidence if any. If you don't know, say so explicitly
rather than guessing.

USER:
Question: {q}
Evidence (if retrieved / from RAG source): {evidence_or_none}"""
            ans = self.adapter.generate_once(prompt, temperature=0.1)
            findings.append(f"Q: {q}\nA: {ans}")
        return "\n".join(findings)

    def _resample(self, original_prompt: str, prefix: str, findings: str, use_case_policy: UseCasePolicy) -> str:
        regen_temp = getattr(use_case_policy, "regenerate_temperature", 0.2)
        
        prompt = f"""SYSTEM: Continue the response below. The prior draft continuation was discarded
because:
{findings}

Do not repeat the discarded content. Stay consistent with everything already
written. If you are not confident about a specific fact, state your uncertainty
explicitly rather than asserting it.

USER:
Original request: {original_prompt}
Accepted response so far: {prefix}
Continue from here:"""
        
        return self.adapter.generate_once(prompt, temperature=regen_temp).strip()

    def regenerate(self, turn_id: str, original_prompt: str, flagged_span: str,
                   risk_reason: str, use_case_policy: UseCasePolicy) -> str:
        prefix = self.checkpoint_mgr.backtrack(turn_id)
        # 1. Diagnose (CoVe step 1)
        questions = self._diagnose(original_prompt, prefix, flagged_span, risk_reason)
        # 2. Verify (CoVe step 2 + RARR)
        findings = self._verify(questions)
        # 3. Resample (CoVe step 3)
        return self._resample(original_prompt, prefix, findings, use_case_policy)
