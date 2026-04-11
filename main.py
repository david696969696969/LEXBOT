#!/usr/bin/env python3
"""
LexBot - KPMG Law Uzbekistan
Real-time Lex.uz parser
"""

import asyncio
import logging
import os
import sys
import json
import re
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, quote

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
    'tax': {'name': 'Taxes', 'icon': '💰', 'desc': 'Tax legislation'},
    'economy': {'name': 'Economy', 'icon': '📈', 'desc': 'Business and investments'},
    'labor': {'name': 'Labor Law', 'icon': '👷', 'desc': 'Labor relations'},
    'digital': {'name': 'IT & Digital', 'icon': '💻', 'desc': 'Digital technologies'},
    'civil': {'name': 'Civil Law', 'icon': '⚖️', 'desc': 'Contracts and property'},
    'criminal': {'name': 'Criminal', 'icon': '🚔', 'desc': 'Criminal law'},
    'administrative': {'name': 'Administrative', 'icon': '📋', 'desc': 'Administrative law'},
    'banking': {'name': 'Banking', 'icon': '🏦', 'desc': 'Banking and finance'},
    'inheritance': {'name': 'Inheritance', 'icon': '📜', 'desc': 'Inheritance law'},
    'constitution': {'name': 'Constitution', 'icon': '🏛️', 'desc': 'Constitutional law'},
}

DOC_TYPES = {
    'law': {'name': 'Law', 'icon': '📜'},
    'decree': {'name': 'Presidential Decree', 'icon': '⚡'},
    'resolution': {'name': 'Cabinet Resolution', 'icon': '📋'},
    'order': {'name': 'Order', 'icon': '📄'},
    'constitution': {'name': 'Constitution', 'icon': '🏛️'},
}

LEX_UZ_BASE = "https://lex.uz"

# Session for requests
session: Optional[aiohttp.ClientSession] = None

async def get_session() -> aiohttp.ClientSession:
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
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

# ==================== PARSER ====================

async def parse_lexuz_search(query: str = "", category: str = "", page: int = 1) -> List[Dict]:
    """Parse search results from Lex.uz"""
    try:
        sess = await get_session()
        
        # Search URL
        search_url = f"{LEX_UZ_BASE}/search"
        params = {
            'q': query or '',
            'page': page,
            'sort': 'date_desc'
        }
        
        if category:
            params['category'] = category
            
        async with sess.get(search_url, params=params, timeout=30) as response:
            if response.status != 200:
                logger.error(f"Search failed: {response.status}")
                return []
                
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            documents = []
            
            # Find document cards
            doc_cards = soup.find_all('div', class_=['doc-card', 'search-item', 'document-item'])
            if not doc_cards:
                # Try alternative selectors
                doc_cards = soup.find_all('div', class_=lambda x: x and ('doc' in x.lower() or 'result' in x.lower()))
            
            for card in doc_cards[:10]:  # Limit to 10
                try:
                    # Extract title
                    title_elem = card.find(['h3', 'h4', 'a', 'div'], class_=lambda x: x and ('title' in str(x).lower()))
                    if not title_elem:
                        title_elem = card.find('a')
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                    
                    # Extract URL
                    url_elem = card.find('a', href=True)
                    url = urljoin(LEX_UZ_BASE, url_elem['href']) if url_elem else ""
                    doc_id = get_doc_id_from_url(url)
                    
                    # Extract number
                    number_elem = card.find(['span', 'div'], class_=lambda x: x and ('number' in str(x).lower() or 'code' in str(x).lower()))
                    doc_number = number_elem.get_text(strip=True) if number_elem else (doc_id or "Unknown")
                    
                    # Extract date
                    date_elem = card.find(['span', 'div'], class_=lambda x: x and 'date' in str(x).lower())
                    date_str = date_elem.get_text(strip=True) if date_elem else datetime.now().strftime("%d.%m.%Y")
                    
                    # Extract description
                    desc_elem = card.find(['div', 'p'], class_=lambda x: x and 'desc' in str(x).lower())
                    description = desc_elem.get_text(strip=True)[:200] if desc_elem else ""
                    
                    if title and url:
                        documents.append({
                            'title': title,
                            'doc_number': doc_number,
                            'url': url,
                            'date_published': date_str,
                            'description': description,
                            'doc_id': doc_id
                        })
                        
                except Exception as e:
                    logger.error(f"Parse card error: {e}")
                    continue
                    
            logger.info(f"Found {len(documents)} documents")
            return documents
            
    except Exception as e:
        logger.error(f"Parser error: {e}")
        return []

