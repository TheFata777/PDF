from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

# Используем мультиязычную модель, подходящую для русского языка
_MODEL = None

def get_model():
    global _MODEL
    if _MODEL is None:
        logger.info("Loading sentence transformer model...")
        _MODEL = SentenceTransformer('distiluse-base-multilingual-cased-v2')
        logger.info("Model loaded.")
    return _MODEL

def compute_embedding(text: str) -> list:
    model = get_model()
    embedding = model.encode(text).tolist()
    return embedding