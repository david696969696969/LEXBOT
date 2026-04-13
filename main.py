#!/usr/bin/env python3
# LexBot - исправленная версия
import asyncio
import logging
import os
import sys
import json
import re
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'lexbot.db')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found!")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

CATEGORIES = {
    'tax': {'name': 'Налоги и сборы', 'icon': '💰'},
    'economy': {'name': 'Экономика и бизнес', 'icon': '📈'},
    'labor': {'name': 'Трудовое право', 'icon': '👷'},
    'digital': {'name': 'IT и цифровизация', 'icon': '💻'},
    'civil': {'name': 'Гражданское право', 'icon': '⚖️'},
    'criminal': {'name': 'Уголовное право', 'icon': '🚔'},
    'administrative': {'name': 'Административное право', 'icon': '📋'},
    'banking': {'name': 'Банковское дело', 'icon': '🏦'},
    'inheritance': {'name': 'Наследственное право', 'icon': '📜'},
    'constitution': {'name': 'Конституция', 'icon': '🏛️'},
    'environment': {'name': 'Экология', 'icon': '🌿'},
    'health': {'name': 'Здравоохранение', 'icon': '🏥'},
    'education': {'name': 'Образование', 'icon': '🎓'},
    'construction': {'name': 'Строительство', 'icon': '🏗️'},
    'trade': {'name': 'Торговля', 'icon': '🌍'},
}

DOC_TYPES = {
    'law': {'name': 'Закон', 'icon': '📜'},
    'decree': {'name': 'Указ Президента', 'icon': '⚡'},
    'resolution': {'name': 'Постановление КМ', 'icon': '📋'},
    'order': {'name': 'Приказ', 'icon': '📄'},
    'constitution': {'name': 'Конституция', 'icon': '🏛️'},
}

LEX_UZ_BASE = "https://lex.uz"
session = None

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'ru-RU,ru;q=0.9',
            }
        )
    return session

def clean_url(url: str) -> str:
    if not url:
        return LEX_UZ_BASE
    url = re.sub(r'<[^>]+>', '', url).strip()
    if url.startswith('/'):
        url = urljoin(LEX_UZ_BASE, url)
    elif not url.startswith('http'):
        url = f"{LEX_UZ_BASE}/docs/{url}"
    return url

def get_doc_id_from_url(url: str) -> Optional[str]:
    match = re.search(r'/docs/(\d+)', url)
    return match.group(1) if match else None

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
    changes: list
    version: int = 1

async def parse_lexuz_main_page() -> List[Dict]:
    try:
        sess = await get_session()
        async with sess.get(LEX_UZ_BASE, timeout=30) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            documents = []
            
            links = soup.find_all('a', href=re.compile(r'/docs/\d+'))
            for link in links[:15]:
                try:
                    title = link.get_text(strip=True)
                    url = urljoin(LEX_UZ_BASE, link['href'])
                    doc_id = get_doc_id_from_url(url)
                    
                    if title and doc_id and len(title) > 3:
                        documents.append({
                            'title': title,
                            'doc_number': f"LEX-{doc_id}",
                            'url': url,
                            'date_published': datetime.now().strftime("%d.%m.%Y"),
                            'description': "Документ с Lex.uz",
                            'doc_id': doc_id
                        })
                except:
                    continue
            return documents
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return []

async def parse_lexuz_by_category(category_key: str) -> List[Dict]:
    category_urls = {
        'tax': '/ru/acts?sort=date&direction=desc&categ=13',
        'banking': '/ru/acts?sort=date&direction=desc&categ=22',
        'labor': '/ru/acts?sort=date&direction=desc&categ=11',
        'economy': '/ru/acts?sort=date&direction=desc&categ=1',
        'civil': '/ru/acts?sort=date&direction=desc&categ=2',
        'criminal': '/ru/acts?sort=date&direction=desc&categ=3',
        'constitution': '/ru/acts?sort=date&direction=desc&categ=0',
    }
    
    path = category_urls.get(category_key, '/ru/acts?sort=date&direction=desc')
    
    try:
        sess = await get_session()
        url = urljoin(LEX_UZ_BASE, path)
        
        async with sess.get(url, timeout=30) as response:
            if response.status != 200:
                return []
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            documents = []
            
            rows = soup.find_all('tr')
            for row in rows[:15]:
                try:
                    link = row.find('a', href=re.compile(r'/docs/\d+'))
                    if not link:
                        continue
                    title = link.get_text(strip=True)
                    url = urljoin(LEX_UZ_BASE, link['href'])
                    doc_id = get_doc_id_from_url(url)
                    
                    if title and doc_id and len(title) > 3:
                        documents.append({
                            'title': title,
                            'doc_number': f"LEX-{doc_id}",
                            'url': url,
                            'date_published': datetime.now().strftime("%d.%m.%Y"),
                            'description': f"Документ: {CATEGORIES.get(category_key, {}).get('name', category_key)}",
                            'doc_id': doc_id
                        })
                except:
                    continue
            return documents
    except Exception as e:
        logger.error(f"Category error: {e}")
        return []

