FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

COPY backend/app /app/app
COPY backend/main.py /app/

CMD ["celery", "-A", "app.tasks.pdf_tasks.celery_app", "worker", "--loglevel=info"]
