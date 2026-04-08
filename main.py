#!/usr/bin/env python3
"""
LexBot — KPMG Law Uzbekistan
Мониторинг законодательства с историей изменений
"""
import asyncio
import logging
import os
import sys
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

def clean_url(url):
    """Clean URL from HTML tags"""
    import re
    url = re.sub(r'<[^>]+>', '', url)
    return url.strip()
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lexbot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'lexbot.db')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '1'))
LEX_UZ_URL = 'https://lex.uz'
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
# ==================== CONSTANTS ====================
CATEGORIES = {
    'tax': {'name': 'Налоги и сборы', 'icon': '💰', 'desc': 'Налоговое законодательство, льготы, отчетность'},
    'economy': {'name': 'Экономика и бизнес', 'icon': '📈', 'desc': 'Предпринимательство, инвестиции, госзакупки'},
    'labor': {'name': 'Трудовое право', 'icon': '👷', 'desc': 'Трудовые отношения, зарплата, отпуска'},
    'digital': {'name': 'IT и цифровизация', 'icon': '💻', 'desc': 'AI, роботы, кибербезопасность, электронное правительство'},
    'civil': {'name': 'Гражданское право', 'icon': '⚖️', 'desc': 'Договоры, собственность, наследство'},
    'criminal': {'name': 'Уголовное право', 'icon': '🚔', 'desc': 'Уголовный кодекс, преступления, наказания'},
    'administrative': {'name': 'Административное право', 'icon': '📋', 'desc': 'Административные процедуры, штрафы'},
    'environment': {'name': 'Экология', 'icon': '🌿', 'desc': 'Охрана окружающей среды, природные ресурсы'},
    'health': {'name': 'Здравоохранение', 'icon': '🏥', 'desc': 'Медицина, фармацевтика, санитарные нормы'},
    'education': {'name': 'Образование', 'icon': '🎓', 'desc': 'Школы, университеты, сертификация'},
    'finance': {'name': 'Финансы и банки', 'icon': '🏦', 'desc': 'Банковское регулирование, валютный контроль'},
    'trade': {'name': 'Торговля и таможня', 'icon': '🌍', 'desc': 'Внешнеторговые операции, таможенное оформление'},
    'construction': {'name': 'Строительство', 'icon': '🏗️', 'desc': 'Строительные нормы, недвижимость, ЖКХ'},
    'transport': {'name': 'Транспорт', 'icon': '🚛', 'desc': 'Авто, авиа, ж/д, логистика'},
    'energy': {'name': 'Энергетика', 'icon': '⚡', 'desc': 'Электроэнергия, газ, возобновляемые источники'},
    'banking': {'name': '?????????? ????', 'icon': '??', 'desc': '?????, ???????, ??????, ???????'},
    'inheritance': {'name': '?????????????? ?????', 'icon': '??', 'desc': '??????????, ?????????, ???????????'},
}
DOC_TYPES = {
    'law': {'name': 'Закон', 'icon': '📜'},
    'decree': {'name': 'Указ Президента', 'icon': '⚡'},
    'resolution': {'name': 'Постановление КМ', 'icon': '📋'},
    'order': {'name': 'Приказ', 'icon': '📄'},
    'regulation': {'name': 'Нормативный акт', 'icon': '📑'},
    'court': {'name': 'Судебная практика', 'icon': '⚖️'},
}
# ==================== DATA MODELS ====================
@dataclass
class LawChange:
    """Изменение в законе"""
    article: str
    old_text: str
    new_text: str
    change_type: str  # added, removed, modified
    explanation: str = ""
