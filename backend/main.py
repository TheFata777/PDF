from app.core.logging_config import setup_logging
setup_logging()
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.api import auth, documents, search, collections
from app.db.models import Base
from app.db.session import engine
from app.core.logging_config import setup_logging
import logging

setup_logging()
logging.info("=== ТЕСТОВОЕ СООБЩЕНИЕ ИЗ MAIN.PY ===")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создание таблиц
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы/проверены")

    # Создание полнотекстового индекса
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_text_chunks_content_tsv
            ON text_chunks USING GIN (to_tsvector('russian', content));
        """))
        conn.commit()
        print("✅ Полнотекстовый индекс создан/проверен")

    yield

# Сначала создаём приложение
app = FastAPI(lifespan=lifespan)

# Монтируем статику
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Подключаем роутеры API
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(collections.router, prefix="/api/collections", tags=["collections"])

# Настраиваем шаблоны
templates = Jinja2Templates(directory="app/templates")

# HTML-страницы
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})

@app.get("/api")
async def root():
    return {"message": "PDF Knowledge Engine API"}

@app.get("/documents/{document_id}/text-view", response_class=HTMLResponse)
async def document_text_page(request: Request, document_id: int):
    return templates.TemplateResponse("document_text.html", {"request": request})

@app.get("/collections", response_class=HTMLResponse)
async def collections_page(request: Request):
    return templates.TemplateResponse("collections.html", {"request": request})

@app.get("/collections/{collection_id}", response_class=HTMLResponse)
async def collection_detail_page(request: Request, collection_id: int):
    return templates.TemplateResponse("collection_detail.html", {"request": request})