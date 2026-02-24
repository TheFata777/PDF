import time
from celery import Celery
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Document, TextChunk
from app.services.pdf_processor import extract_text_chunks
#from app.ml.model import compute_embedding
import logging
from app.core.logging_config import setup_logging
logger = logging.getLogger(__name__)
setup_logging()

celery_app = Celery(__name__, broker=settings.redis_url)

@celery_app.task
def process_pdf(document_id: int, file_path: str):
    db = SessionLocal()
    doc = None
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return

        doc.status = "processing"
        db.commit()
        logger.info(f"Started processing document {document_id}: {doc.filename}")

        chunks_data = extract_text_chunks(file_path)

        for chunk in chunks_data:
            # Вычисляем эмбеддинг для текста чанка
            #embedding = compute_embedding(chunk["content"])
            db_chunk = TextChunk(
                document_id=document_id,
                page_number=chunk["page_number"],
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                embedding=None
            )
            db.add(db_chunk)
        db.commit()

        doc.status = "completed"
        db.commit()
        logger.info(f"Completed processing document {document_id}, chunks: {len(chunks_data)}")

    except Exception as e:
        logger.exception(f"Error processing document {document_id}: {e}")
        if doc:
            doc.status = "error"
            db.commit()
    finally:
        db.close()