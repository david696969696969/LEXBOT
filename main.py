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
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Установите: pip install beautifulsoup4 lxml")
    BeautifulSoup = None

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
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))  # Увеличил до 30 минут
LEX_UZ_URL = 'https://lex.uz'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

CATEGORIES = {
    'tax': {'name': 'Налоги и сборы', 'icon': '💰', 'desc': 'Налоговое законодательство'},
    'labor': {'name': 'Трудовое право', 'icon': '👷', 'desc': 'Трудовые отношения'},
    'digital': {'name': 'IT и цифровизация', 'icon': '💻', 'desc': 'AI, роботы, кибербезопасность'},
    'finance': {'name': 'Финансы и банки', 'icon': '🏦', 'desc': 'Банковское регулирование'},
    'general': {'name': 'Общие', 'icon': '📁', 'desc': 'Прочие документы'},
}

DOC_TYPES = {
    'law': {'name': 'Закон', 'icon': '📜'},
    'decree': {'name': 'Указ Президента', 'icon': '⚡'},
    'resolution': {'name': 'Постановление КМ', 'icon': '📋'},
    'order': {'name': 'Приказ', 'icon': '📄'},
}

@dataclass
class LawChange:
    article: str
    old_text: str
    new_text: str
    change_type: str
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

class LexUzParser:
    def __init__(self):
        self.base_url = "https://lex.uz"
        self.session = None
        self._doc_counter = 0  # Счётчик для уникальных ID

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_category(self, title: str) -> str:
        """Улучшенное определение категории"""
        title_lower = title.lower()
        
        category_keywords = {
            'tax': ['налог', 'сбор', 'ндс', 'прибыль', 'акциз', 'таможен', 'пошлин'],
            'labor': ['труд', 'зарплат', 'отпуск', 'работник', 'занятост', 'профсоюз'],
            'digital': ['цифров', 'информаци', 'коммуникаци', 'интернет', 'электронн', 'кибер', 'программн'],
            'finance': ['банк', 'валют', 'финанс', 'кредит', 'страхован', 'бирж', 'ценн бумаг'],
        }
        
        for cat, keywords in category_keywords.items():
            if any(kw in title_lower for kw in keywords):
                return cat
        return 'general'

    def _get_doc_type(self, doc_number: str) -> str:
        """Определение типа документа"""
        doc_upper = doc_number.upper()
        if doc_upper.startswith('УП') or 'УП-' in doc_upper:
            return 'decree'
        elif doc_upper.startswith('ПКМ') or 'ПКМ-' in doc_upper:
            return 'resolution'
        elif doc_upper.startswith('П ') or 'ПРИКАЗ' in doc_upper:
            return 'order'
        elif 'ЗРУ' in doc_upper or 'ЗАКОН' in doc_upper:
            return 'law'
        return 'regulation'

    def _build_url(self, doc_number: str, href: Optional[str] = None) -> str:
        """Построение корректного URL"""
        if href:
            if href.startswith('/'):
                return f'{self.base_url}{href}'
            elif href.startswith('http'):
                return href
        
        # Если нет href — генерируем поисковый URL
        clean_num = doc_number.replace(' ', '+').replace('/', '%2F')
        return f'{self.base_url}/ru/search/all/?text={clean_num}'

    async def fetch_new_documents(self) -> List[LawDocument]:
        """Парсинг с защитой от ошибок"""
        documents = []
        
        if not BeautifulSoup:
            logger.error("BeautifulSoup не установлен")
            return documents

        try:
            logger.info(f"Запрос к {self.base_url}/ru/lists/all/")
            async with self.session.get(f"{self.base_url}/ru/lists/all/") as response:
                logger.info(f"Статус ответа: {response.status}")
                
                if response.status != 200:
                    logger.warning(f"Неожиданный статус: {response.status}")
                    return documents
                
                html = await response.text()
                
                if not html or len(html) < 100:
                    logger.warning("Пустой или слишком короткий ответ")
                    return documents
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Пробуем разные селекторы
                rows = (soup.find_all('tr', class_='doc-row') or 
                        soup.find_all('tr', class_=re.compile('doc')) or
                        soup.find_all('tr'))
                
                logger.info(f"Найдено строк: {len(rows)}")
                
                for row in rows[:20]:  # Ограничение для безопасности
                    try:
                        cells = row.find_all('td')
                        if len(cells) < 2:
                            continue

                        # Номер документа
                        doc_number = cells[0].get_text(strip=True) if cells[0] else 'N/A'
                        if not doc_number or doc_number == 'N/A':
                            continue

                        # Заголовок и ссылка
                        title_cell = cells[1] if len(cells) > 1 else cells[0]
                        link_elem = title_cell.find('a')
                        
                        title = 'Без названия'
                        href = None
                        
                        if link_elem:
                            title = link_elem.get_text(strip=True)
                            href = link_elem.get('href')  # Безопасное получение
                        
                        if title == 'Без названия' and title_cell:
                            title = title_cell.get_text(strip=True)

                        # Дата
                        date_published = datetime.now().strftime('%d.%m.%Y')
                        if len(cells) > 2:
                            date_text = cells[2].get_text(strip=True)
                            if date_text:
                                date_published = date_text

                        # Определяем тип и категорию
                        doc_type = self._get_doc_type(doc_number)
                        category = self._get_category(title)
                        
                        # Строим URL
                        url = self._build_url(doc_number, href)

                        documents.append(LawDocument(
                            id=0,
                            title=title[:300],  # Ограничение длины
                            doc_type=doc_type,
                            doc_number=doc_number[:100],
                            date_published=date_published,
                            date_effective=date_published,
                            category=category,
                            description=title[:250],
                            full_text='',
                            url=url,
                            status='new',
                            version=1,
                            changes=[],
                            previous_versions=[],
                            created_at=datetime.now().isoformat()
                        ))
                        
                    except Exception as e:
                        logger.error(f'Ошибка парсинга строки: {e}')
                        continue
                        
        except asyncio.TimeoutError:
            logger.error('Таймаут при подключении к Lex.uz')
        except aiohttp.ClientError as e:
            logger.error(f'Ошибка клиента aiohttp: {e}')
        except Exception as e:
            logger.error(f'Неожиданная ошибка: {e}')
            import traceback
            logger.error(traceback.format_exc())

        logger.info(f'Успешно спарсено: {len(documents)} документов')
        return documents

    async def test_connection(self) -> bool:
        """Проверка доступности сайта"""
        try:
            async with self.session.get(self.base_url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Сайт недоступен: {e}")
            return False

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
                category TEXT DEFAULT 'general',
                description TEXT,
                full_text TEXT,
                url TEXT,
                status TEXT DEFAULT 'new',
                changes TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для производительности
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_docs_category ON documents(category)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_docs_date ON documents(created_at)
        """)
        
        # Таблица подписчиков
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                notifications_enabled INTEGER DEFAULT 1,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Логи проверок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS check_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                new_documents INTEGER DEFAULT 0,
                updated_documents INTEGER DEFAULT 0,
                status TEXT,
                error_message TEXT
            )
        """)
        
        await db.commit()
    logger.info("Database initialized")

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

