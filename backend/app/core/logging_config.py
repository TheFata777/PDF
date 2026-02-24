import logging
import sys
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logging():
    """Настройка логирования: вывод в консоль и файл с ротацией"""
    logger = logging.getLogger()
    # Защита от множественного добавления обработчиков при перезагрузках
    if logger.handlers:
        return

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Файловый handler с ротацией
    file_handler = RotatingFileHandler(
        filename=os.path.join(LOG_DIR, "app.log"),
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Логгер ошибок Uvicorn
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.addHandler(file_handler)
    uvicorn_error.addHandler(console_handler)  # можно оставить, но уже есть в корневом
    uvicorn_error.propagate = False  # предотвращаем дублирование

    # Логгер доступа Uvicorn
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addHandler(file_handler)
    uvicorn_access.addHandler(console_handler)
    uvicorn_access.propagate = False

    # Устанавливаем уровень для этих логгеров
    uvicorn_error.setLevel(logging.INFO)
    uvicorn_access.setLevel(logging.INFO)

    # Уровни для сторонних библиотек
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)