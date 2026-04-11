#!/usr/bin/env python3
"""
LexBot - KPMG Law Uzbekistan
Monitoring legislation with history tracking
"""

import asyncio
import logging
import os
import sys
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# Configure stdout for UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'lexbot.db')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found!")
    sys.exit(1)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Categories (English to avoid encoding issues)
CATEGORIES = {
    'tax': {'name': 'Taxes', 'icon': '💰', 'desc': 'Tax legislation, benefits, reporting'},
    'economy': {'name': 'Economy & Business', 'icon': '📈', 'desc': 'Entrepreneurship, investments, procurement'},
    'labor': {'name': 'Labor Law', 'icon': '👷', 'desc': 'Labor relations, wages, vacations'},
    'digital': {'name': 'IT & Digital', 'icon': '💻', 'desc': 'AI, robotics, cybersecurity, e-government'},
    'civil': {'name': 'Civil Law', 'icon': '⚖️', 'desc': 'Contracts, property, inheritance'},
    'criminal': {'name': 'Criminal Law', 'icon': '🚔', 'desc': 'Criminal code, crimes, punishments'},
    'administrative': {'name': 'Administrative', 'icon': '📋', 'desc': 'Administrative procedures, fines'},
    'environment': {'name': 'Environment', 'icon': '🌿', 'desc': 'Environmental protection, natural resources'},
    'health': {'name': 'Healthcare', 'icon': '🏥', 'desc': 'Medicine, pharmaceuticals, sanitary norms'},
    'education': {'name': 'Education', 'icon': '🎓', 'desc': 'Schools, universities, certification'},
    'finance': {'name': 'Finance & Banking', 'icon': '🏦', 'desc': 'Banking regulation, currency control'},
    'trade': {'name': 'Trade & Customs', 'icon': '🌍', 'desc': 'Foreign trade, customs procedures'},
    'construction': {'name': 'Construction', 'icon': '🏗️', 'desc': 'Building codes, real estate, utilities'},
    'transport': {'name': 'Transport', 'icon': '🚛', 'desc': 'Auto, aviation, railway, logistics'},
    'energy': {'name': 'Energy', 'icon': '⚡', 'desc': 'Electricity, gas, renewable sources'},
    'banking': {'name': 'Banking', 'icon': '🏦', 'desc': 'Banks, loans, deposits, payments'},
    'inheritance': {'name': 'Inheritance Law', 'icon': '📜', 'desc': 'Inheritance, wills, succession'},
}

# Document types
DOC_TYPES = {
    'law': {'name': 'Law', 'icon': '📜'},
    'decree': {'name': 'Presidential Decree', 'icon': '⚡'},
    'resolution': {'name': 'Cabinet Resolution', 'icon': '📋'},
    'order': {'name': 'Order', 'icon': '📄'},
    'regulation': {'name': 'Regulation', 'icon': '📑'},
    'court': {'name': 'Court Practice', 'icon': '⚖️'},
}

# URL cleaning function
def clean_url(url: str) -> str:
    """Remove HTML tags and clean URL"""
    if not url:
        return ""
    # Remove HTML tags
    url = re.sub(r'<[^>]+>', '', url)
    # Remove whitespace
    url = url.strip()
    # Ensure proper format
    if not url.startswith('http'):
        url = 'https://lex.uz/docs/' + url.replace('https://lex.uz/docs/', '')
    return url

# Data models
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

# Database functions
async def init_database():
    """Initialize database tables"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database initialized")

async def add_subscriber(user_id: int, username: str, first_name: str):
    """Add user to subscribers"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO subscribers (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        await db.commit()

async def log_action(user_id: int, username: str, first_name: str, action: str):
    """Log user action"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO user_logs (user_id, username, first_name, action)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, action))
        await db.commit()

async def get_all_subscribers() -> List[Dict]:
    """Get all subscribers"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM subscribers') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_document_by_number(doc_number: str) -> Optional[Dict]:
    """Get document by number with URL cleaning"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM documents WHERE doc_number = ?', (doc_number,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('url'):
                    result['url'] = clean_url(result['url'])
                return result
            return None

async def get_documents_by_category(category: str, limit: int = 10) -> List[Dict]:
    """Get documents by category with URL cleaning"""
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
                if doc.get('url'):
                    doc['url'] = clean_url(doc['url'])
                results.append(doc)
            return results

async def get_all_categories_stats() -> Dict[str, int]:
    """Get document count by category"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        stats = {}
        for cat_key in CATEGORIES.keys():
            async with db.execute(
                'SELECT COUNT(*) FROM documents WHERE category = ?', (cat_key,)
            ) as cursor:
                count = (await cursor.fetchone())[0]
                stats[cat_key] = count
        return stats