@dataclass
class LawDocument:
    id: int
    title: str
    doc_type: str
    doc_number: str
    date_published: str
    date_effective: Optional[str]
    category: str
    description: str
    full_text: str
    url: str
    status: str
    changes: List[LawChange]
    version: int = 1
    previous_versions: List[Dict] = None
    created_at: str = ""
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'doc_type': self.doc_type,
            'doc_number': self.doc_number,
            'date_published': self.date_published,
            'date_effective': self.date_effective,
            'category': self.category,
            'description': self.description,
            'full_text': self.full_text,
            'url': self.url,
            'status': self.status,
            'changes': [asdict(c) for c in self.changes],
            'version': self.version,
            'previous_versions': self.previous_versions or [],
            'created_at': self.created_at
        }
# ==================== DATABASE ====================
async def init_database():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Основная таблица документов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                doc_number TEXT UNIQUE,
                date_published TEXT,
                date_effective TEXT,
                category TEXT,
                description TEXT,
                full_text TEXT,
                url TEXT,
                status TEXT DEFAULT 'new',
                changes TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # История версий документов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS document_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_number TEXT,
                version INTEGER,
                title TEXT,
                full_text TEXT,
                changes TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_number) REFERENCES documents(doc_number)
            )
        """)
        # Подписчики
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                categories TEXT DEFAULT 'all',
                notifications_enabled INTEGER DEFAULT 1,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Логи пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # История проверок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS check_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                new_documents INTEGER DEFAULT 0,
                updated_documents INTEGER DEFAULT 0,
                status TEXT
            )
        """)
        await db.commit()
    logger.info("Database initialized with history support")
async def add_subscriber(user_id: int, username: str, first_name: str, last_name: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO subscribers (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, last_name))
        await db.commit()
async def remove_subscriber(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('DELETE FROM subscribers WHERE user_id = ?', (user_id,))
        await db.commit()
async def log_user_action(user_id: int, username: str, first_name: str, last_name: str, action: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO user_logs (user_id, username, first_name, last_name, action)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, first_name, last_name, action))
        await db.commit()
    if ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"👤 {first_name} {last_name} (@{username}) — {action}"
            )
        except Exception as e:
            logger.error(f"Admin notify error: {e}")
