from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, BigInteger, JSON, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
# Таблица связи многие-ко-многим между коллекциями и документами
collection_documents = Table(
    'collection_documents',
    Base.metadata,
    Column('collection_id', Integer, ForeignKey('collections.id'), primary_key=True),
    Column('document_id', Integer, ForeignKey('documents.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    collections = relationship("Collection", back_populates="owner", cascade="all, delete-orphan")

    # Связь с документами
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=True)          # размер в байтах
    total_pages = Column(Integer, nullable=True)           # общее количество страниц
    status = Column(String, default="pending")             # pending, processing, completed, error
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    collections = relationship("Collection", secondary=collection_documents, back_populates="documents")

    # Связи
    owner = relationship("User", back_populates="documents")
    chunks = relationship("TextChunk", back_populates="document", cascade="all, delete-orphan")


class TextChunk(Base):
    __tablename__ = "text_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)          # номер страницы
    chunk_index = Column(Integer, nullable=False)          # порядковый номер чанка на странице
    content = Column(Text, nullable=False)                 # текст фрагмента
    embedding = Column(JSON, nullable=True)                # эмбеддинг (список чисел)

    # Связь с документом
    document = relationship("Document", back_populates="chunks")


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    owner = relationship("User", back_populates="collections")
    documents = relationship("Document", secondary=collection_documents, back_populates="collections")