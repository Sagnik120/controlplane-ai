import os
import threading

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

class EmbeddingRegistry:
    _instance = None
    _model = None
    _lock = threading.Lock()

    @classmethod
    def get_embedder(cls):
        if cls._model is None and SentenceTransformer is not None:
            with cls._lock:
                if cls._model is None:
                    cls._model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        return cls._model