async def get_all_subscribers() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM subscribers WHERE notifications_enabled = 1') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
async def get_document_by_number(doc_number: str) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM documents WHERE doc_number = ?', (doc_number,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
async def get_document_versions(doc_number: str) -> List[Dict]:
    """Получить историю версий документа"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM document_versions 
            WHERE doc_number = ? 
            ORDER BY version DESC
        """, (doc_number,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
async def get_documents_by_category(category: str, limit: int = 10) -> List[Dict]:
    """Получить документы по категории"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM documents 
            WHERE category = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (category, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
async def get_all_categories_stats() -> Dict[str, int]:
    """Статистика по категориям"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        stats = {}
        for cat_key in CATEGORIES.keys():
            async with db.execute('SELECT COUNT(*) FROM documents WHERE category = ?', (cat_key,)) as cursor:
                count = (await cursor.fetchone())[0]
                stats[cat_key] = count
        return stats
# ==================== PARSER ====================
async def fetch_lexuz_updates() -> List[LawDocument]:
    """Получение демо-документов с изменениями"""
    demo_docs = [
        LawDocument(
            id=0,
            title="О внесении изменений в Налоговый кодекс Республики Узбекистан",
            doc_type="law",
            doc_number="ЗРУ-1234",
            date_published=datetime.now().strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y"),
            category="tax",
            description="Внесены изменения в части налогообложения IT-компаний и стартапов. Установлены льготные ставки налога на прибыль.",
            full_text="Полный текст закона...",
            url=f"{LEX_UZ_URL}/docs/1234",
            status="new",
            version=2,
            changes=[
                LawChange("Ст. 123", "20%", "7%", "modified", "Снижение ставки налога на прибыль для IT"),
                LawChange("Ст. 124", "-", "Льгота для стартапов", "added", "Освобождение от налога первые 3 года"),
                LawChange("Ст. 125", "15%", "-", "removed", "Отменена прежняя льгота"),
            ],
            previous_versions=[
                {'version': 1, 'date': '01.01.2024', 'changes': 'Первоначальная редакция'}
            ],
            created_at=""
        ),
        LawDocument(
            id=0,
            title="О развитии искусственного интеллекта и цифровых технологий",
            doc_type="decree",
            doc_number="УП-4567",
            date_published=(datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y"),
            date_effective=datetime.now().strftime("%d.%m.%Y"),
            category="digital",
            description="Создано Национальное агентство по регулированию искусственного интеллекта. Утверждена Концепция развития AI до 2030.",
            full_text="Полный текст указа...",
            url=f"{LEX_UZ_URL}/docs/4567",
            status="new",
            version=1,
            changes=[
                LawChange("Весь документ", "-", "Новый указ", "added", "Создание агентства по AI"),
            ],
            previous_versions=[],
            created_at=""
        ),
        LawDocument(
            id=0,
            title="Об утверждении Правил регистрации робототехнических систем",
            doc_type="resolution",
            doc_number="ПКМ-789",
            date_published=(datetime.now() - timedelta(days=2)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=15)).strftime("%d.%m.%Y"),
            category="digital",
            description="Установлен порядок государственной регистрации промышленных и сервисных роботов. Введены требования безопасности.",
            full_text="Полный текст постановления...",
            url=f"{LEX_UZ_URL}/docs/789",
            status="new",
            version=1,
            changes=[
                LawChange("Раздел 1", "-", "Правила регистрации", "added", "Обязательная регистрация всех роботов"),
                LawChange("Раздел 2", "-", "Требования безопасности", "added", "Сертификация ISO 10218"),
            ],
            previous_versions=[],
            created_at=""
        ),
        LawDocument(
            id=0,
            title="О внесении изменений в Трудовой кодекс РУз",
            doc_type="law",
            doc_number="ЗРУ-1235",
            date_published=(datetime.now() - timedelta(days=3)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=10)).strftime("%d.%m.%Y"),
            category="labor",
            description="Закреплены правовые нормы для удаленной работы. Урегулированы вопросы мониторинга деятельности удаленных сотрудников.",
            full_text="Полный текст закона...",
            url=f"{LEX_UZ_URL}/docs/1235",
            status="new",
            version=3,
            changes=[
                LawChange("Ст. 50", "Только офис", "Офис/удаленно/гибрид", "modified", "Новые форматы работы"),
                LawChange("Ст. 51", "-", "Электронный контроль", "added", "Разрешен мониторинг с согласия"),
            ],
            previous_versions=[
                {'version': 1, 'date': '01.01.2023', 'changes': 'Первоначальная редакция'},
                {'version': 2, 'date': '15.06.2024', 'changes': 'Изменения по отпускам'}
            ],
            created_at=""
        ),
    ]
    return demo_docs
