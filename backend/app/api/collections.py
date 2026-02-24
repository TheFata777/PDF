from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import List
from jose import JWTError, jwt

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import User, Collection, Document
from app.schemas import CollectionCreate, CollectionUpdate, CollectionOut

router = APIRouter()

def get_current_user_from_token(request: Request, token: str = Query(None)) -> int:
    auth_header = request.headers.get("Authorization")
    token_to_use = None
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
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/", response_model=List[CollectionOut])
def list_collections(
    request: Request,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    user_id = get_current_user_from_token(request, token)
    collections = db.query(Collection).filter(Collection.user_id == user_id).all()
    result = []
    for c in collections:
        result.append({
            "id": c.id,
            "user_id": c.user_id,
            "name": c.name,
            "description": c.description,
            "created_at": c.created_at,
            "documents": [doc.id for doc in c.documents]
        })
    return result

@router.post("/", response_model=CollectionOut)
def create_collection(
    request: Request,
    collection: CollectionCreate,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    user_id = get_current_user_from_token(request, token)
    db_collection = Collection(
        user_id=user_id,
        name=collection.name,
        description=collection.description
    )
    db.add(db_collection)
    db.commit()
    db.refresh(db_collection)
    return {
        "id": db_collection.id,
        "user_id": db_collection.user_id,
        "name": db_collection.name,
        "description": db_collection.description,
        "created_at": db_collection.created_at,
        "documents": []
    }

@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(
    request: Request,
    collection_id: int,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    user_id = get_current_user_from_token(request, token)
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.user_id == user_id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {
        "id": collection.id,
        "user_id": collection.user_id,
        "name": collection.name,
        "description": collection.description,
        "created_at": collection.created_at,
        "documents": [doc.id for doc in collection.documents]
    }

@router.put("/{collection_id}", response_model=CollectionOut)
def update_collection(
    request: Request,
    collection_id: int,
    collection_update: CollectionUpdate,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    user_id = get_current_user_from_token(request, token)
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.user_id == user_id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    if collection_update.name is not None:
        collection.name = collection_update.name
    if collection_update.description is not None:
        collection.description = collection_update.description
    db.commit()
    db.refresh(collection)
    return {
        "id": collection.id,
        "user_id": collection.user_id,
        "name": collection.name,
        "description": collection.description,
        "created_at": collection.created_at,
        "documents": [doc.id for doc in collection.documents]
    }

@router.delete("/{collection_id}", status_code=204)
def delete_collection(
    request: Request,
    collection_id: int,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    user_id = get_current_user_from_token(request, token)
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.user_id == user_id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    db.delete(collection)
    db.commit()
    return

@router.post("/{collection_id}/documents/{document_id}")
def add_document_to_collection(
    request: Request,
    collection_id: int,
    document_id: int,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    user_id = get_current_user_from_token(request, token)
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.user_id == user_id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document not in collection.documents:
        collection.documents.append(document)
        db.commit()
    return {"message": "Document added"}

@router.delete("/{collection_id}/documents/{document_id}")
def remove_document_from_collection(
    request: Request,
    collection_id: int,
    document_id: int,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    user_id = get_current_user_from_token(request, token)
    collection = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.user_id == user_id
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == user_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document in collection.documents:
        collection.documents.remove(document)
        db.commit()
    return {"message": "Document removed"}