async def parse_lexuz_main_page() -> List[Dict]:
    """Parse main page for latest documents"""
    try:
        sess = await get_session()
        async with sess.get(LEX_UZ_BASE, timeout=30) as response:
            if response.status != 200:
                return []
                
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            documents = []
            
            # Look for latest documents section
            sections = soup.find_all(['section', 'div'], class_=lambda x: x and ('latest' in str(x).lower() or 'new' in str(x).lower() or 'recent' in str(x).lower()))
            
            for section in sections:
                links = section.find_all('a', href=re.compile(r'/docs/\d+'))
                for link in links[:10]:
                    try:
                        title = link.get_text(strip=True)
                        url = urljoin(LEX_UZ_BASE, link['href'])
                        doc_id = get_doc_id_from_url(url)
                        
                        if title and doc_id:
                            documents.append({
                                'title': title,
                                'doc_number': f"LEX-{doc_id}",
                                'url': url,
                                'date_published': datetime.now().strftime("%d.%m.%Y"),
                                'description': "Latest document from Lex.uz",
                                'doc_id': doc_id
                            })
                    except:
                        continue
                        
            return documents
            
    except Exception as e:
        logger.error(f"Main page parse error: {e}")
        return []

async def parse_lexuz_by_category(category_key: str) -> List[Dict]:
    """Parse category page"""
    category_urls = {
        'tax': '/category/nalogi',
        'banking': '/category/banki',
        'labor': '/category/trud',
        'economy': '/category/ekonomika',
        'civil': '/category/grazhdanskoe-pravo',
        'criminal': '/category/ugolovnoe-pravo',
        'constitution': '/category/konstitutsiya',
    }
    
    path = category_urls.get(category_key, f'/category/{category_key}')
    
    try:
        sess = await get_session()
        url = urljoin(LEX_UZ_BASE, path)
        
        async with sess.get(url, timeout=30) as response:
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
                    
                    if title and doc_id and len(title) > 5:
                        documents.append({
                            'title': title,
                            'doc_number': f"LEX-{doc_id}",
                            'url': url,
                            'date_published': datetime.now().strftime("%d.%m.%Y"),
                            'description': f"Document from {CATEGORIES.get(category_key, {}).get('name', category_key)} category",
                            'doc_id': doc_id
                        })
                except:
                    continue
                    
            return documents
            
    except Exception as e:
        logger.error(f"Category parse error: {e}")
        return []

# ==================== DATABASE ====================

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
        async with db.execute(
            'SELECT * FROM documents WHERE doc_number = ?', (doc_number,)
        ) as cursor:
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
            async with db.execute(
                'SELECT COUNT(*) FROM documents WHERE category = ?', (cat_key,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
                stats[cat_key] = count
        return stats

# ==================== DOCUMENT LOADER ====================

async def load_documents_from_parser():
    """Load documents using parser"""
    all_docs = []
    
    # Parse main page for latest
    logger.info("Parsing main page...")
    main_docs = await parse_lexuz_main_page()
    for doc in main_docs:
        doc['category'] = 'constitution'
        doc['doc_type'] = 'law'
        all_docs.append(doc)
    
    # Parse by category
    for cat_key in ['tax', 'banking', 'labor', 'economy', 'civil']:
        logger.info(f"Parsing category: {cat_key}")
        cat_docs = await parse_lexuz_by_category(cat_key)
        for doc in cat_docs:
            doc['category'] = cat_key
            doc['doc_type'] = 'law'
            all_docs.append(doc)
        await asyncio.sleep(2)  # Be nice to server
    
    # Search for specific terms
    logger.info("Searching for documents...")
    search_docs = await parse_lexuz_search("2024")
    for doc in search_docs:
        if not doc.get('category'):
            doc['category'] = 'economy'
        doc['doc_type'] = 'law'
        all_docs.append(doc)
    
    return all_docs

async def check_new_documents():
    """Check and load new documents"""
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
                
                # Create document object for notification
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
        
        logger.info(f"Added {new_count} new documents")
        
    except Exception as e:
        logger.error(f"Check error: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def notify_subscribers(doc: LawDocument):
    """Notify about new document"""
    subscribers = await get_all_subscribers()
    type_info = DOC_TYPES.get(doc.doc_type, {'name': 'Document', 'icon': '📄'})
    cat_info = CATEGORIES.get(doc.category, {'name': doc.category, 'icon': '📁'})
    
    message = f"""
🆕 <b>NEW DOCUMENT</b>

{type_info['icon']} <b>{doc.title}</b>

<b>📋 Information:</b>
• Type: {type_info['name']}
• Number: <code>{doc.doc_number}</code>
• Category: {cat_info['icon']} {cat_info['name']}
• Date: {doc.date_published or 'N/A'}

<b>📝 Description:</b>
{doc.description[:300] if doc.description else 'No description'}

<b>🔗 Link:</b> <a href="{doc.url}">Open on Lex.uz →</a>
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Open Document", url=doc.url)],
        [InlineKeyboardButton(text=f"{cat_info['icon']} More {cat_info['name']}", 
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

# ==================== HANDLERS ====================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    await add_subscriber(user.id, user.username or "", user.first_name or "")
    
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    
    welcome = f"""
🏛️ <b>KPMG Law Uzbekistan — LexBot</b>

Hello, {user.first_name}!

🤖 I monitor Uzbekistan legislation from <b>Lex.uz</b> in real-time.

📊 <b>Database:</b> {total_docs} documents
📁 <b>Categories:</b> {len(CATEGORIES)}

<b>⚡ Features:</b>
• Real-time parsing from Lex.uz
• Working document links
• Category filtering
• Instant notifications

<b>📋 Commands:</b>
/documents — Latest documents
/categories — Browse by category
/search — Search documents
/stats — Statistics
/help — Help
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Documents", callback_data="all_docs"),
         InlineKeyboardButton(text="📁 Categories", callback_data="categories_menu")],
    ])
    
    await message.answer(welcome, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("documents"))
