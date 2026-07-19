#!/bin/bash
# =============================================================
# Деплой Restobot на сервер
# Требования: SSH-ключ (ssh-copy-id root@SERVER)
# =============================================================

set -e

# Загружаем переменные из .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "❌ Файл .env не найден!"
    exit 1
fi

if [ -z "$DEPLOY_HOST" ]; then
    echo "❌ Переменная DEPLOY_HOST не задана в .env!"
    exit 1
fi

echo "📦 Создаём архив проекта..."
zip -r restobot.zip . \
    -x ".venv/*" \
    -x "node_modules/*" \
    -x ".git/*" \
    -x "__pycache__/*" \
    -x "*.zip" \
    -x ".DS_Store" \
    -x ".env" \
    -x "data/*"

echo "🚀 Загружаем на сервер ${DEPLOY_HOST}..."
scp -o StrictHostKeyChecking=no restobot.zip root@${DEPLOY_HOST}:/root/restobot.zip

echo "🔧 Запускаем сборку на сервере..."
ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} \
    "cd /root/restobot && unzip -o /root/restobot.zip && docker compose up -d --build"

# Удаляем локальный архив после деплоя
rm -f restobot.zip

echo "✅ Деплой завершён успешно!"
