# Personal PDF Knowledge Engine

Серверное приложение для анализа PDF-документов с многопользовательской поддержкой, асинхронной обработкой и поиском.


### Запуск локально
1. Клонируйте репозиторий:
   ```bash
   git clone <url-репозитория>
   cd pdf-knowledge-engine
   ```
2. Запустите контейнеры:
   ```bash
   sudo docker-compose up --build
   ```
3. Открытие localtunnel:
   ```bash
   npx localtunnel --port 8000
   ```