async def get_documents_by_category(category: str, limit: int = 10) -> List[Dict]:
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
    async with aiosqlite.connect(DATABASE_PATH) as db:
        stats = {}
        for cat_key in CATEGORIES.keys():
            async with db.execute('SELECT COUNT(*) FROM documents WHERE category = ?', (cat_key,)) as cursor:
                count = (await cursor.fetchone())[0]
                stats[cat_key] = count
        return stats

async def cleanup_old_documents(days: int = 90):
    """Очистка старых документов"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            DELETE FROM documents 
            WHERE created_at < datetime('now', '-{} days')
        """.format(days))
        await db.commit()

# ==================== CHECK DOCUMENTS ====================

async def check_new_documents():
    logger.info("Starting check for new documents...")
    
    try:
        async with LexUzParser() as parser:
            # Проверяем доступность
            if not await parser.test_connection():
                logger.error("Lex.uz недоступен")
                await log_check(0, 0, 'error', 'Site unavailable')
                return
            
            new_docs = await parser.fetch_new_documents()
        
        if not new_docs:
            logger.info("No documents found")
            await log_check(0, 0, 'success', 'No new documents')
            return
        
        new_count = 0
        updated_count = 0
        
        for doc in new_docs[:50]:  # Лимит на обработку
            try:
                existing = await get_document_by_number(doc.doc_number)
                
                if not existing:
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
                    
            except Exception as e:
                logger.error(f"Error processing document {doc.doc_number}: {e}")
                continue
        
        await log_check(new_count, updated_count, 'success')
        
        if new_count > 0 and ADMIN_ID:
            await bot.send_message(
                ADMIN_ID,
                f"✅ Проверка завершена!\n📄 Новых документов: {new_count}\n🔄 Обновлено: {updated_count}"
            )
            
    except Exception as e:
        logger.error(f"Check error: {e}")
        await log_check(0, 0, 'error', str(e))
        import traceback
        logger.error(traceback.format_exc())