async def init_database():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                doc_type TEXT,
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS check_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                new_count INTEGER DEFAULT 0,
                status TEXT
            )
        """)
        await db.commit()
    logger.info("Database initialized")

async def add_subscriber(user_id: int, username: str, first_name: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO subscribers (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        await db.commit()

async def get_all_subscribers():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM subscribers') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_document_by_number(doc_number: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM documents WHERE doc_number = ?', (doc_number,)) as cursor:
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                result['url'] = clean_url(result['url'])
                return result
            return None

async def get_documents_by_category(category: str, limit: int = 10):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM documents 
            WHERE category = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (category, limit)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                doc = dict(row)
                doc['url'] = clean_url(doc['url'])
                results.append(doc)
            return results

async def get_all_categories_stats():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        stats = {}
        for cat_key in CATEGORIES.keys():
            async with db.execute('SELECT COUNT(*) FROM documents WHERE category = ?', (cat_key,)) as cursor:
                count = (await cursor.fetchone())[0]
                stats[cat_key] = count
        return stats

async def get_latest_documents(limit: int = 10):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM documents 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                doc = dict(row)
                doc['url'] = clean_url(doc['url'])
                results.append(doc)
            return results

async def load_documents_from_parser():
    all_docs = []
    
    logger.info("Parsing main page...")
    main_docs = await parse_lexuz_main_page()
    for doc in main_docs:
        doc['category'] = 'constitution'
        doc['doc_type'] = 'law'
        all_docs.append(doc)
    
    for cat_key in ['tax', 'banking', 'labor', 'economy', 'civil']:
        logger.info(f"Parsing category: {cat_key}")
        cat_docs = await parse_lexuz_by_category(cat_key)
        for doc in cat_docs:
            doc['category'] = cat_key
            doc['doc_type'] = 'law'
            all_docs.append(doc)
        await asyncio.sleep(1)
    
    return all_docs

async def check_new_documents():
    logger.info("Checking for new documents...")
    try:
        new_docs = await load_documents_from_parser()
        new_count = 0
        
        for doc_data in new_docs:
            existing = await get_document_by_number(doc_data['doc_number'])
            if not existing:
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute("""
                        INSERT INTO documents 
                        (title, doc_type, doc_number, date_published, category, 
                         description, url, status, changes, version)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        doc_data['title'],
                        doc_data.get('doc_type', 'law'),
                        doc_data['doc_number'],
                        doc_data.get('date_published', datetime.now().strftime("%d.%m.%Y")),
                        doc_data.get('category', 'economy'),
                        doc_data.get('description', ''),
                        doc_data['url'],
                        'new',
                        json.dumps([]),
                        1
                    ))
                    await db.commit()
                new_count += 1
                
                doc = LawDocument(
                    id=0,
                    title=doc_data['title'],
                    doc_type=doc_data.get('doc_type', 'law'),
                    doc_number=doc_data['doc_number'],
                    date_published=doc_data.get('date_published', ''),
                    date_effective=None,
                    category=doc_data.get('category', 'economy'),
                    description=doc_data.get('description', ''),
                    full_text='',
                    url=doc_data['url'],
                    status='new',
                    changes=[],
                    version=1
                )
                await notify_subscribers(doc)
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO check_logs (new_count, status) VALUES (?, ?)",
                (new_count, 'success')
            )
            await db.commit()
        
        logger.info(f"Added {new_count} new documents")
        
    except Exception as e:
        logger.error(f"Check error: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def notify_subscribers(doc: LawDocument):
    subscribers = await get_all_subscribers()
    type_info = DOC_TYPES.get(doc.doc_type, {'name': 'Документ', 'icon': '📄'})
    cat_info = CATEGORIES.get(doc.category, {'name': doc.category, 'icon': '📁'})
    
    message = f"""
🆕 <b>НОВЫЙ ДОКУМЕНТ</b>

{type_info['icon']} <b>{doc.title}</b>

<b>📋 Информация:</b>
• Тип: {type_info['name']}
• Номер: <code>{doc.doc_number}</code>
• Категория: {cat_info['icon']} {cat_info['name']}
• Дата: {doc.date_published or 'N/A'}

<b>📝 Описание:</b>
{doc.description[:300] if doc.description else 'Нет описания'}

<b>🔗 Ссылка:</b> <a href="{doc.url}">Открыть на Lex.uz →</a>
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Открыть документ", url=doc.url)],
        [InlineKeyboardButton(text=f"{cat_info['icon']} Ещё {cat_info['name']}", 
                            callback_data=f"cat_{doc.category}")],
    ])
    
    for sub in subscribers:
        try:
            await bot.send_message(
                sub['user_id'],
                message,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Notify error: {e}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    await add_subscriber(user.id, user.username or "", user.first_name or "")
    
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    
    welcome = f"""
🏛️ <b>KPMG Law Uzbekistan — LexBot</b>

Привет, {user.first_name}!

🤖 Я мониторю законодательство Узбекистана с <b>Lex.uz</b> в реальном времени.

📊 <b>База данных:</b> {total_docs} документов
📁 <b>Категории:</b> {len(CATEGORIES)}

<b>⚡ Возможности:</b>
• Автоматический парсинг Lex.uz
• Рабочие ссылки на документы
• Фильтрация по категориям
• Мгновенные уведомления

<b>📋 Команды:</b>
/documents — Последние документы
/categories — Категории
/search — Поиск документов
/stats — Статистика
/help — Помощь
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Документы", callback_data="all_docs"),
         InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu")],
    ])
    
    await message.answer(welcome, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("documents"))