async def check_new_documents():
    logger.info("Checking for new documents...")
    try:
        new_docs = await fetch_lexuz_updates()
        new_count = 0
        updated_count = 0
        for doc in new_docs:
            existing = await get_document_by_number(doc.doc_number)
            if not existing:
                # Новый документ
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute("""
                        INSERT INTO documents 
                        (title, doc_type, doc_number, date_published, date_effective,
                         category, description, full_text, url, status, changes, version)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        doc.title, doc.doc_type, doc.doc_number, doc.date_published,
                        doc.date_effective, doc.category, doc.description, doc.full_text,
                        doc.url, doc.status, json.dumps([asdict(c) for c in doc.changes]),
                        doc.version
                    ))
                    await db.commit()
                new_count += 1
                await notify_subscribers(doc, is_update=False)
            elif existing['version'] < doc.version:
                # Обновление существующего документа
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    # Сохраняем старую версию
                    await db.execute("""
                        INSERT INTO document_versions 
                        (doc_number, version, title, full_text, changes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        existing['doc_number'], existing['version'],
                        existing['title'], existing.get('full_text', ''),
                        existing.get('changes', '[]')
                    ))
                    # Обновляем документ
                    await db.execute("""
                        UPDATE documents SET
                        title = ?, date_effective = ?, description = ?,
                        full_text = ?, changes = ?, version = ?, status = 'updated'
                        WHERE doc_number = ?
                    """, (
                        doc.title, doc.date_effective, doc.description,
                        doc.full_text, json.dumps([asdict(c) for c in doc.changes]),
                        doc.version, doc.doc_number
                    ))
                    await db.commit()
                updated_count += 1
                await notify_subscribers(doc, is_update=True)
        # Логируем проверку
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                INSERT INTO check_logs (new_documents, updated_documents, status)
                VALUES (?, ?, ?)
            """, (new_count, updated_count, 'success'))
            await db.commit()
        logger.info(f"Check completed. New: {new_count}, Updated: {updated_count}")
        if (new_count > 0 or updated_count > 0) and ADMIN_ID:
            await bot.send_message(
                ADMIN_ID,
                f"✅ Проверка завершена!\nНовых: {new_count}\nОбновлено: {updated_count}"
            )
    except Exception as e:
        logger.error(f"Check error: {e}")
        import traceback
        logger.error(traceback.format_exc())
async def notify_subscribers(doc: LawDocument, is_update: bool = False):
    """Уведомление подписчиков с историей изменений"""
    subscribers = await get_all_subscribers()
    type_info = DOC_TYPES.get(doc.doc_type, {'name': 'Документ', 'icon': '📄'})
    cat_info = CATEGORIES.get(doc.category, {'name': doc.category, 'icon': '📁'})
    # Форматируем изменения
    changes_text = ""
    if doc.changes:
        changes_text = "\n<b>📝 Ключевые изменения:</b>\n"
        for i, change in enumerate(doc.changes[:5], 1):  # Показываем первые 5
            if change.change_type == "added":
                changes_text += f"\n{i}. ➕ <b>{change.article}</b>: {change.new_text}"
            elif change.change_type == "removed":
                changes_text += f"\n{i}. ➖ <b>{change.article}</b>: удалено"
            else:
                changes_text += f"\n{i}. 🔄 <b>{change.article}</b>: {change.old_text} → {change.new_text}"
            if change.explanation:
                changes_text += f"\n   <i>{change.explanation}</i>"
    # История версий
    versions_text = ""
    if doc.previous_versions:
        versions_text = f"\n\n<b>📚 История:</b> {len(doc.previous_versions)} предыдущих версий"
    action_emoji = "🔄" if is_update else "🆕"
    action_text = "ОБНОВЛЕНИЕ" if is_update else "НОВЫЙ ДОКУМЕНТ"
    message = f"""
{action_emoji} <b>{action_text}</b>
{type_info['icon']} <b>{doc.title}</b>
<b>📋 Информация:</b>
• Тип: {type_info['name']}
• Номер: <code>{doc.doc_number}</code>
• Дата публикации: {doc.date_published}
• Вступает в силу: {doc.date_effective or 'Немедленно'}
• Категория: {cat_info['icon']} {cat_info['name']}
• Версия: <b>v{doc.version}</b>
<b>🎯 Описание:</b>
{doc.description}
{changes_text}
{versions_text}
<b>🔗 Источник:</b> <a href="{clean_url(doc.url)}">Lex.uz</a>
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Полный текст", url=clean_url(doc.url))],
        [InlineKeyboardButton(text="📚 История изменений", callback_data=f"history_{doc.doc_number}")],
        [InlineKeyboardButton(text=f"{cat_info['icon']} Все {cat_info['name']}", callback_data=f"cat_{doc.category}")],
        [InlineKeyboardButton(text="❌ Отключить уведомления", callback_data="unsubscribe")]
    ])
    for sub in subscribers:
        try:
            await bot.send_message(
                sub['user_id'],
                message,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Notify error for {sub['user_id']}: {e}")
# ==================== COMMANDS ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    await log_user_action(user.id, user.username or "", user.first_name or "", user.last_name or "", "start")
    await add_subscriber(user.id, user.username or "", user.first_name or "", user.last_name or "")
    # Статистика по категориям
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    welcome = f"""
<b>🏛️ KPMG Law Uzbekistan — LexBot</b>
Привет, {user.first_name}!
🤖 Я профессионально мониторю законодательство Узбекистана с <b>историей изменений</b>.
<b>📊 В базе:</b>
• Всего документов: <b>{total_docs}</b>
• Категорий: <b>{len(CATEGORIES)}</b>
<b>⚡ Возможности:</b>
• 📜 Новые законы и изменения
• 📚 История версий документов
• 🔔 Мгновенные уведомления
• 📁 Поиск по 15 категориям
• 📊 Детальная статистика
<b>📋 Команды:</b>
/documents — Все документы
/categories — По категориям
/history — История изменений
/stats — Статистика
/search — Поиск
/help — Помощь
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Документы", callback_data="all_docs"),
         InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu")],
        [InlineKeyboardButton(text="📚 История", callback_data="history_menu"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])
    await message.answer(welcome, reply_markup=keyboard, parse_mode="HTML")
@dp.message(Command("documents"))
async def cmd_documents(message: Message):
    """Все документы с пагинацией"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM documents ORDER BY created_at DESC LIMIT 5'
        ) as cursor:
            docs = await cursor.fetchall()
    if not docs:
        await message.answer("📭 Пока нет документов в базе")
        return
    text = "<b>📜 ПОСЛЕДНИЕ ДОКУМЕНТЫ</b>\n\n"
    for i, doc in enumerate(docs, 1):
        type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
        cat_info = CATEGORIES.get(doc['category'], {'name': doc['category']})
        text += f"{i}. {type_info['icon']} <b>{doc['title']}</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | v{doc['version']}\n"
        text += f"   📅 {doc['date_published']} | {cat_info['name']}\n"
        text += f"   <a href='{clean_url(doc['url'])}'>Открыть →</a>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 По категориям", callback_data="categories_menu")],
        [InlineKeyboardButton(text="📚 История изменений", callback_data="history_menu")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    """Меню категорий"""
    cat_stats = await get_all_categories_stats()
    text = "<b>📁 КАТЕГОРИИ ЗАКОНОДАТЕЛЬСТВА</b>\n\n"
    text += "Выберите категорию для просмотра документов:\n\n"
    keyboard_buttons = []
    row = []
    for key, info in CATEGORIES.items():
        count = cat_stats.get(key, 0)
        btn = InlineKeyboardButton(
            text=f"{info['icon']} {info['name']} ({count})",
            callback_data=f"cat_{key}"
        )
        row.append(btn)
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []
    if row:
        keyboard_buttons.append(row)
    keyboard_buttons.append([
        InlineKeyboardButton(text="📊 Статистика по категориям", callback_data="cats_stats")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
@dp.message(Command("history"))
async def cmd_history(message: Message):
    """История изменений"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
    SELECT d.*, COUNT(v.id) as version_count 
    FROM documents d
    LEFT JOIN document_versions v ON d.doc_number = v.doc_number
    GROUP BY d.id, d.doc_number
    HAVING d.version > 1 OR COUNT(v.id) > 0
    ORDER BY d.created_at DESC
    LIMIT 10
""") as cursor:
            docs = await cursor.fetchall()
    if not docs:
        await message.answer("📭 Пока нет документов с историей изменений")
        return
    text = "<b>📚 ИСТОРИЯ ИЗМЕНЕНИЙ</b>\n\n"
    text += "Документы с версиями и изменениями:\n\n"
    for doc in docs:
        versions = doc.get('version_count', 0) + 1
        text += f"📜 <b>{doc['title']}</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | {versions} версий\n"
        text += f"   Текущая: v{doc['version']}\n"
        text += f"   <a href='{clean_url(doc['url'])}'>Смотреть →</a>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти документ", callback_data="search_doc")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    user = message.from_user
    await add_subscriber(user.id, user.username or "", user.first_name or "", user.last_name or "")
    await message.answer(
        "✅ <b>Подписка оформлена!</b>\n\n"
        "Вы будете получать уведомления о:\n"
        "• Новых документах\n"
        "• Обновлениях существующих\n"
        "• История изменений",
        parse_mode="HTML"
    )
@dp.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message):
    await remove_subscriber(message.from_user.id)
    await message.answer("❌ <b>Уведомления отключены</b>", parse_mode="HTML")
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM document_versions') as cursor:
            total_versions = (await cursor.fetchone())[0]
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        async with db.execute('SELECT COUNT(*) FROM documents WHERE created_at > ?', (week_ago,)) as cursor:
            new_week = (await cursor.fetchone())[0]
    text = f"""
<b>📊 СТАТИСТИКА ЗАКОНОДАТЕЛЬСТВА</b>
<b>📚 Общие показатели:</b>
• Всего документов: <b>{total_docs}</b>
• Версий документов: <b>{total_versions}</b>
• Новых за неделю: <b>{new_week}</b>
<b>📁 По категориям:</b>
"""
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁'})
            percentage = (count / total_docs * 100) if total_docs > 0 else 0
            bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
            text += f"\n{info['icon']} {info['name']}: {count} <code>[{bar}]</code> {percentage:.1f}%"
    text += f"\n\n<b>🔄 Обновление:</b> каждые {CHECK_INTERVAL} мин"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu"),
         InlineKeyboardButton(text="📜 Документы", callback_data="all_docs")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