async def log_check(new: int, updated: int, status: str, error: str = None):
    """Логирование проверки"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO check_logs (new_documents, updated_documents, status, error_message)
            VALUES (?, ?, ?, ?)
        """, (new, updated, status, error))
        await db.commit()

async def notify_subscribers(doc: LawDocument, is_update: bool = False):
    subscribers = await get_all_subscribers()
    
    if not subscribers:
        return
    
    type_info = DOC_TYPES.get(doc.doc_type, {'name': 'Документ', 'icon': '📄'})
    cat_info = CATEGORIES.get(doc.category, {'name': doc.category, 'icon': '📁'})
    
    action_emoji = "🔄" if is_update else "🆕"
    action_text = "ОБНОВЛЕНИЕ" if is_update else "НОВЫЙ ДОКУМЕНТ"
    
    message = f"""
{action_emoji} <b>{action_text}</b>

{type_info['icon']} <b>{doc.title}</b>

<b>📋 Информация:</b>
• Тип: {type_info['name']}
• Номер: <code>{doc.doc_number}</code>
• Дата публикации: {doc.date_published}
• Категория: {cat_info['icon']} {cat_info['name']}

<b>🔗 Источник:</b> <a href="{doc.url}">Lex.uz</a>
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Открыть на Lex.uz", url=doc.url)],
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
    await add_subscriber(user.id, user.username or "", user.first_name or "", user.last_name or "")
    
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    
    welcome = f"""
<b>🏛️ KPMG Law Uzbekistan — LexBot</b>

Привет, {user.first_name or 'друг'}!

🤖 Я мониторю законодательство Узбекистана.

<b>📊 В базе:</b>
• Всего документов: <b>{total_docs}</b>

<b>📋 Команды:</b>
/documents — Все документы
/categories — По категориям
/stats — Статистика
/help — Помощь
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Документы", callback_data="all_docs"),
         InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu")]
    ])
    
    await message.answer(welcome, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("documents"))
async def cmd_documents(message: Message):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM documents ORDER BY created_at DESC LIMIT 5') as cursor:
            docs = await cursor.fetchall()
    
    if not docs:
        await message.answer("📭 Пока нет документов в базе")
        return
    
    text = "<b>📜 ПОСЛЕДНИЕ ДОКУМЕНТЫ</b>\n\n"
    
    for i, doc in enumerate(docs, 1):
        type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
        cat_info = CATEGORIES.get(doc['category'], {'name': doc['category']})
        
        text += f"{i}. {type_info['icon']} <b>{doc['title'][:80]}</b>\n"
        text += f"   <code>{doc['doc_number']}</code>\n"
        text += f"   📅 {doc['date_published']} | {cat_info['name']}\n"
        text += f"   <a href='{doc['url']}'>Открыть →</a>\n\n"
    
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    cat_stats = await get_all_categories_stats()
    
    text = "<b>📁 КАТЕГОРИИ ЗАКОНОДАТЕЛЬСТВА</b>\n\n"
    
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    
    text = f"<b>📊 СТАТИСТИКА</b>\n\n<b>📚 Всего документов: {total_docs}</b>\n\n<b>📁 По категориям:</b>\n"
    
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁'})
            text += f"\n{info['icon']} {info['name']}: {count}"
    
    # Добавляем информацию о последней проверке
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM check_logs ORDER BY check_time DESC LIMIT 1'
        ) as cursor:
            last_check = await cursor.fetchone()
            if last_check:
                text += f"\n\n<b>🕐 Последняя проверка:</b>\n{last_check['check_time']}"
                if last_check['status'] == 'error':
                    text += f"\n⚠️ Ошибка: {last_check['error_message'][:100]}"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("""
<b>❓ ПОМОЩЬ — KPMG Law LexBot</b>

<b>📋 Команды:</b>
/start — Начать работу
/documents — Все документы
/categories — По категориям
/stats — Статистика
/help — Помощь

<b>🏛️ KPMG Law Uzbekistan</b>
""", parse_mode="HTML")

