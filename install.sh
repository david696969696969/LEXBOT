#!/bin/bash
# Скрипт установки LexBot на Ubuntu/Debian

echo "🤖 Установка LexBot..."

# Обновление системы
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

# Создание пользователя
sudo useradd -m -s /bin/bash lexbot 2>/dev/null || true

# Создание директории
sudo mkdir -p /opt/lexbot
sudo chown lexbot:lexbot /opt/lexbot

# Копирование файлов (предполагается, что файлы уже скопированы в /opt/lexbot)
cd /opt/lexbot

# Создание виртуального окружения
sudo -u lexbot python3 -m venv venv

# Установка зависимостей
sudo -u lexbot ./venv/bin/pip install -r requirements.txt

# Настройка переменных окружения
echo "⚠️  Не забудьте настроить .env файл!"
echo "   sudo nano /opt/lexbot/.env"

# Настройка systemd
sudo cp lexbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lexbot

echo "✅ Установка завершена!"
echo ""
echo "📋 Дальнейшие шаги:"
echo "1. Настройте .env файл"
echo "2. Запустите бота: sudo systemctl start lexbot"
echo "3. Проверьте статус: sudo systemctl status lexbot"
echo "4. Смотрите логи: sudo journalctl -u lexbot -f"
