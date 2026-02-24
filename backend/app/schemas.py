from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class DocumentOut(BaseModel):
    id: int
    filename: str
    file_size: int | None
    status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

class DocumentStatus(BaseModel):
    id: int
    status: str

class SearchResultItem(BaseModel):
    document_id: int
    document_name: str
    page_number: int
    chunk_index: int
    content: str
    rank: float  # релевантность

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]

class TextChunkOut(BaseModel):
    id: int
    page_number: int
    chunk_index: int
    content: str

    class Config:
        from_attributes = True

class CollectionBase(BaseModel):
    name: str
    description: Optional[str] = None

class CollectionCreate(CollectionBase):
    pass

class CollectionUpdate(CollectionBase):
    name: Optional[str] = None
    description: Optional[str] = None

class CollectionOut(CollectionBase):
    id: int
    user_id: int
    created_at: datetime
    documents: List[int] = []  # список id документов

    class Config:
        from_attributes = True