import os
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

class EmbeddingRegistry:
    _instance = None
    _model = None

    @classmethod
    def get_embedder(cls):
        if cls._model is None and SentenceTransformer is not None:
            cls._model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        return cls._model
