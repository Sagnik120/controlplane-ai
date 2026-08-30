import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np

from src.engine.embedding_registry import EmbeddingRegistry

class SessionRiskState(BaseModel):
    session_id: str
    turn_count: int = 0
    
    # Semantic drift (TCA)
    initial_intent_embedding: Optional[List[float]] = None
    last_n_turn_embeddings: List[List[float]] = Field(default_factory=list)
    drift_history: List[float] = Field(default_factory=list) # records drift-from-start per turn
    semantic_drift_score: float = 0.0
    
    # Cumulative PII (CAMP Proxy)
    accumulated_pii_entities: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    cumulative_pii_exposure_score: float = 0.0
    
    # General
    per_turn_risk_history: List[Dict[str, Any]] = Field(default_factory=list)
    session_risk_trend: str = "stable"

class SessionStore:
    def __init__(self, embedder=None):
        self.sessions: Dict[str, SessionRiskState] = {}
        self._model = embedder

    @property
    def model(self):
        if self._model is None:
            self._model = EmbeddingRegistry.get_embedder()
        return self._model

    def get_or_create(self, session_id: str) -> SessionRiskState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionRiskState(session_id=session_id)
        return self.sessions[session_id]

    def _cosine_distance(self, vec1: List[float], vec2: List[float]) -> float:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 1.0
        similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return float(1.0 - similarity)

    def update(self, session_id: str, user_text: str, checker_results: List[Any], 
               drift_window: int = 5, require_monotonic: bool = True) -> SessionRiskState:
        state = self.get_or_create(session_id)
        state.turn_count += 1
        
        # 1. Update Semantic Drift (TCA)
        if self.model and user_text.strip():
            emb = self.model.encode(user_text).tolist()
            
            if state.initial_intent_embedding is None:
                state.initial_intent_embedding = emb
                state.drift_history.append(0.0)
            else:
                drift_from_start = self._cosine_distance(emb, state.initial_intent_embedding)
                
                # Check drift from immediate predecessor (TCA's cross-turn intention consistency)
                # If there's a massive jump from the immediate previous turn, it's a harmless topic change
                # (or just random), not a gradual adversarial manipulation.
                is_sudden_jump = False
                if state.last_n_turn_embeddings:
                    drift_from_prev = self._cosine_distance(emb, state.last_n_turn_embeddings[-1])
                    if drift_from_prev > 0.4: # Sudden topic change threshold
                        is_sudden_jump = True
                        
                state.drift_history.append(drift_from_start)
                
                # Check monotonic trend over the window
                window = state.drift_history[-drift_window:]
                if require_monotonic and len(window) >= 3:
                    # It must be strictly increasing, AND not a sudden jump
                    is_increasing = all(window[i] < window[i+1] for i in range(len(window)-1))
                    if is_increasing and not is_sudden_jump:
                        state.semantic_drift_score = max(state.semantic_drift_score, drift_from_start)
                elif not require_monotonic:
                    state.semantic_drift_score = max(state.semantic_drift_score, drift_from_start)
                
            state.last_n_turn_embeddings.append(emb)
            if len(state.last_n_turn_embeddings) > drift_window:
                state.last_n_turn_embeddings.pop(0)

        # 2. Update Cumulative PII Exposure (CAMP)
        for result in checker_results:
            if result.checker_name == "pii":
                # We pull from entities (if they exist) directly
                for ent in getattr(result, "entities", []):
                    etype = ent.get("entity_type", "UNKNOWN")
                    val = ent.get("text", "")
                    
                    if etype not in state.accumulated_pii_entities:
                        state.accumulated_pii_entities[etype] = []
                    
                    # Only append if we haven't seen this exact value before in this session
                    existing_vals = [e["value"] for e in state.accumulated_pii_entities[etype]]
                    if val not in existing_vals:
                        state.accumulated_pii_entities[etype].append({
                            "value": val,
                            "turn_index": state.turn_count,
                            "confidence": ent.get("confidence", 1.0)
                        })
        
        # Calculate Distinct Entity Type Count
        distinct_types = len(state.accumulated_pii_entities)
        state.cumulative_pii_exposure_score = float(distinct_types)
        
        return state
