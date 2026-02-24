import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional
#import numpy as np
#from app.ml.model import compute_embedding

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.db.models import User, Document, TextChunk, collection_documents
from app.schemas import SearchResponse, SearchResultItem

router = APIRouter()

@router.get("/", response_model=SearchResponse)
def search(
    q: str,
    doc_id: Optional[int] = None,
    collection_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not q:
        raise HTTPException(status_code=400, detail="Query is empty")

    # Базовый SQL
    sql = """
        SELECT
            d.id as document_id,
            d.filename as document_name,
            tc.page_number,
            tc.chunk_index,
            tc.content,
            ts_rank(to_tsvector('russian', tc.content), plainto_tsquery('russian', :query)) as rank
        FROM text_chunks tc
        JOIN documents d ON d.id = tc.document_id
        WHERE
            d.user_id = :user_id
            AND to_tsvector('russian', tc.content) @@ plainto_tsquery('russian', :query)
    """
    params = {"user_id": current_user.id, "query": q}

    # Добавляем фильтр по документу
    if doc_id is not None:
        sql += " AND d.id = :doc_id"
        params["doc_id"] = doc_id

    # Добавляем фильтр по коллекции
    if collection_id is not None:
        sql += """ AND d.id IN (
            SELECT document_id FROM collection_documents
            WHERE collection_id = :collection_id
        )"""
        params["collection_id"] = collection_id

    sql += " ORDER BY rank DESC LIMIT 50;"

    result = db.execute(text(sql), params).fetchall()

    items = [
        SearchResultItem(
            document_id=row.document_id,
            document_name=row.document_name,
            page_number=row.page_number,
            chunk_index=row.chunk_index,
            content=row.content,
            rank=float(row.rank)
        )
        for row in result
    ]

    return SearchResponse(query=q, results=items)


@router.get("/export")
def export_search(
    request: Request,
    q: str,
    doc_id: Optional[int] = Query(None, description="ID документа для фильтрации"),
    token: str = Query(None, description="JWT token (альтернатива заголовку Authorization)"),
    db: Session = Depends(get_db)
):
    if not q:
        raise HTTPException(status_code=400, detail="Query is empty")

    # Получаем токен: сначала из query-параметра, потом из заголовка
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

    # Выполняем поиск
    sql = """
        SELECT
            d.filename as document_name,
            tc.page_number,
            tc.content
        FROM text_chunks tc
        JOIN documents d ON d.id = tc.document_id
        WHERE
            d.user_id = :user_id
            AND to_tsvector('russian', tc.content) @@ plainto_tsquery('russian', :query)
    """
    params = {"user_id": user_id, "query": q}

    if doc_id is not None:
        sql += " AND d.id = :doc_id"
        params["doc_id"] = doc_id

    sql += " ORDER BY ts_rank(to_tsvector('russian', tc.content), plainto_tsquery('russian', :query)) DESC LIMIT 100;"

    result = db.execute(text(sql), params).fetchall()

    if not result:
        content = f"По запросу '{q}' ничего не найдено."
    else:
        lines = [f"Результаты поиска по запросу: {q}\n", "=" * 50 + "\n"]
        for row in result:
            lines.append(f"\nДокумент: {row.document_name} (страница {row.page_number})\n")
            lines.append("-" * 40 + "\n")
            lines.append(row.content + "\n")
        content = "".join(lines)

    # Генерируем безопасное имя файла
    safe_q = re.sub(r'[^\w\-_]', '', q.replace(' ', '_'))[:50]
    filename = "search_results.txt"

    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
"""
@router.get("/semantic", response_model=SearchResponse)
def semantic_search(
    q: str,
    doc_id: Optional[int] = None,
    collection_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not q:
        raise HTTPException(status_code=400, detail="Query is empty")

    # 1. Получить список id документов, доступных пользователю с учётом фильтров
    doc_query = db.query(Document.id).filter(Document.user_id == current_user.id)
    if doc_id:
        doc_query = doc_query.filter(Document.id == doc_id)
    if collection_id:
        # Подзапрос: документы, входящие в коллекцию
        doc_query = doc_query.filter(Document.id.in_(
            db.query(collection_documents.c.document_id).filter(collection_documents.c.collection_id == collection_id)
        ))
    doc_ids = [row[0] for row in doc_query.all()]

    if not doc_ids:
        return SearchResponse(query=q, results=[])

    # 2. Загрузить чанки этих документов (можно ограничить количество)
    # Загружаем только id, текст и эмбеддинг
    chunks = db.query(TextChunk.id, TextChunk.content, TextChunk.embedding,
                      Document.filename.label('document_name'),
                      TextChunk.page_number, TextChunk.chunk_index)\
               .join(Document, Document.id == TextChunk.document_id)\
               .filter(TextChunk.document_id.in_(doc_ids))\
               .limit(1000).all()  # ограничим для производительности

    if not chunks:
        return SearchResponse(query=q, results=[])

    # 3. Вычислить эмбеддинг запроса
    query_embedding = compute_embedding(q)
    query_embedding = np.array(query_embedding)

    # 4. Вычислить косинусное сходство для каждого чанка
    results = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        chunk_emb = np.array(chunk.embedding)
        # косинусное сходство = (A·B) / (||A|| ||B||)
        norm = np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb)
        if norm == 0:
            similarity = 0
        else:
            similarity = np.dot(query_embedding, chunk_emb) / norm
        results.append({
            "document_id": chunk.document_id,
            "document_name": chunk.document_name,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "rank": float(similarity)
        })

    # 5. Сортировать по убыванию сходства и взять топ-50
    results.sort(key=lambda x: x["rank"], reverse=True)
    top_results = results[:50]

    items = [SearchResultItem(**r) for r in top_results]
    return SearchResponse(query=q, results=items)
"""