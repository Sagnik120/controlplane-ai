import math
from typing import List, Dict, Any, Optional
import numpy as np
from src.policy.schemas import FlaggedSpan, OverlapGroup

class SemanticOverlapDetector:
    def __init__(self, embedder=None):
        """
        Dynamically gets or reuses the SentenceTransformer to guarantee
        zero startup overhead and zero RAM consumption during server boot.
        """
        self._embedder = embedder

    @property
    def embedder(self):
        if self._embedder is None:
            from src.engine.embedding_registry import EmbeddingRegistry
            self._embedder = EmbeddingRegistry.get_embedder()
        return self._embedder

    def _char_iou(self, span1: FlaggedSpan, span2: FlaggedSpan) -> float:
        # Calculate intersection
        start = max(span1.char_start, span2.char_start)
        end = min(span1.char_end, span2.char_end)
        intersection = max(0, end - start)
        
        # Calculate union
        union = (span1.char_end - span1.char_start) + (span2.char_end - span2.char_start) - intersection
        if union == 0:
            return 0.0
            
        return intersection / union

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def find_overlaps(self, spans: List[FlaggedSpan], 
                     char_iou_threshold: float = 0.3,
                     cosine_threshold: float = 0.62) -> List[OverlapGroup]:
        if not spans:
            return []

        # We will build an adjacency list for related spans
        n = len(spans)
        adj = {i: set() for i in range(n)}

        # 1. Positional Pass (Cheap)
        for i in range(n):
            for j in range(i + 1, n):
                # Don't overlap spans from the exact same checker
                if spans[i].checker_name == spans[j].checker_name:
                    continue
                iou = self._char_iou(spans[i], spans[j])
                if iou >= char_iou_threshold:
                    adj[i].add(j)
                    adj[j].add(i)

        # 2. Semantic Pass (Batch Embedding)
        if self.embedder:
            texts_to_embed = []
            indices_to_embed = []
            for i, span in enumerate(spans):
                if span.embedding is None:
                    texts_to_embed.append(span.text)
                    indices_to_embed.append(i)

            if texts_to_embed:
                embeddings = self.embedder.encode(texts_to_embed, batch_size=32).tolist()
                for i, emb in zip(indices_to_embed, embeddings):
                    spans[i].embedding = emb

            # Compute pairwise cosine similarity
            for i in range(n):
                for j in range(i + 1, n):
                    if spans[i].checker_name == spans[j].checker_name:
                        continue
                    if j in adj[i]:
                        continue # Already linked positionally
                    
                    if spans[i].embedding and spans[j].embedding:
                        sim = self._cosine_similarity(spans[i].embedding, spans[j].embedding)
                        if sim >= cosine_threshold:
                            adj[i].add(j)
                            adj[j].add(i)

        # Find connected components (Groups of overlapping spans)
        visited = set()
        overlap_groups = []

        for i in range(n):
            if i not in visited and adj[i]: # Only create groups if there's an edge
                comp = []
                queue = [i]
                visited.add(i)
                while queue:
                    curr = queue.pop(0)
                    comp.append(spans[curr])
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                
                # We have a component of related spans
                if len(comp) > 1:
                    # Noisy-OR Escalation
                    individual_risks = [s.risk_score for s in comp]
                    prob_safe = 1.0
                    for r in individual_risks:
                        prob_safe *= (1.0 - r)
                    aggregated_risk = 1.0 - prob_safe
                    
                    overlap_groups.append(OverlapGroup(
                        spans=comp,
                        aggregated_risk=round(aggregated_risk, 3),
                        multiplier_applied=1.0,
                        reason="Semantic or Positional overlap detected"
                    ))
                    
        return overlap_groups