@dp.message(Command("search"))
async def cmd_search(message: Message):
    keyboard_buttons = []
    row = []
    for key, info in list(CATEGORIES.items())[:8]:  # Первые 8 категорий
        btn = InlineKeyboardButton(
            text=f"{info['icon']} {info['name']}",
            callback_data=f"cat_{key}"
        )
        row.append(btn)
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []
    if row:
        keyboard_buttons.append(row)
    keyboard_buttons.append([
        InlineKeyboardButton(text="📊 Все категории", callback_data="categories_menu")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(
        "<b>🔍 ПОИСК ПО КАТЕГОРИЯМ</b>\n\n"
        "Выберите категорию или введите ключевые слова:\n"
        "<i>например: налоговый кодекс, удаленная работа, AI</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = f"""
<b>❓ ПОМОЩЬ — KPMG Law LexBot</b>
<b>📋 Основные команды:</b>
/documents — Все документы с версиями
/categories — Просмотр по категориям (15 разделов)
/history — История изменений документов
/stats — Детальная статистика
/search — Поиск по категориям
<b>⚙️ Управление:</b>
/subscribe — Подписаться на уведомления
/unsubscribe — Отключить уведомления
<b>💡 Возможности:</b>
• 📚 Отслеживание версий документов
• 📝 Детальный анализ изменений
• 🔔 Уведомления о новых редакциях
• 📊 Статистика по 15 категориям
<b>🏛️ KPMG Law Uzbekistan</b>
Аудит | Налоги | Право | Консалтинг
"""
    await message.answer(help_text, parse_mode="HTML")
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ <b>Доступ запрещен</b>", parse_mode="HTML")
        return
    cat_stats = await get_all_categories_stats()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM user_logs") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM subscribers") as cursor:
            active_subs = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM documents") as cursor:
            total_docs = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM document_versions") as cursor:
            total_versions = (await cursor.fetchone())[0]
        async with db.execute("""
            SELECT first_name, username, action, timestamp 
            FROM user_logs 
            ORDER BY timestamp DESC 
            LIMIT 5
        """) as cursor:
            recent = await cursor.fetchall()
    report = f"""
<b>📊 АДМИН-ПАНЕЛЬ KPMG LexBot</b>
<b>👥 Пользователи:</b>
• Всего уникальных: <b>{total_users}</b>
• Активных подписчиков: <b>{active_subs}</b>
<b>📚 Документы:</b>
• Всего документов: <b>{total_docs}</b>
• Версий (история): <b>{total_versions}</b>
<b>📁 По категориям:</b>
"""
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
        info = CATEGORIES.get(cat_key, {'name': cat_key})
        report += f"\n• {info['name']}: {count}"
    report += "\n\n<b>🔥 Последние действия:</b>"
    for name, username, action, time in recent:
        report += f"\n• {name} (@{username}) — {action}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ])
    await message.answer(report, reply_markup=keyboard, parse_mode="HTML")
# ==================== CALLBACKS ====================
@dp.callback_query(F.data == "all_docs")
async def callback_all_docs(callback: CallbackQuery):
    await cmd_documents(callback.message)
    await callback.answer()
@dp.callback_query(F.data == "categories_menu")
async def callback_categories_menu(callback: CallbackQuery):
    await cmd_categories(callback.message)
    await callback.answer()
@dp.callback_query(F.data == "history_menu")
async def callback_history_menu(callback: CallbackQuery):
    await cmd_history(callback.message)
    await callback.answer()
@dp.callback_query(F.data == "stats")
async def callback_stats(callback: CallbackQuery):
    await cmd_stats(callback.message)
    await callback.answer()
@dp.callback_query(F.data == "subscribe_confirm")
async def callback_subscribe(callback: CallbackQuery):
    user = callback.from_user
    await add_subscriber(user.id, user.username or "", user.first_name or "", user.last_name or "")
    await callback.message.edit_text("✅ <b>Подписка оформлена!</b>", parse_mode="HTML")
    await callback.answer("Подписка активирована")
@dp.callback_query(F.data == "unsubscribe")
async def callback_unsubscribe(callback: CallbackQuery):
    await remove_subscriber(callback.from_user.id)
    await callback.message.edit_text("❌ <b>Уведомления отключены</b>", parse_mode="HTML")
    await callback.answer("Уведомления отключены")
@dp.callback_query(F.data.startswith("cat_"))
async def callback_category(callback: CallbackQuery):
    category = callback.data.replace("cat_", "")
    if category not in CATEGORIES:
        await callback.answer("Категория не найдена")
        return
    cat_info = CATEGORIES[category]
    docs = await get_documents_by_category(category, limit=10)
    if not docs:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        text += f"📭 В этой категории пока нет документов\n\n"
        text += f"<i>{cat_info['desc']}</i>"
    else:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        text += f"<i>{cat_info['desc']}</i>\n\n"
        text += f"📚 Найдено документов: <b>{len(docs)}</b>\n\n"
        for i, doc in enumerate(docs, 1):
            type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
            text += f"{i}. {type_info['icon']} <b>{doc['title']}</b>\n"
            text += f"   <code>{doc['doc_number']}</code> | v{doc['version']}\n"
            text += f"   📅 {doc['date_published']}\n"
            text += f"   <a href='{clean_url(doc['url'])}'>Открыть →</a>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Все категории", callback_data="categories_menu")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()
@dp.callback_query(F.data.startswith("history_"))
async def callback_document_history(callback: CallbackQuery):
    """Показать историю версий конкретного документа"""
    doc_number = callback.data.replace("history_", "")
    doc = await get_document_by_number(doc_number)
    if not doc:
        await callback.answer("Документ не найден")
        return
    versions = await get_document_versions(doc_number)
    type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
    text = f"{type_info['icon']} <b>{doc['title']}</b>\n\n"
    text += f"<b>📚 История версий:</b>\n\n"
    text += f"Текущая версия: <b>v{doc['version']}</b>\n"
    if versions:
        text += f"Предыдущих версий: <b>{len(versions)}</b>\n\n"
        for v in versions:
            text += f"📄 v{v['version']} — {v['changed_at'][:10]}\n"
    else:
        text += "\n<i>Это первая версия документа</i>"
    # Показываем изменения текущей версии
    changes = json.loads(doc.get('changes', '[]'))
    if changes:
        text += "\n\n<b>📝 Текущие изменения:</b>"
        for change in changes:
            text += f"\n• {change.get('article', '')}: {change.get('change_type', '')}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Полный текст", url=clean_url(doc['url']))],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="all_docs")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
@dp.callback_query(F.data == "cats_stats")
async def callback_categories_stats(callback: CallbackQuery):
    """Детальная статистика по категориям"""
    cat_stats = await get_all_categories_stats()
    total = sum(cat_stats.values())
    text = "<b>📊 СТАТИСТИКА ПО КАТЕГОРИЯМ</b>\n\n"
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁', 'desc': ''})
        percentage = (count / total * 100) if total > 0 else 0
        text += f"\n{info['icon']} <b>{info['name']}</b>\n"
        text += f"   Документов: <b>{count}</b> ({percentage:.1f}%)\n"
        text += f"   <i>{info['desc']}</i>\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="categories_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
# ==================== MAIN ====================
async def on_startup_webhook(bot: Bot, webhook_url: str):
    """Установка вебхука при старте"""
    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )
    logger.info(f"Webhook установлен: {webhook_url}")
async def on_shutdown(bot: Bot):
    """Очистка при остановке"""
    scheduler.shutdown()
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Бот остановлен")
async def main_webhook():
    """Режим WEBHOOK для Railway (продакшен)"""
    logger.info("Starting LexBot in WEBHOOK mode...")
    await init_database()
    # Запускаем планировщик
    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='lexuz_check',
        name='Check Lex.uz',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started (interval: {CHECK_INTERVAL} min)")
    # Получаем домен Railway
    RAILWAY_STATIC_URL = os.getenv("RAILWAY_STATIC_URL")
    RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if RAILWAY_STATIC_URL:
        WEBHOOK_HOST = f"https://{RAILWAY_STATIC_URL}"
    elif RAILWAY_PUBLIC_DOMAIN:
        WEBHOOK_HOST = f"https://{RAILWAY_PUBLIC_DOMAIN}"
    else:
        logger.error("Не найден домен Railway! Проверь переменные RAILWAY_STATIC_URL или RAILWAY_PUBLIC_DOMAIN")
        return
    WEBHOOK_PATH = f"/bot{BOT_TOKEN}"
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    # Устанавливаем вебхук
    await on_startup_webhook(bot, WEBHOOK_URL)
    # Создаем aiohttp сервер
    from aiohttp import web
    async def handle_webhook(request):
        """Обработчик вебхуков от Telegram"""
        if request.match_info.get('token') == BOT_TOKEN:
            try:
                data = await request.json()
                update = types.Update(**data)
                await dp.feed_update(bot, update)
                return web.Response(text="OK")
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                return web.Response(status=500)
        return web.Response(status=403)
    async def health_check(request):
        """Health check для Railway"""
        return web.Response(text="LexBot is running!")
    app = web.Application()
    app.router.add_post(f'/bot{BOT_TOKEN}', handle_webhook)
    app.router.add_get('/health', health_check)
    # Graceful shutdown
    async def cleanup(app):
        await on_shutdown(bot)
    app.on_cleanup.append(cleanup)
    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    PORT = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    logger.info(f"Server started on port {PORT}")
    await site.start()
    # Держим процесс живым
    while True:
        await asyncio.sleep(3600)
async def main_polling():
    """Режим POLLING для локальной разработки"""
    logger.info("Starting LexBot in POLLING mode...")
    await init_database()
    # Запускаем планировщик
    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='lexuz_check',
        name='Check Lex.uz',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started (interval: {CHECK_INTERVAL} min)")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()
        scheduler.shutdown()
if __name__ == "__main__":
    # Проверяем режим: если есть переменные Railway — вебхуки, иначе polling
    if os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        asyncio.run(main_webhook())
    else:
        asyncio.run(main_polling())