async def cmd_documents(message: Message):
    docs = await get_latest_documents(10)
    
    if not docs:
        await message.answer("📭 Пока нет документов. Используйте /parse для загрузки с Lex.uz")
        return
    
    text = "<b>📜 ПОСЛЕДНИЕ ДОКУМЕНТЫ С LEX.UZ</b>\n\n"
    
    for i, doc in enumerate(docs, 1):
        type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
        cat_info = CATEGORIES.get(doc['category'], {'name': doc['category']})
        
        text += f"{i}. {type_info['icon']} <b>{doc['title'][:60]}</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | {cat_info['name']}\n"
        text += f"   <a href='{doc['url']}'>🔗 Открыть на Lex.uz</a>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="all_docs")],
        [InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu")],
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)

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

@dp.message(Command("search"))
async def cmd_search(message: Message):
    args = message.text.replace("/search", "").strip()
    
    if not args:
        await message.answer(
            "🔍 <b>ПОИСК</b>\n\n"
            "Использование: <code>/search ключевое слово</code>\n\n"
            "Примеры:\n"
            "/search налог\n"
            "/search банк\n"
            "/search труд",
            parse_mode="HTML"
        )
        return
    
    await message.answer(f"🔍 Ищу: <b>{args}</b>...", parse_mode="HTML")
    
    results = await parse_lexuz_search(args)
    
    if not results:
        await message.answer(f"❌ Ничего не найдено по запросу: {args}")
        return
    
    text = f"<b>🔍 РЕЗУЛЬТАТЫ ПОИСКА: {args}</b>\n\n"
    for i, doc in enumerate(results[:5], 1):
        text += f"{i}. 📄 <b>{doc['title'][:80]}</b>\n"
        text += f"   <a href='{doc['url']}'>🔗 Открыть</a>\n\n"
    
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(Command("parse"))
async def cmd_parse(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Только для администратора")
        return
    
    await message.answer("🔄 Парсинг Lex.uz...")
    await check_new_documents()
    await message.answer("✅ Парсинг завершён!")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    cat_stats = await get_all_categories_stats()
    total = sum(cat_stats.values())
    
    text = f"<b>📊 СТАТИСТИКА</b>\n\nВсего: <b>{total}</b> документов\n\n"
    
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁'})
            text += f"{info['icon']} {info['name']}: <b>{count}</b>\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
<b>❓ ПОМОЩЬ — LexBot</b>

<b>📋 Команды:</b>
/start — Начать работу
/documents — Последние документы
/categories — Категории
/search [слово] — Поиск
/parse — Загрузить новые (админ)
/stats — Статистика
/help — Эта справка

<b>🔍 Все ссылки открываются напрямую на Lex.uz</b>
"""
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещён")
        return
    
    try:
        if os.path.exists(DATABASE_PATH):
            os.remove(DATABASE_PATH)
        await init_database()
        await message.answer("✅ База данных сброшена! Используйте /parse для загрузки.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

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
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\nПока нет документов в этой категории."
    else:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        for i, doc in enumerate(docs, 1):
            text += f"{i}. 📄 {doc['title'][:50]}...\n"
            text += f"   <a href='{doc['url']}'>🔗 Открыть</a>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="categories_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

async def on_startup():
    await init_database()

async def on_shutdown():
    global session
    if session and not session.closed:
        await session.close()
    scheduler.shutdown()

async def main():
    logger.info("Starting LexBot...")

    await init_database()
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM documents') as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                logger.info("База пуста, загружаем с Lex.uz...")
                await check_new_documents()
    
    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='parse',
        replace_existing=True
    )
    scheduler.start()
    
    logger.info("Bot started!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