async def cmd_documents(message: Message):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM documents ORDER BY created_at DESC LIMIT 10'
        ) as cursor:
            docs = await cursor.fetchall()
    
    if not docs:
        await message.answer("📭 No documents yet. Use /parse to load from Lex.uz")
        return
    
    text = "<b>📜 LATEST DOCUMENTS FROM LEX.UZ</b>\n\n"
    for i, doc in enumerate(docs, 1):
        type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
        cat_info = CATEGORIES.get(doc['category'], {'name': doc['category']})
        text += f"{i}. {type_info['icon']} <b>{doc['title'][:60]}...</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | {cat_info['name']}\n"
        text += f"   <a href='{doc['url']}'>🔗 Open on Lex.uz</a>\n\n"
    
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)

@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    cat_stats = await get_all_categories_stats()
    
    text = "<b>📁 CATEGORIES</b>\n\n"
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
    """Search documents"""
    args = message.text.replace("/search", "").strip()
    
    if not args:
        await message.answer(
            "🔍 <b>SEARCH</b>\n\n"
            "Usage: <code>/search keyword</code>\n\n"
            "Examples:\n"
            "/search tax\n"
            "/search banking\n"
            "/search labor",
            parse_mode="HTML"
        )
        return
    
    await message.answer(f"🔍 Searching for: <b>{args}</b>...", parse_mode="HTML")
    
    # Search via parser
    results = await parse_lexuz_search(args)
    
    if not results:
        await message.answer(f"❌ No results found for: {args}")
        return
    
    text = f"<b>🔍 SEARCH RESULTS: {args}</b>\n\n"
    for i, doc in enumerate(results[:5], 1):
        text += f"{i}. 📄 <b>{doc['title'][:80]}...</b>\n"
        text += f"   <a href='{doc['url']}'>🔗 Open</a>\n\n"
    
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)

@dp.message(Command("parse"))
async def cmd_parse(message: Message):
    """Manual parse trigger"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Admin only")
        return
    
    await message.answer("🔄 Parsing Lex.uz...")
    await check_new_documents()
    await message.answer("✅ Parsing complete!")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    cat_stats = await get_all_categories_stats()
    total = sum(cat_stats.values())
    
    text = f"<b>📊 STATISTICS</b>\n\nTotal: <b>{total}</b> documents\n\n"
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁'})
            text += f"{info['icon']} {info['name']}: <b>{count}</b>\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
<b>❓ HELP — LexBot</b>

<b>📋 Commands:</b>
/start — Start bot
/documents — Latest from Lex.uz
/categories — Browse categories
/search [keyword] — Search
/parse — Load new (admin)
/stats — Statistics
/help — This help

<b>🔍 All links open directly on Lex.uz</b>
"""
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Access denied")
        return
    
    try:
        if os.path.exists(DATABASE_PATH):
            os.remove(DATABASE_PATH)
        await init_database()
        await message.answer("✅ Database reset! Use /parse to load documents.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

# Callbacks
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
        await callback.answer("Category not found")
        return
    
    cat_info = CATEGORIES[category]
    docs = await get_documents_by_category(category, limit=10)
    
    if not docs:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\nNo documents yet."
    else:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        for i, doc in enumerate(docs, 1):
            text += f"{i}. 📄 {doc['title'][:50]}...\n"
            text += f"   <a href='{doc['url']}'>🔗 Open</a>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="categories_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# Main
async def on_startup():
    await init_database()

async def on_shutdown():
    global session
    if session and not session.closed:
        await session.close()
    scheduler.shutdown()

async def main():
    logger.info("Starting LexBot with parser...")
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Check if empty and load
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM documents') as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                logger.info("Database empty, loading from Lex.uz...")
                await check_new_documents()
    
    # Schedule regular parsing
    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='parse',
        replace_existing=True
    )
    scheduler.start()
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")