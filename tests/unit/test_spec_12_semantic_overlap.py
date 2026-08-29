import pytest
from src.engine.semantic_overlap import SemanticOverlapDetector
from src.policy.schemas import FlaggedSpan
from src.engine.embedding_registry import EmbeddingRegistry

@pytest.fixture(scope="module")
def overlap_detector():
    embedder = EmbeddingRegistry.get_embedder()
    return SemanticOverlapDetector(embedder)

def test_positional_overlap(overlap_detector):
    """Test that two spans with high char IoU but different semantics are still clustered (fallback)"""
    # Create two spans that completely overlap in chars, even if text is different
    spans = [
        FlaggedSpan(
            checker_name="performance",
            text="The treaty was signed in 1994.",
            char_start=0,
            char_end=30,
            risk_score=0.5,
            risk_reason="hallucination"
        ),
        FlaggedSpan(
            checker_name="pii",
            text="John Smith signed the paper.",
            char_start=0,
            char_end=30,  # Same character bounding box
            risk_score=0.5,
            risk_reason="PERSON"
        )
    ]
    
    # Run with very high cosine threshold so it fails semantic pass, but passes positional pass
    groups = overlap_detector.find_overlaps(spans, char_iou_threshold=0.3, cosine_threshold=0.99)
    
    assert len(groups) == 1, "Should find 1 overlap group due to positional char IoU"
    group = groups[0]
    assert len(group.spans) == 2
    # Noisy-OR: 1 - (1 - 0.5) * (1 - 0.5) = 1 - 0.25 = 0.75
    assert group.aggregated_risk == 0.75

def test_semantic_overlap_different_sentences(overlap_detector):
    """Test the core capability: two spans with 0 char overlap but high semantic similarity are clustered."""
    spans = [
        FlaggedSpan(
            checker_name="performance",
            text="The treaty was signed by John Whitfield in 1994.",
            char_start=0,
            char_end=48,
            risk_score=0.5,
            risk_reason="hallucination"
        ),
        FlaggedSpan(
            checker_name="pii",
            text="John Whitfield signed the 1994 agreement.",
            char_start=200, # Completely different location
            char_end=241,
            risk_score=0.6,
            risk_reason="PERSON"
        )
    ]

    # Run with high char_iou so it fails positional pass, but passes semantic pass
    groups = overlap_detector.find_overlaps(spans, char_iou_threshold=0.99, cosine_threshold=0.60)
    
    assert len(groups) == 1, "Should find 1 overlap group due to semantic embedding similarity"
    group = groups[0]
    assert len(group.spans) == 2
    # Noisy-OR: 1 - (1 - 0.5) * (1 - 0.6) = 1 - 0.2 = 0.8
    assert group.aggregated_risk == 0.8

def test_no_overlap_unrelated(overlap_detector):
    """Test that unrelated spans with no char overlap and low semantic similarity are not clustered."""
    spans = [
        FlaggedSpan(
            checker_name="performance",
            text="The treaty was signed in 1994.",
            char_start=0,
            char_end=30,
            risk_score=0.5,
            risk_reason="hallucination"
        ),
        FlaggedSpan(
            checker_name="safety",
            text="I will hack into the mainframe.",
            char_start=200,
            char_end=231,
            risk_score=0.9,
            risk_reason="safety_violation"
        )
    ]
    
    groups = overlap_detector.find_overlaps(spans, char_iou_threshold=0.3, cosine_threshold=0.62)
    
    assert len(groups) == 0, "Should find 0 overlap groups for unrelated sentences"

def test_same_checker_not_grouped(overlap_detector):
    """Test that two spans from the exact same checker are not grouped together (to prevent self-amplification)"""
    spans = [
        FlaggedSpan(
            checker_name="pii",
            text="John Whitfield",
            char_start=0,
            char_end=14,
            risk_score=0.6,
            risk_reason="PERSON"
        ),
        FlaggedSpan(
            checker_name="pii",
            text="John Whitfield",
            char_start=0,
            char_end=14,
            risk_score=0.6,
            risk_reason="PERSON"
        )
    ]
    
    groups = overlap_detector.find_overlaps(spans, char_iou_threshold=0.3, cosine_threshold=0.62)
    assert len(groups) == 0, "Should not group identical checkers to prevent self-escalation"

def test_noisy_or_3_way(overlap_detector):
    """Test that Noisy-OR correctly aggregates 3 overlapping spans from different checkers."""
    spans = [
        FlaggedSpan(checker_name="performance", text="Shared text", char_start=0, char_end=11, risk_score=0.4, risk_reason="hallucination"),
        FlaggedSpan(checker_name="pii", text="Shared text", char_start=0, char_end=11, risk_score=0.5, risk_reason="PERSON"),
        FlaggedSpan(checker_name="safety", text="Shared text", char_start=0, char_end=11, risk_score=0.6, risk_reason="safety_violation")
    ]
    groups = overlap_detector.find_overlaps(spans, char_iou_threshold=0.3, cosine_threshold=0.99)
    assert len(groups) == 1, "Should find 1 overlap group containing all 3 spans"
    group = groups[0]
    assert len(group.spans) == 3
    # Noisy-OR: 1 - (1 - 0.4) * (1 - 0.5) * (1 - 0.6) = 1 - (0.6 * 0.5 * 0.4) = 1 - 0.12 = 0.88
    assert group.aggregated_risk == 0.88