# Demo data generator
async def fetch_demo_documents() -> List[LawDocument]:
    """Generate demo documents"""
    docs = [
        LawDocument(
            id=0,
            title="On Amendments to the Tax Code of Uzbekistan",
            doc_type="law",
            doc_number="ZRU-2024-1234",
            date_published=datetime.now().strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y"),
            category="tax",
            description="Amendments regarding taxation of IT companies and startups. Reduced profit tax rates established.",
            full_text="Full text of the law...",
            url="https://lex.uz/docs/1234",
            status="new",
            version=2,
            changes=[
                LawChange("Art. 123", "20%", "7%", "modified", "Reduced tax rate for IT"),
                LawChange("Art. 124", "-", "Startup exemption", "added", "Tax exemption for first 3 years"),
            ]
        ),
        LawDocument(
            id=0,
            title="On Development of Artificial Intelligence and Digital Technologies",
            doc_type="decree",
            doc_number="UP-2024-4567",
            date_published=(datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y"),
            date_effective=datetime.now().strftime("%d.%m.%Y"),
            category="digital",
            description="Established National Agency for AI Regulation. Approved AI Development Concept until 2030.",
            full_text="Full text of the decree...",
            url="https://lex.uz/docs/4567",
            status="new",
            version=1,
            changes=[
                LawChange("Full document", "-", "New decree", "added", "Creation of AI agency"),
            ]
        ),
        LawDocument(
            id=0,
            title="On Approval of Rules for Registration of Robotic Systems",
            doc_type="resolution",
            doc_number="PKM-2024-789",
            date_published=(datetime.now() - timedelta(days=2)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=15)).strftime("%d.%m.%Y"),
            category="digital",
            description="Established state registration procedure for industrial and service robots. Safety requirements introduced.",
            full_text="Full text of the resolution...",
            url="https://lex.uz/docs/789",
            status="new",
            version=1,
            changes=[
                LawChange("Section 1", "-", "Registration rules", "added", "Mandatory registration of all robots"),
                LawChange("Section 2", "-", "Safety requirements", "added", "ISO 10218 certification"),
            ]
        ),
        LawDocument(
            id=0,
            title="On Amendments to the Labor Code of Uzbekistan",
            doc_type="law",
            doc_number="ZRU-2024-1235",
            date_published=(datetime.now() - timedelta(days=3)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=10)).strftime("%d.%m.%Y"),
            category="labor",
            description="Legal norms for remote work fixed. Employee monitoring issues regulated.",
            full_text="Full text of the law...",
            url="https://lex.uz/docs/1235",
            status="new",
            version=3,
            changes=[
                LawChange("Art. 50", "Office only", "Office/remote/hybrid", "modified", "New work formats"),
                LawChange("Art. 51", "-", "Electronic control", "added", "Monitoring with consent"),
            ]
        ),
        LawDocument(
            id=0,
            title="On Banking Regulation and Currency Control",
            doc_type="law",
            doc_number="ZRU-2024-5678",
            date_published=(datetime.now() - timedelta(days=5)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=20)).strftime("%d.%m.%Y"),
            category="banking",
            description="New banking regulations for digital payments and cryptocurrency transactions.",
            full_text="Full text of the law...",
            url="https://lex.uz/docs/5678",
            status="new",
            version=1,
            changes=[
                LawChange("Art. 200", "-", "Digital payments", "added", "Regulation of e-money"),
                LawChange("Art. 201", "-", "Crypto assets", "added", "Cryptocurrency framework"),
            ]
        ),
        LawDocument(
            id=0,
            title="On Inheritance Law and Will Procedures",
            doc_type="law",
            doc_number="ZRU-2024-9012",
            date_published=(datetime.now() - timedelta(days=7)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=45)).strftime("%d.%m.%Y"),
            category="inheritance",
            description="Updated inheritance procedures, electronic will validation, and succession rules.",
            full_text="Full text of the law...",
            url="https://lex.uz/docs/9012",
            status="new",
            version=2,
            changes=[
                LawChange("Art. 50", "Paper only", "Electronic valid", "modified", "Digital wills accepted"),
                LawChange("Art. 51", "-", "Notary online", "added", "Remote notarization"),
            ]
        ),
    ]
    return docs