@dp.callback_query(F.data == "all_docs")
async def callback_all_docs(callback: CallbackQuery):
    await cmd_documents(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "categories_menu")
async def callback_categories_menu(callback: CallbackQuery):
    await cmd_categories(callback.message)
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def callback_category(callback: CallbackQuery):
    category = callback.data.replace("cat_", "")
    
    if category not in CATEGORIES:
        await callback.answer("Категория не найдена")
        return
    
    cat_info = CATEGORIES[category]
    docs = await get_documents_by_category(category, limit=10)
    
    if not docs:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n📭 Нет документов"
    else:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n📚 Найдено: <b>{len(docs)}</b>\n\n"
        for i, doc in enumerate(docs, 1):
            text += f"{i}. <b>{doc['title'][:60]}</b>\n   <a href='{doc['url']}'>Открыть →</a>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="categories_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "unsubscribe")
async def callback_unsubscribe(callback: CallbackQuery):
    await remove_subscriber(callback.from_user.id)
    await callback.message.edit_text("❌ <b>Уведомления отключены</b>", parse_mode="HTML")
    await callback.answer()

# ==================== RAILWAY WEBHOOK MODE ====================

async def on_startup_webhook(bot: Bot, webhook_url: str):
    try:
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        logger.info(f"Webhook установлен: {webhook_url}")
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")

async def on_shutdown(bot: Bot):
    try:
        scheduler.shutdown()
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке: {e}")

async def main_webhook():
    """Режим WEBHOOK для Railway"""
    logger.info("Starting LexBot in WEBHOOK mode...")
    
    await init_database()
    
    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='lexuz_check',
        name='Check Lex.uz',
        replace_existing=True,
        misfire_grace_time=300
    )
    scheduler.start()
    logger.info(f"Scheduler started (interval: {CHECK_INTERVAL} min)")
    
    RAILWAY_STATIC_URL = os.getenv("RAILWAY_STATIC_URL")
    RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    
    if RAILWAY_STATIC_URL:
        WEBHOOK_HOST = f"https://{RAILWAY_STATIC_URL}"
    elif RAILWAY_PUBLIC_DOMAIN:
        WEBHOOK_HOST = f"https://{RAILWAY_PUBLIC_DOMAIN}"
    else:
        logger.error("Не найден домен Railway!")
        return
    
    WEBHOOK_PATH = f"/bot{BOT_TOKEN}"
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    
    await on_startup_webhook(bot, WEBHOOK_URL)
    
    from aiohttp import web
    
    async def handle_webhook(request):
        token = request.match_info.get('token', '')
        if token != BOT_TOKEN:
            return web.Response(status=403, text="Forbidden")
        
        try:
            data = await request.json()
            update = types.Update(**data)
            await dp.feed_update(bot, update)
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return web.Response(status=500, text="Internal Server Error")
    
    async def health_check(request):
        return web.Response(
            text="LexBot is running!",
            headers={'Content-Type': 'text/plain'}
        )
    
    app = web.Application()
    app.router.add_post(f'/bot{BOT_TOKEN}', handle_webhook)
    app.router.add_get('/health', health_check)
    app.on_cleanup.append(lambda app: asyncio.create_task(on_shutdown(bot)))
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    PORT = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    
    logger.info(f"Server started on port {PORT}")
    await site.start()
    
    # Бесконечный цикл с проверкой здоровья
    while True:
        await asyncio.sleep(3600)

async def main_polling():
    """Режим POLLING для локальной разработки"""
    logger.info("Starting LexBot in POLLING mode...")
    
    await init_database()
    
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
    except Exception as e:
        logger.error(f"Polling error: {e}")
    finally:
        await on_shutdown(bot)

if __name__ == "__main__":
    if os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        asyncio.run(main_webhook())
    else:
        asyncio.run(main_polling())