import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request, Query
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from jose import JWTError, jwt
import yake

from app.api.deps import get_db
from app.core.security import get_current_user
from app.db.models import User, Document, TextChunk
from app.schemas import DocumentOut, DocumentStatus, TextChunkOut
from app.tasks.pdf_tasks import process_pdf
from app.core.config import settings
from collections import Counter
import re

router = APIRouter()
#список стоп-слов
STOP_WORDS = {"и", "в", "на", "с", "по", "для", "а", "но", "или", "из", "у", "к", "о", "об", "за", "от", "до", "без", "над", "под"}

@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Проверка, что файл - PDF
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Создаём директорию для пользователя, если её нет
    user_dir = f"uploads/{current_user.id}"
    os.makedirs(user_dir, exist_ok=True)

    # Генерируем уникальное имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(user_dir, safe_filename)

    # Сохраняем файл
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Получаем размер файла
    file_size = os.path.getsize(file_path)

    # Создаём запись в БД
    db_document = Document(
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        status="pending"
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    # Отправляем задачу в Celery
    process_pdf.delay(db_document.id, file_path)

    return db_document

@router.get("/", response_model=list[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    return documents

@router.get("/{document_id}/status", response_model=DocumentStatus)
def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatus(id=document.id, status=document.status)

@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Находим документ, принадлежащий текущему пользователю
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Удаляем файл с диска, если он существует
    file_path = document.file_path
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            # Логируем ошибку
            print(f"Error deleting file {file_path}: {e}")

    # Удаляем запись из БД
    db.delete(document)
    db.commit()

    return None  # 204 No Content

@router.get("/{document_id}/file")
def get_pdf_file(
    request: Request,
    document_id: int,
    token: str = Query(None, description="JWT token (alternative to Authorization header)"),
    db: Session = Depends(get_db)
):
    """Возвращает PDF-файл для просмотра/скачивания"""
    # Получаем токен
    auth_header = request.headers.get("Authorization")
    if token:
        token_to_use = token
    elif auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header.split(" ")[1]
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Проверяем токен и получаем user_id
    try:
        payload = jwt.decode(token_to_use, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = document.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        filename=document.filename,
        media_type='application/pdf'
    )


@router.get("/{document_id}/text", response_model=list[TextChunkOut])
def get_document_text(
    request: Request,
    document_id: int,
    token: str = Query(None, description="JWT token (alternative to Authorization header)"),
    db: Session = Depends(get_db)
):
    """Возвращает все чанки текста документа"""
    # Получаем токен
    auth_header = request.headers.get("Authorization")
    if token:
        token_to_use = token
    elif auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header.split(" ")[1]
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token_to_use, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(TextChunk).filter(
        TextChunk.document_id == document_id
    ).order_by(TextChunk.page_number, TextChunk.chunk_index).all()
    return chunks

@router.get("/{document_id}/keywords")
def get_document_keywords(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Собираем весь текст документа из чанков
    chunks = db.query(TextChunk).filter(TextChunk.document_id == document_id).all()
    full_text = "\n".join([chunk.content for chunk in chunks])
    if not full_text.strip():
        return {"keywords": []}

    # Настройки YAKE (можно экспериментировать)
    kw_extractor = yake.KeywordExtractor(lan="ru", top=20, n=2, dedupLim=0.9)
    keywords = kw_extractor.extract_keywords(full_text)
    # keywords - список кортежей (слово, релевантность)
    result = [{"keyword": kw, "score": score} for kw, score in keywords]
    return {"document_id": document_id, "keywords": result}

@router.get("/{document_id}/frequencies")
def get_document_frequencies(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(TextChunk).filter(TextChunk.document_id == document_id).all()
    full_text = " ".join([chunk.content for chunk in chunks]).lower()
    words = re.findall(r'\w+', full_text, flags=re.UNICODE)
    # Убираем стоп-слова и короткие слова
    filtered = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    counter = Counter(filtered).most_common(30)
    return {"document_id": document_id, "frequencies": [{"word": w, "count": c} for w, c in counter]}

@router.get("/{document_id}/frequencies")
def get_document_frequencies(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(TextChunk).filter(TextChunk.document_id == document_id).all()
    full_text = " ".join([chunk.content for chunk in chunks]).lower()
    words = re.findall(r'\w+', full_text, flags=re.UNICODE)
    # Убираем стоп-слова и короткие слова
    filtered = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    counter = Counter(filtered).most_common(30)
    return {"document_id": document_id, "frequencies": [{"word": w, "count": c} for w, c in counter]}