# Document checking
async def check_new_documents():
    """Check for new documents"""
    logger.info("Checking for new documents...")
    try:
        new_docs = await fetch_demo_documents()
        new_count = 0
        
        for doc in new_docs:
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
                        clean_url(doc.url), doc.status, json.dumps([asdict(c) for c in doc.changes]),
                        doc.version
                    ))
                    await db.commit()
                new_count += 1
                await notify_subscribers(doc, is_update=False)
        
        logger.info(f"Check completed. New: {new_count}")
    except Exception as e:
        logger.error(f"Check error: {e}")

# Notification
async def notify_subscribers(doc: LawDocument, is_update: bool = False):
    """Notify subscribers about new document"""
    subscribers = await get_all_subscribers()
    type_info = DOC_TYPES.get(doc.doc_type, {'name': 'Document', 'icon': '📄'})
    cat_info = CATEGORIES.get(doc.category, {'name': doc.category, 'icon': '📁'})
    
    changes_text = ""
    if doc.changes:
        changes_text = "\n<b>📝 Key Changes:</b>\n"
        for i, change in enumerate(doc.changes[:3], 1):
            if change.change_type == "added":
                changes_text += f"\n{i}. ➕ <b>{change.article}</b>: {change.new_text}"
            elif change.change_type == "removed":
                changes_text += f"\n{i}. ➖ <b>{change.article}</b>: removed"
            else:
                changes_text += f"\n{i}. 🔄 <b>{change.article}</b>: {change.old_text} → {change.new_text}"
    
    action_emoji = "🔄" if is_update else "🆕"
    action_text = "UPDATED" if is_update else "NEW DOCUMENT"
    
    message = f"""
{action_emoji} <b>{action_text}</b>

{type_info['icon']} <b>{doc.title}</b>

<b>📋 Information:</b>
• Type: {type_info['name']}
• Number: <code>{doc.doc_number}</code>
• Published: {doc.date_published}
• Effective: {doc.date_effective or 'Immediately'}
• Category: {cat_info['icon']} {cat_info['name']}
• Version: <b>v{doc.version}</b>

<b>🎯 Description:</b>
{doc.description}
{changes_text}

<b>🔗 Source:</b> <a href="{clean_url(doc.url)}">Lex.uz</a>
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Full Text", url=clean_url(doc.url))],
        [InlineKeyboardButton(text=f"{cat_info['icon']} All {cat_info['name']}", callback_data=f"cat_{doc.category}")],
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

# Command handlers
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    await log_action(user.id, user.username or "", user.first_name or "", "start")
    await add_subscriber(user.id, user.username or "", user.first_name or "")
    
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    
    welcome = f"""
🏛️ <b>KPMG Law Uzbekistan — LexBot</b>

Hello, {user.first_name}!

🤖 I professionally monitor Uzbekistan legislation with <b>version history tracking</b>.

<b>📊 Database:</b>
• Total documents: <b>{total_docs}</b>
• Categories: <b>{len(CATEGORIES)}</b>

<b>⚡ Features:</b>
📜 New laws and amendments
📚 Document version history
🔔 Instant notifications
📁 Search by 17 categories
📊 Detailed statistics

<b>📋 Commands:</b>
/documents — All documents
/categories — By category
/history — Amendment history
/stats — Statistics
/search — Search
/help — Help
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Documents", callback_data="all_docs"),
         InlineKeyboardButton(text="📁 Categories", callback_data="categories_menu")],
        [InlineKeyboardButton(text="📚 History", callback_data="history_menu"),
         InlineKeyboardButton(text="📊 Stats", callback_data="stats")]
    ])
    
    await message.answer(welcome, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("documents"))
async def cmd_documents(message: Message):
    """Show all documents"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM documents ORDER BY created_at DESC LIMIT 5'
        ) as cursor:
            docs = await cursor.fetchall()
    
    if not docs:
        await message.answer("📭 No documents in database yet")
        return
    
    text = "<b>📜 LATEST DOCUMENTS</b>\n\n"
    for i, doc in enumerate(docs, 1):
        type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
        cat_info = CATEGORIES.get(doc['category'], {'name': doc['category']})
        clean_doc_url = clean_url(doc['url'])
        text += f"{i}. {type_info['icon']} <b>{doc['title']}</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | v{doc['version']}\n"
        text += f"   📅 {doc['date_published']} | {cat_info['name']}\n"
        text += f"   <a href='{clean_doc_url}'>Open →</a>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 By Categories", callback_data="categories_menu")],
    ])
    
    await message.answer(
        text, 
        reply_markup=keyboard, 
        parse_mode="HTML", 
        disable_web_page_preview=True
    )

@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    """Show categories menu"""
    cat_stats = await get_all_categories_stats()
    
    text = "<b>📁 LEGISLATION CATEGORIES</b>\n\n"
    text += "Select category to view documents:\n\n"
    
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

@dp.message(Command("history"))
async def cmd_history(message: Message):
    """Show amendment history"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM documents 
            WHERE version > 1 
            ORDER BY created_at DESC 
            LIMIT 10
        """) as cursor:
            docs = await cursor.fetchall()
    
    if not docs:
        await message.answer("📭 No documents with amendment history yet")
        return
    
    text = "<b>📚 AMENDMENT HISTORY</b>\n\n"
    text += "Documents with version changes:\n\n"
    
    for doc in docs:
        text += f"📜 <b>{doc['title']}</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | {doc['version']} versions\n"
        text += f"   <a href='{clean_url(doc['url'])}'>View →</a>\n\n"
    
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show statistics"""
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    
    text = f"""
<b>📊 LEGISLATION STATISTICS</b>

<b>📚 General:</b>
• Total documents: <b>{total_docs}</b>
• Categories: <b>{len(CATEGORIES)}</b>

<b>📁 By Category:</b>
"""
    
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁'})
            text += f"\n{info['icon']} {info['name']}: <b>{count}</b>"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Show help"""
    help_text = """
<b>❓ HELP — KPMG Law LexBot</b>

<b>📋 Commands:</b>
/start — Start bot, subscribe to notifications
/documents — All documents with versions
/categories — Browse by 17 categories
/history — Amendment history
/stats — Detailed statistics
/search — Search by category
/help — This help

<b>💡 Features:</b>
📚 Document version tracking
📝 Detailed change analysis
🔔 Instant new edition notifications
📊 Statistics by 17 categories

<b>🏛️ KPMG Law Uzbekistan</b>
Audit | Taxes | Law | Consulting
"""
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin panel"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ <b>Access denied</b>", parse_mode="HTML")
        return
    
    cat_stats = await get_all_categories_stats()
    subscribers = await get_all_subscribers()
    
    report = f"""
<b>📊 ADMIN PANEL KPMG LexBot</b>

<b>👥 Users:</b>
• Total subscribers: <b>{len(subscribers)}</b>

<b>📚 Documents:</b>
• Total documents: <b>{sum(cat_stats.values())}</b>

<b>📁 By Category:</b>
"""
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
        info = CATEGORIES.get(cat_key, {'name': cat_key})
        report += f"\n• {info['name']}: {count}"
    
    await message.answer(report, parse_mode="HTML")

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    """Reset database (admin only)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ <b>Access denied</b>", parse_mode="HTML")
        return
    
    try:
        if os.path.exists(DATABASE_PATH):
            os.remove(DATABASE_PATH)
        await init_database()
        await check_new_documents()
        await message.answer("✅ <b>Database reset successful!</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ <b>Error:</b> {e}", parse_mode="HTML")

# Callback handlers
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

@dp.callback_query(F.data.startswith("cat_"))
async def callback_category(callback: CallbackQuery):
    """Show documents in category"""
    category = callback.data.replace("cat_", "")
    
    if category not in CATEGORIES:
        await callback.answer("Category not found")
        return
    
    cat_info = CATEGORIES[category]
    docs = await get_documents_by_category(category, limit=10)
    
    if not docs:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        text += f"📭 No documents in this category yet\n\n"
        text += f"<i>{cat_info['desc']}</i>"
    else:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        text += f"<i>{cat_info['desc']}</i>\n\n"
        text += f"📚 Found documents: <b>{len(docs)}</b>\n\n"
        
        for i, doc in enumerate(docs, 1):
            type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
            clean_doc_url = clean_url(doc['url'])
            text += f"{i}. {type_info['icon']} <b>{doc['title']}</b>\n"
            text += f"   <code>{doc['doc_number']}</code> | v{doc['version']}\n"
            text += f"   📅 {doc['date_published']}\n"
            text += f"   <a href='{clean_doc_url}'>Open →</a>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 All Categories", callback_data="categories_menu")],
    ])
    
    await callback.message.edit_text(
        text, 
        reply_markup=keyboard, 
        parse_mode="HTML", 
        disable_web_page_preview=True
    )
    await callback.answer()

# Main function
async def main():
    """Main entry point"""
    logger.info("Starting LexBot...")
    
    # Initialize database
    await init_database()
    
    # Load initial data if empty
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM documents') as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                logger.info("Loading initial demo data...")
                await check_new_documents()
    
    # Start scheduler
    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='lexuz_check',
        name='Check Lex.uz',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started (interval: {CHECK_INTERVAL} min)")
    
    # Start polling
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")