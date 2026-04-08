#!/usr/bin/env python3
"""
LexBot â€” KPMG Law Uzbekistan
ÐœÐ¾Ð½Ð¸Ñ‚Ð¾Ñ€Ð¸Ð½Ð³ Ð·Ð°ÐºÐ¾Ð½Ð¾Ð´Ð°Ñ‚ÐµÐ»ÑŒÑÑ‚Ð²Ð° Ñ Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÐµÐ¹ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹
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
    'tax': {'name': 'ÐÐ°Ð»Ð¾Ð³Ð¸ Ð¸ ÑÐ±Ð¾Ñ€Ñ‹', 'icon': 'ðŸ’°', 'desc': 'ÐÐ°Ð»Ð¾Ð³Ð¾Ð²Ð¾Ðµ Ð·Ð°ÐºÐ¾Ð½Ð¾Ð´Ð°Ñ‚ÐµÐ»ÑŒÑÑ‚Ð²Ð¾, Ð»ÑŒÐ³Ð¾Ñ‚Ñ‹, Ð¾Ñ‚Ñ‡ÐµÑ‚Ð½Ð¾ÑÑ‚ÑŒ'},
    'economy': {'name': 'Ð­ÐºÐ¾Ð½Ð¾Ð¼Ð¸ÐºÐ° Ð¸ Ð±Ð¸Ð·Ð½ÐµÑ', 'icon': 'ðŸ“ˆ', 'desc': 'ÐŸÑ€ÐµÐ´Ð¿Ñ€Ð¸Ð½Ð¸Ð¼Ð°Ñ‚ÐµÐ»ÑŒÑÑ‚Ð²Ð¾, Ð¸Ð½Ð²ÐµÑÑ‚Ð¸Ñ†Ð¸Ð¸, Ð³Ð¾ÑÐ·Ð°ÐºÑƒÐ¿ÐºÐ¸'},
    'labor': {'name': 'Ð¢Ñ€ÑƒÐ´Ð¾Ð²Ð¾Ðµ Ð¿Ñ€Ð°Ð²Ð¾', 'icon': 'ðŸ‘·', 'desc': 'Ð¢Ñ€ÑƒÐ´Ð¾Ð²Ñ‹Ðµ Ð¾Ñ‚Ð½Ð¾ÑˆÐµÐ½Ð¸Ñ, Ð·Ð°Ñ€Ð¿Ð»Ð°Ñ‚Ð°, Ð¾Ñ‚Ð¿ÑƒÑÐºÐ°'},
    'digital': {'name': 'IT Ð¸ Ñ†Ð¸Ñ„Ñ€Ð¾Ð²Ð¸Ð·Ð°Ñ†Ð¸Ñ', 'icon': 'ðŸ’»', 'desc': 'AI, Ñ€Ð¾Ð±Ð¾Ñ‚Ñ‹, ÐºÐ¸Ð±ÐµÑ€Ð±ÐµÐ·Ð¾Ð¿Ð°ÑÐ½Ð¾ÑÑ‚ÑŒ, ÑÐ»ÐµÐºÑ‚Ñ€Ð¾Ð½Ð½Ð¾Ðµ Ð¿Ñ€Ð°Ð²Ð¸Ñ‚ÐµÐ»ÑŒÑÑ‚Ð²Ð¾'},
    'civil': {'name': 'Ð“Ñ€Ð°Ð¶Ð´Ð°Ð½ÑÐºÐ¾Ðµ Ð¿Ñ€Ð°Ð²Ð¾', 'icon': 'âš–ï¸', 'desc': 'Ð”Ð¾Ð³Ð¾Ð²Ð¾Ñ€Ñ‹, ÑÐ¾Ð±ÑÑ‚Ð²ÐµÐ½Ð½Ð¾ÑÑ‚ÑŒ, Ð½Ð°ÑÐ»ÐµÐ´ÑÑ‚Ð²Ð¾'},
    'criminal': {'name': 'Ð£Ð³Ð¾Ð»Ð¾Ð²Ð½Ð¾Ðµ Ð¿Ñ€Ð°Ð²Ð¾', 'icon': 'ðŸš”', 'desc': 'Ð£Ð³Ð¾Ð»Ð¾Ð²Ð½Ñ‹Ð¹ ÐºÐ¾Ð´ÐµÐºÑ, Ð¿Ñ€ÐµÑÑ‚ÑƒÐ¿Ð»ÐµÐ½Ð¸Ñ, Ð½Ð°ÐºÐ°Ð·Ð°Ð½Ð¸Ñ'},
    'administrative': {'name': 'ÐÐ´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¸Ð²Ð½Ð¾Ðµ Ð¿Ñ€Ð°Ð²Ð¾', 'icon': 'ðŸ“‹', 'desc': 'ÐÐ´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¸Ð²Ð½Ñ‹Ðµ Ð¿Ñ€Ð¾Ñ†ÐµÐ´ÑƒÑ€Ñ‹, ÑˆÑ‚Ñ€Ð°Ñ„Ñ‹'},
    'environment': {'name': 'Ð­ÐºÐ¾Ð»Ð¾Ð³Ð¸Ñ', 'icon': 'ðŸŒ¿', 'desc': 'ÐžÑ…Ñ€Ð°Ð½Ð° Ð¾ÐºÑ€ÑƒÐ¶Ð°ÑŽÑ‰ÐµÐ¹ ÑÑ€ÐµÐ´Ñ‹, Ð¿Ñ€Ð¸Ñ€Ð¾Ð´Ð½Ñ‹Ðµ Ñ€ÐµÑÑƒÑ€ÑÑ‹'},
    'health': {'name': 'Ð—Ð´Ñ€Ð°Ð²Ð¾Ð¾Ñ…Ñ€Ð°Ð½ÐµÐ½Ð¸Ðµ', 'icon': 'ðŸ¥', 'desc': 'ÐœÐµÐ´Ð¸Ñ†Ð¸Ð½Ð°, Ñ„Ð°Ñ€Ð¼Ð°Ñ†ÐµÐ²Ñ‚Ð¸ÐºÐ°, ÑÐ°Ð½Ð¸Ñ‚Ð°Ñ€Ð½Ñ‹Ðµ Ð½Ð¾Ñ€Ð¼Ñ‹'},
    'education': {'name': 'ÐžÐ±Ñ€Ð°Ð·Ð¾Ð²Ð°Ð½Ð¸Ðµ', 'icon': 'ðŸŽ“', 'desc': 'Ð¨ÐºÐ¾Ð»Ñ‹, ÑƒÐ½Ð¸Ð²ÐµÑ€ÑÐ¸Ñ‚ÐµÑ‚Ñ‹, ÑÐµÑ€Ñ‚Ð¸Ñ„Ð¸ÐºÐ°Ñ†Ð¸Ñ'},
    'finance': {'name': 'Ð¤Ð¸Ð½Ð°Ð½ÑÑ‹ Ð¸ Ð±Ð°Ð½ÐºÐ¸', 'icon': 'ðŸ¦', 'desc': 'Ð‘Ð°Ð½ÐºÐ¾Ð²ÑÐºÐ¾Ðµ Ñ€ÐµÐ³ÑƒÐ»Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ðµ, Ð²Ð°Ð»ÑŽÑ‚Ð½Ñ‹Ð¹ ÐºÐ¾Ð½Ñ‚Ñ€Ð¾Ð»ÑŒ'},
    'trade': {'name': 'Ð¢Ð¾Ñ€Ð³Ð¾Ð²Ð»Ñ Ð¸ Ñ‚Ð°Ð¼Ð¾Ð¶Ð½Ñ', 'icon': 'ðŸŒ', 'desc': 'Ð’Ð½ÐµÑˆÐ½ÐµÑ‚Ð¾Ñ€Ð³Ð¾Ð²Ñ‹Ðµ Ð¾Ð¿ÐµÑ€Ð°Ñ†Ð¸Ð¸, Ñ‚Ð°Ð¼Ð¾Ð¶ÐµÐ½Ð½Ð¾Ðµ Ð¾Ñ„Ð¾Ñ€Ð¼Ð»ÐµÐ½Ð¸Ðµ'},
    'construction': {'name': 'Ð¡Ñ‚Ñ€Ð¾Ð¸Ñ‚ÐµÐ»ÑŒÑÑ‚Ð²Ð¾', 'icon': 'ðŸ—ï¸', 'desc': 'Ð¡Ñ‚Ñ€Ð¾Ð¸Ñ‚ÐµÐ»ÑŒÐ½Ñ‹Ðµ Ð½Ð¾Ñ€Ð¼Ñ‹, Ð½ÐµÐ´Ð²Ð¸Ð¶Ð¸Ð¼Ð¾ÑÑ‚ÑŒ, Ð–ÐšÐ¥'},
    'transport': {'name': 'Ð¢Ñ€Ð°Ð½ÑÐ¿Ð¾Ñ€Ñ‚', 'icon': 'ðŸš›', 'desc': 'ÐÐ²Ñ‚Ð¾, Ð°Ð²Ð¸Ð°, Ð¶/Ð´, Ð»Ð¾Ð³Ð¸ÑÑ‚Ð¸ÐºÐ°'},
    'energy': {'name': 'Ð­Ð½ÐµÑ€Ð³ÐµÑ‚Ð¸ÐºÐ°', 'icon': 'âš¡', 'desc': 'Ð­Ð»ÐµÐºÑ‚Ñ€Ð¾ÑÐ½ÐµÑ€Ð³Ð¸Ñ, Ð³Ð°Ð·, Ð²Ð¾Ð·Ð¾Ð±Ð½Ð¾Ð²Ð»ÑÐµÐ¼Ñ‹Ðµ Ð¸ÑÑ‚Ð¾Ñ‡Ð½Ð¸ÐºÐ¸'},
}
DOC_TYPES = {
    'law': {'name': 'Ð—Ð°ÐºÐ¾Ð½', 'icon': 'ðŸ“œ'},
    'decree': {'name': 'Ð£ÐºÐ°Ð· ÐŸÑ€ÐµÐ·Ð¸Ð´ÐµÐ½Ñ‚Ð°', 'icon': 'âš¡'},
    'resolution': {'name': 'ÐŸÐ¾ÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ ÐšÐœ', 'icon': 'ðŸ“‹'},
    'order': {'name': 'ÐŸÑ€Ð¸ÐºÐ°Ð·', 'icon': 'ðŸ“„'},
    'regulation': {'name': 'ÐÐ¾Ñ€Ð¼Ð°Ñ‚Ð¸Ð²Ð½Ñ‹Ð¹ Ð°ÐºÑ‚', 'icon': 'ðŸ“‘'},
    'court': {'name': 'Ð¡ÑƒÐ´ÐµÐ±Ð½Ð°Ñ Ð¿Ñ€Ð°ÐºÑ‚Ð¸ÐºÐ°', 'icon': 'âš–ï¸'},
}
# ==================== DATA MODELS ====================
@dataclass
class LawChange:
    """Ð˜Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ðµ Ð² Ð·Ð°ÐºÐ¾Ð½Ðµ"""
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
        # ÐžÑÐ½Ð¾Ð²Ð½Ð°Ñ Ñ‚Ð°Ð±Ð»Ð¸Ñ†Ð° Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²
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
        # Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð²ÐµÑ€ÑÐ¸Ð¹ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²
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
        # ÐŸÐ¾Ð´Ð¿Ð¸ÑÑ‡Ð¸ÐºÐ¸
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
        # Ð›Ð¾Ð³Ð¸ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»ÐµÐ¹
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
        # Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð¿Ñ€Ð¾Ð²ÐµÑ€Ð¾Ðº
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
                f"ðŸ‘¤ {first_name} {last_name} (@{username}) â€” {action}"
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
    """ÐŸÐ¾Ð»ÑƒÑ‡Ð¸Ñ‚ÑŒ Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÑŽ Ð²ÐµÑ€ÑÐ¸Ð¹ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð°"""
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
    """ÐŸÐ¾Ð»ÑƒÑ‡Ð¸Ñ‚ÑŒ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹ Ð¿Ð¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¸"""
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
    """Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð¿Ð¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        stats = {}
        for cat_key in CATEGORIES.keys():
            async with db.execute('SELECT COUNT(*) FROM documents WHERE category = ?', (cat_key,)) as cursor:
                count = (await cursor.fetchone())[0]
                stats[cat_key] = count
        return stats
# ==================== PARSER ====================
async def fetch_lexuz_updates() -> List[LawDocument]:
    """ÐŸÐ¾Ð»ÑƒÑ‡ÐµÐ½Ð¸Ðµ Ð´ÐµÐ¼Ð¾-Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð² Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸ÑÐ¼Ð¸"""
    demo_docs = [
        LawDocument(
            id=0,
            title="Ðž Ð²Ð½ÐµÑÐµÐ½Ð¸Ð¸ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹ Ð² ÐÐ°Ð»Ð¾Ð³Ð¾Ð²Ñ‹Ð¹ ÐºÐ¾Ð´ÐµÐºÑ Ð ÐµÑÐ¿ÑƒÐ±Ð»Ð¸ÐºÐ¸ Ð£Ð·Ð±ÐµÐºÐ¸ÑÑ‚Ð°Ð½",
            doc_type="law",
            doc_number="Ð—Ð Ð£-1234",
            date_published=datetime.now().strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y"),
            category="tax",
            description="Ð’Ð½ÐµÑÐµÐ½Ñ‹ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ Ð² Ñ‡Ð°ÑÑ‚Ð¸ Ð½Ð°Ð»Ð¾Ð³Ð¾Ð¾Ð±Ð»Ð¾Ð¶ÐµÐ½Ð¸Ñ IT-ÐºÐ¾Ð¼Ð¿Ð°Ð½Ð¸Ð¹ Ð¸ ÑÑ‚Ð°Ñ€Ñ‚Ð°Ð¿Ð¾Ð². Ð£ÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ñ‹ Ð»ÑŒÐ³Ð¾Ñ‚Ð½Ñ‹Ðµ ÑÑ‚Ð°Ð²ÐºÐ¸ Ð½Ð°Ð»Ð¾Ð³Ð° Ð½Ð° Ð¿Ñ€Ð¸Ð±Ñ‹Ð»ÑŒ.",
            full_text="ÐŸÐ¾Ð»Ð½Ñ‹Ð¹ Ñ‚ÐµÐºÑÑ‚ Ð·Ð°ÐºÐ¾Ð½Ð°...",
            url=f"{LEX_UZ_URL}/docs/1234",
            status="new",
            version=2,
            changes=[
                LawChange("Ð¡Ñ‚. 123", "20%", "7%", "modified", "Ð¡Ð½Ð¸Ð¶ÐµÐ½Ð¸Ðµ ÑÑ‚Ð°Ð²ÐºÐ¸ Ð½Ð°Ð»Ð¾Ð³Ð° Ð½Ð° Ð¿Ñ€Ð¸Ð±Ñ‹Ð»ÑŒ Ð´Ð»Ñ IT"),
                LawChange("Ð¡Ñ‚. 124", "-", "Ð›ÑŒÐ³Ð¾Ñ‚Ð° Ð´Ð»Ñ ÑÑ‚Ð°Ñ€Ñ‚Ð°Ð¿Ð¾Ð²", "added", "ÐžÑÐ²Ð¾Ð±Ð¾Ð¶Ð´ÐµÐ½Ð¸Ðµ Ð¾Ñ‚ Ð½Ð°Ð»Ð¾Ð³Ð° Ð¿ÐµÑ€Ð²Ñ‹Ðµ 3 Ð³Ð¾Ð´Ð°"),
                LawChange("Ð¡Ñ‚. 125", "15%", "-", "removed", "ÐžÑ‚Ð¼ÐµÐ½ÐµÐ½Ð° Ð¿Ñ€ÐµÐ¶Ð½ÑÑ Ð»ÑŒÐ³Ð¾Ñ‚Ð°"),
            ],
            previous_versions=[
                {'version': 1, 'date': '01.01.2024', 'changes': 'ÐŸÐµÑ€Ð²Ð¾Ð½Ð°Ñ‡Ð°Ð»ÑŒÐ½Ð°Ñ Ñ€ÐµÐ´Ð°ÐºÑ†Ð¸Ñ'}
            ],
            created_at=""
        ),
        LawDocument(
            id=0,
            title="Ðž Ñ€Ð°Ð·Ð²Ð¸Ñ‚Ð¸Ð¸ Ð¸ÑÐºÑƒÑÑÑ‚Ð²ÐµÐ½Ð½Ð¾Ð³Ð¾ Ð¸Ð½Ñ‚ÐµÐ»Ð»ÐµÐºÑ‚Ð° Ð¸ Ñ†Ð¸Ñ„Ñ€Ð¾Ð²Ñ‹Ñ… Ñ‚ÐµÑ…Ð½Ð¾Ð»Ð¾Ð³Ð¸Ð¹",
            doc_type="decree",
            doc_number="Ð£ÐŸ-4567",
            date_published=(datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y"),
            date_effective=datetime.now().strftime("%d.%m.%Y"),
            category="digital",
            description="Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¾ ÐÐ°Ñ†Ð¸Ð¾Ð½Ð°Ð»ÑŒÐ½Ð¾Ðµ Ð°Ð³ÐµÐ½Ñ‚ÑÑ‚Ð²Ð¾ Ð¿Ð¾ Ñ€ÐµÐ³ÑƒÐ»Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸ÑŽ Ð¸ÑÐºÑƒÑÑÑ‚Ð²ÐµÐ½Ð½Ð¾Ð³Ð¾ Ð¸Ð½Ñ‚ÐµÐ»Ð»ÐµÐºÑ‚Ð°. Ð£Ñ‚Ð²ÐµÑ€Ð¶Ð´ÐµÐ½Ð° ÐšÐ¾Ð½Ñ†ÐµÐ¿Ñ†Ð¸Ñ Ñ€Ð°Ð·Ð²Ð¸Ñ‚Ð¸Ñ AI Ð´Ð¾ 2030.",
            full_text="ÐŸÐ¾Ð»Ð½Ñ‹Ð¹ Ñ‚ÐµÐºÑÑ‚ ÑƒÐºÐ°Ð·Ð°...",
            url=f"{LEX_UZ_URL}/docs/4567",
            status="new",
            version=1,
            changes=[
                LawChange("Ð’ÐµÑÑŒ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚", "-", "ÐÐ¾Ð²Ñ‹Ð¹ ÑƒÐºÐ°Ð·", "added", "Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð°Ð³ÐµÐ½Ñ‚ÑÑ‚Ð²Ð° Ð¿Ð¾ AI"),
            ],
            previous_versions=[],
            created_at=""
        ),
        LawDocument(
            id=0,
            title="ÐžÐ± ÑƒÑ‚Ð²ÐµÑ€Ð¶Ð´ÐµÐ½Ð¸Ð¸ ÐŸÑ€Ð°Ð²Ð¸Ð» Ñ€ÐµÐ³Ð¸ÑÑ‚Ñ€Ð°Ñ†Ð¸Ð¸ Ñ€Ð¾Ð±Ð¾Ñ‚Ð¾Ñ‚ÐµÑ…Ð½Ð¸Ñ‡ÐµÑÐºÐ¸Ñ… ÑÐ¸ÑÑ‚ÐµÐ¼",
            doc_type="resolution",
            doc_number="ÐŸÐšÐœ-789",
            date_published=(datetime.now() - timedelta(days=2)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=15)).strftime("%d.%m.%Y"),
            category="digital",
            description="Ð£ÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½ Ð¿Ð¾Ñ€ÑÐ´Ð¾Ðº Ð³Ð¾ÑÑƒÐ´Ð°Ñ€ÑÑ‚Ð²ÐµÐ½Ð½Ð¾Ð¹ Ñ€ÐµÐ³Ð¸ÑÑ‚Ñ€Ð°Ñ†Ð¸Ð¸ Ð¿Ñ€Ð¾Ð¼Ñ‹ÑˆÐ»ÐµÐ½Ð½Ñ‹Ñ… Ð¸ ÑÐµÑ€Ð²Ð¸ÑÐ½Ñ‹Ñ… Ñ€Ð¾Ð±Ð¾Ñ‚Ð¾Ð². Ð’Ð²ÐµÐ´ÐµÐ½Ñ‹ Ñ‚Ñ€ÐµÐ±Ð¾Ð²Ð°Ð½Ð¸Ñ Ð±ÐµÐ·Ð¾Ð¿Ð°ÑÐ½Ð¾ÑÑ‚Ð¸.",
            full_text="ÐŸÐ¾Ð»Ð½Ñ‹Ð¹ Ñ‚ÐµÐºÑÑ‚ Ð¿Ð¾ÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ñ...",
            url=f"{LEX_UZ_URL}/docs/789",
            status="new",
            version=1,
            changes=[
                LawChange("Ð Ð°Ð·Ð´ÐµÐ» 1", "-", "ÐŸÑ€Ð°Ð²Ð¸Ð»Ð° Ñ€ÐµÐ³Ð¸ÑÑ‚Ñ€Ð°Ñ†Ð¸Ð¸", "added", "ÐžÐ±ÑÐ·Ð°Ñ‚ÐµÐ»ÑŒÐ½Ð°Ñ Ñ€ÐµÐ³Ð¸ÑÑ‚Ñ€Ð°Ñ†Ð¸Ñ Ð²ÑÐµÑ… Ñ€Ð¾Ð±Ð¾Ñ‚Ð¾Ð²"),
                LawChange("Ð Ð°Ð·Ð´ÐµÐ» 2", "-", "Ð¢Ñ€ÐµÐ±Ð¾Ð²Ð°Ð½Ð¸Ñ Ð±ÐµÐ·Ð¾Ð¿Ð°ÑÐ½Ð¾ÑÑ‚Ð¸", "added", "Ð¡ÐµÑ€Ñ‚Ð¸Ñ„Ð¸ÐºÐ°Ñ†Ð¸Ñ ISO 10218"),
            ],
            previous_versions=[],
            created_at=""
        ),
        LawDocument(
            id=0,
            title="Ðž Ð²Ð½ÐµÑÐµÐ½Ð¸Ð¸ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹ Ð² Ð¢Ñ€ÑƒÐ´Ð¾Ð²Ð¾Ð¹ ÐºÐ¾Ð´ÐµÐºÑ Ð Ð£Ð·",
            doc_type="law",
            doc_number="Ð—Ð Ð£-1235",
            date_published=(datetime.now() - timedelta(days=3)).strftime("%d.%m.%Y"),
            date_effective=(datetime.now() + timedelta(days=10)).strftime("%d.%m.%Y"),
            category="labor",
            description="Ð—Ð°ÐºÑ€ÐµÐ¿Ð»ÐµÐ½Ñ‹ Ð¿Ñ€Ð°Ð²Ð¾Ð²Ñ‹Ðµ Ð½Ð¾Ñ€Ð¼Ñ‹ Ð´Ð»Ñ ÑƒÐ´Ð°Ð»ÐµÐ½Ð½Ð¾Ð¹ Ñ€Ð°Ð±Ð¾Ñ‚Ñ‹. Ð£Ñ€ÐµÐ³ÑƒÐ»Ð¸Ñ€Ð¾Ð²Ð°Ð½Ñ‹ Ð²Ð¾Ð¿Ñ€Ð¾ÑÑ‹ Ð¼Ð¾Ð½Ð¸Ñ‚Ð¾Ñ€Ð¸Ð½Ð³Ð° Ð´ÐµÑÑ‚ÐµÐ»ÑŒÐ½Ð¾ÑÑ‚Ð¸ ÑƒÐ´Ð°Ð»ÐµÐ½Ð½Ñ‹Ñ… ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ¾Ð².",
            full_text="ÐŸÐ¾Ð»Ð½Ñ‹Ð¹ Ñ‚ÐµÐºÑÑ‚ Ð·Ð°ÐºÐ¾Ð½Ð°...",
            url=f"{LEX_UZ_URL}/docs/1235",
            status="new",
            version=3,
            changes=[
                LawChange("Ð¡Ñ‚. 50", "Ð¢Ð¾Ð»ÑŒÐºÐ¾ Ð¾Ñ„Ð¸Ñ", "ÐžÑ„Ð¸Ñ/ÑƒÐ´Ð°Ð»ÐµÐ½Ð½Ð¾/Ð³Ð¸Ð±Ñ€Ð¸Ð´", "modified", "ÐÐ¾Ð²Ñ‹Ðµ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ñ‹ Ñ€Ð°Ð±Ð¾Ñ‚Ñ‹"),
                LawChange("Ð¡Ñ‚. 51", "-", "Ð­Ð»ÐµÐºÑ‚Ñ€Ð¾Ð½Ð½Ñ‹Ð¹ ÐºÐ¾Ð½Ñ‚Ñ€Ð¾Ð»ÑŒ", "added", "Ð Ð°Ð·Ñ€ÐµÑˆÐµÐ½ Ð¼Ð¾Ð½Ð¸Ñ‚Ð¾Ñ€Ð¸Ð½Ð³ Ñ ÑÐ¾Ð³Ð»Ð°ÑÐ¸Ñ"),
            ],
            previous_versions=[
                {'version': 1, 'date': '01.01.2023', 'changes': 'ÐŸÐµÑ€Ð²Ð¾Ð½Ð°Ñ‡Ð°Ð»ÑŒÐ½Ð°Ñ Ñ€ÐµÐ´Ð°ÐºÑ†Ð¸Ñ'},
                {'version': 2, 'date': '15.06.2024', 'changes': 'Ð˜Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ Ð¿Ð¾ Ð¾Ñ‚Ð¿ÑƒÑÐºÐ°Ð¼'}
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
                # ÐÐ¾Ð²Ñ‹Ð¹ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚
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
                # ÐžÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÑƒÑ‰ÐµÑÑ‚Ð²ÑƒÑŽÑ‰ÐµÐ³Ð¾ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð°
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    # Ð¡Ð¾Ñ…Ñ€Ð°Ð½ÑÐµÐ¼ ÑÑ‚Ð°Ñ€ÑƒÑŽ Ð²ÐµÑ€ÑÐ¸ÑŽ
                    await db.execute("""
                        INSERT INTO document_versions 
                        (doc_number, version, title, full_text, changes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        existing['doc_number'], existing['version'],
                        existing['title'], existing.get('full_text', ''),
                        existing.get('changes', '[]')
                    ))
                    # ÐžÐ±Ð½Ð¾Ð²Ð»ÑÐµÐ¼ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚
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
        # Ð›Ð¾Ð³Ð¸Ñ€ÑƒÐµÐ¼ Ð¿Ñ€Ð¾Ð²ÐµÑ€ÐºÑƒ
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
                f"âœ… ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð·Ð°Ð²ÐµÑ€ÑˆÐµÐ½Ð°!\nÐÐ¾Ð²Ñ‹Ñ…: {new_count}\nÐžÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾: {updated_count}"
            )
    except Exception as e:
        logger.error(f"Check error: {e}")
        import traceback
        logger.error(traceback.format_exc())
async def notify_subscribers(doc: LawDocument, is_update: bool = False):
    """Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ðµ Ð¿Ð¾Ð´Ð¿Ð¸ÑÑ‡Ð¸ÐºÐ¾Ð² Ñ Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÐµÐ¹ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹"""
    subscribers = await get_all_subscribers()
    type_info = DOC_TYPES.get(doc.doc_type, {'name': 'Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚', 'icon': 'ðŸ“„'})
    cat_info = CATEGORIES.get(doc.category, {'name': doc.category, 'icon': 'ðŸ“'})
    # Ð¤Ð¾Ñ€Ð¼Ð°Ñ‚Ð¸Ñ€ÑƒÐµÐ¼ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ
    changes_text = ""
    if doc.changes:
        changes_text = "\n<b>ðŸ“ ÐšÐ»ÑŽÑ‡ÐµÐ²Ñ‹Ðµ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ:</b>\n"
        for i, change in enumerate(doc.changes[:5], 1):  # ÐŸÐ¾ÐºÐ°Ð·Ñ‹Ð²Ð°ÐµÐ¼ Ð¿ÐµÑ€Ð²Ñ‹Ðµ 5
            if change.change_type == "added":
                changes_text += f"\n{i}. âž• <b>{change.article}</b>: {change.new_text}"
            elif change.change_type == "removed":
                changes_text += f"\n{i}. âž– <b>{change.article}</b>: ÑƒÐ´Ð°Ð»ÐµÐ½Ð¾"
            else:
                changes_text += f"\n{i}. ðŸ”„ <b>{change.article}</b>: {change.old_text} â†’ {change.new_text}"
            if change.explanation:
                changes_text += f"\n   <i>{change.explanation}</i>"
    # Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð²ÐµÑ€ÑÐ¸Ð¹
    versions_text = ""
    if doc.previous_versions:
        versions_text = f"\n\n<b>ðŸ“š Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ:</b> {len(doc.previous_versions)} Ð¿Ñ€ÐµÐ´Ñ‹Ð´ÑƒÑ‰Ð¸Ñ… Ð²ÐµÑ€ÑÐ¸Ð¹"
    action_emoji = "ðŸ”„" if is_update else "ðŸ†•"
    action_text = "ÐžÐ‘ÐÐžÐ’Ð›Ð•ÐÐ˜Ð•" if is_update else "ÐÐžÐ’Ð«Ð™ Ð”ÐžÐšÐ£ÐœÐ•ÐÐ¢"
    message = f"""
{action_emoji} <b>{action_text}</b>
{type_info['icon']} <b>{doc.title}</b>
<b>ðŸ“‹ Ð˜Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ†Ð¸Ñ:</b>
â€¢ Ð¢Ð¸Ð¿: {type_info['name']}
â€¢ ÐÐ¾Ð¼ÐµÑ€: <code>{doc.doc_number}</code>
â€¢ Ð”Ð°Ñ‚Ð° Ð¿ÑƒÐ±Ð»Ð¸ÐºÐ°Ñ†Ð¸Ð¸: {doc.date_published}
â€¢ Ð’ÑÑ‚ÑƒÐ¿Ð°ÐµÑ‚ Ð² ÑÐ¸Ð»Ñƒ: {doc.date_effective or 'ÐÐµÐ¼ÐµÐ´Ð»ÐµÐ½Ð½Ð¾'}
â€¢ ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ñ: {cat_info['icon']} {cat_info['name']}
â€¢ Ð’ÐµÑ€ÑÐ¸Ñ: <b>v{doc.version}</b>
<b>ðŸŽ¯ ÐžÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ:</b>
{doc.description}
{changes_text}
{versions_text}
<b>ðŸ”— Ð˜ÑÑ‚Ð¾Ñ‡Ð½Ð¸Ðº:</b> <a href="{clean_url(doc.url)}">Lex.uz</a>
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ“– ÐŸÐ¾Ð»Ð½Ñ‹Ð¹ Ñ‚ÐµÐºÑÑ‚", url=clean_url(doc.url))],
        [InlineKeyboardButton(text="ðŸ“š Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹", callback_data=f"history_{doc.doc_number}")],
        [InlineKeyboardButton(text=f"{cat_info['icon']} Ð’ÑÐµ {cat_info['name']}", callback_data=f"cat_{doc.category}")],
        [InlineKeyboardButton(text="âŒ ÐžÑ‚ÐºÐ»ÑŽÑ‡Ð¸Ñ‚ÑŒ ÑƒÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ", callback_data="unsubscribe")]
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
    # Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð¿Ð¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())
    welcome = f"""
<b>ðŸ›ï¸ KPMG Law Uzbekistan â€” LexBot</b>
ÐŸÑ€Ð¸Ð²ÐµÑ‚, {user.first_name}!
ðŸ¤– Ð¯ Ð¿Ñ€Ð¾Ñ„ÐµÑÑÐ¸Ð¾Ð½Ð°Ð»ÑŒÐ½Ð¾ Ð¼Ð¾Ð½Ð¸Ñ‚Ð¾Ñ€ÑŽ Ð·Ð°ÐºÐ¾Ð½Ð¾Ð´Ð°Ñ‚ÐµÐ»ÑŒÑÑ‚Ð²Ð¾ Ð£Ð·Ð±ÐµÐºÐ¸ÑÑ‚Ð°Ð½Ð° Ñ <b>Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÐµÐ¹ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹</b>.
<b>ðŸ“Š Ð’ Ð±Ð°Ð·Ðµ:</b>
â€¢ Ð’ÑÐµÐ³Ð¾ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²: <b>{total_docs}</b>
â€¢ ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¹: <b>{len(CATEGORIES)}</b>
<b>âš¡ Ð’Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾ÑÑ‚Ð¸:</b>
â€¢ ðŸ“œ ÐÐ¾Ð²Ñ‹Ðµ Ð·Ð°ÐºÐ¾Ð½Ñ‹ Ð¸ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ
â€¢ ðŸ“š Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð²ÐµÑ€ÑÐ¸Ð¹ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²
â€¢ ðŸ”” ÐœÐ³Ð½Ð¾Ð²ÐµÐ½Ð½Ñ‹Ðµ ÑƒÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ
â€¢ ðŸ“ ÐŸÐ¾Ð¸ÑÐº Ð¿Ð¾ 15 ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼
â€¢ ðŸ“Š Ð”ÐµÑ‚Ð°Ð»ÑŒÐ½Ð°Ñ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°
<b>ðŸ“‹ ÐšÐ¾Ð¼Ð°Ð½Ð´Ñ‹:</b>
/documents â€” Ð’ÑÐµ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹
/categories â€” ÐŸÐ¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼
/history â€” Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹
/stats â€” Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°
/search â€” ÐŸÐ¾Ð¸ÑÐº
/help â€” ÐŸÐ¾Ð¼Ð¾Ñ‰ÑŒ
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ“œ Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹", callback_data="all_docs"),
         InlineKeyboardButton(text="ðŸ“ ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¸", callback_data="categories_menu")],
        [InlineKeyboardButton(text="ðŸ“š Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ", callback_data="history_menu"),
         InlineKeyboardButton(text="ðŸ“Š Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°", callback_data="stats")]
    ])
    await message.answer(welcome, reply_markup=keyboard, parse_mode="HTML")
@dp.message(Command("documents"))
async def cmd_documents(message: Message):
    """Ð’ÑÐµ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹ Ñ Ð¿Ð°Ð³Ð¸Ð½Ð°Ñ†Ð¸ÐµÐ¹"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM documents ORDER BY created_at DESC LIMIT 5'
        ) as cursor:
            docs = await cursor.fetchall()
    if not docs:
        await message.answer("ðŸ“­ ÐŸÐ¾ÐºÐ° Ð½ÐµÑ‚ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð² Ð² Ð±Ð°Ð·Ðµ")
        return
    text = "<b>ðŸ“œ ÐŸÐžÐ¡Ð›Ð•Ð”ÐÐ˜Ð• Ð”ÐžÐšÐ£ÐœÐ•ÐÐ¢Ð«</b>\n\n"
    for i, doc in enumerate(docs, 1):
        type_info = DOC_TYPES.get(doc['doc_type'], {'icon': 'ðŸ“„'})
        cat_info = CATEGORIES.get(doc['category'], {'name': doc['category']})
        text += f"{i}. {type_info['icon']} <b>{doc['title']}</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | v{doc['version']}\n"
        text += f"   ðŸ“… {doc['date_published']} | {cat_info['name']}\n"
        text += f"   <a href='{doc['url']}'>ÐžÑ‚ÐºÑ€Ñ‹Ñ‚ÑŒ â†’</a>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ“ ÐŸÐ¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼", callback_data="categories_menu")],
        [InlineKeyboardButton(text="ðŸ“š Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹", callback_data="history_menu")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    """ÐœÐµÐ½ÑŽ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¹"""
    cat_stats = await get_all_categories_stats()
    text = "<b>ðŸ“ ÐšÐÐ¢Ð•Ð“ÐžÐ Ð˜Ð˜ Ð—ÐÐšÐžÐÐžÐ”ÐÐ¢Ð•Ð›Ð¬Ð¡Ð¢Ð’Ð</b>\n\n"
    text += "Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑŽ Ð´Ð»Ñ Ð¿Ñ€Ð¾ÑÐ¼Ð¾Ñ‚Ñ€Ð° Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²:\n\n"
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
        InlineKeyboardButton(text="ðŸ“Š Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð¿Ð¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼", callback_data="cats_stats")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
@dp.message(Command("history"))
async def cmd_history(message: Message):
    """Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹"""
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
        await message.answer("ðŸ“­ ÐŸÐ¾ÐºÐ° Ð½ÐµÑ‚ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð² Ñ Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÐµÐ¹ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹")
        return
    text = "<b>ðŸ“š Ð˜Ð¡Ð¢ÐžÐ Ð˜Ð¯ Ð˜Ð—ÐœÐ•ÐÐ•ÐÐ˜Ð™</b>\n\n"
    text += "Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹ Ñ Ð²ÐµÑ€ÑÐ¸ÑÐ¼Ð¸ Ð¸ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸ÑÐ¼Ð¸:\n\n"
    for doc in docs:
        versions = doc.get('version_count', 0) + 1
        text += f"ðŸ“œ <b>{doc['title']}</b>\n"
        text += f"   <code>{doc['doc_number']}</code> | {versions} Ð²ÐµÑ€ÑÐ¸Ð¹\n"
        text += f"   Ð¢ÐµÐºÑƒÑ‰Ð°Ñ: v{doc['version']}\n"
        text += f"   <a href='{doc['url']}'>Ð¡Ð¼Ð¾Ñ‚Ñ€ÐµÑ‚ÑŒ â†’</a>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ” ÐÐ°Ð¹Ñ‚Ð¸ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚", callback_data="search_doc")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    user = message.from_user
    await add_subscriber(user.id, user.username or "", user.first_name or "", user.last_name or "")
    await message.answer(
        "âœ… <b>ÐŸÐ¾Ð´Ð¿Ð¸ÑÐºÐ° Ð¾Ñ„Ð¾Ñ€Ð¼Ð»ÐµÐ½Ð°!</b>\n\n"
        "Ð’Ñ‹ Ð±ÑƒÐ´ÐµÑ‚Ðµ Ð¿Ð¾Ð»ÑƒÑ‡Ð°Ñ‚ÑŒ ÑƒÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¾:\n"
        "â€¢ ÐÐ¾Ð²Ñ‹Ñ… Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð°Ñ…\n"
        "â€¢ ÐžÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸ÑÑ… ÑÑƒÑ‰ÐµÑÑ‚Ð²ÑƒÑŽÑ‰Ð¸Ñ…\n"
        "â€¢ Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹",
        parse_mode="HTML"
    )
@dp.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message):
    await remove_subscriber(message.from_user.id)
    await message.answer("âŒ <b>Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¾Ñ‚ÐºÐ»ÑŽÑ‡ÐµÐ½Ñ‹</b>", parse_mode="HTML")
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
<b>ðŸ“Š Ð¡Ð¢ÐÐ¢Ð˜Ð¡Ð¢Ð˜ÐšÐ Ð—ÐÐšÐžÐÐžÐ”ÐÐ¢Ð•Ð›Ð¬Ð¡Ð¢Ð’Ð</b>
<b>ðŸ“š ÐžÐ±Ñ‰Ð¸Ðµ Ð¿Ð¾ÐºÐ°Ð·Ð°Ñ‚ÐµÐ»Ð¸:</b>
â€¢ Ð’ÑÐµÐ³Ð¾ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²: <b>{total_docs}</b>
â€¢ Ð’ÐµÑ€ÑÐ¸Ð¹ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²: <b>{total_versions}</b>
â€¢ ÐÐ¾Ð²Ñ‹Ñ… Ð·Ð° Ð½ÐµÐ´ÐµÐ»ÑŽ: <b>{new_week}</b>
<b>ðŸ“ ÐŸÐ¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼:</b>
"""
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': 'ðŸ“'})
            percentage = (count / total_docs * 100) if total_docs > 0 else 0
            bar = "â–ˆ" * int(percentage / 10) + "â–‘" * (10 - int(percentage / 10))
            text += f"\n{info['icon']} {info['name']}: {count} <code>[{bar}]</code> {percentage:.1f}%"
    text += f"\n\n<b>ðŸ”„ ÐžÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ:</b> ÐºÐ°Ð¶Ð´Ñ‹Ðµ {CHECK_INTERVAL} Ð¼Ð¸Ð½"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ“ ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¸", callback_data="categories_menu"),
         InlineKeyboardButton(text="ðŸ“œ Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹", callback_data="all_docs")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
@dp.message(Command("search"))
async def cmd_search(message: Message):
    keyboard_buttons = []
    row = []
    for key, info in list(CATEGORIES.items())[:8]:  # ÐŸÐµÑ€Ð²Ñ‹Ðµ 8 ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¹
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
        InlineKeyboardButton(text="ðŸ“Š Ð’ÑÐµ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¸", callback_data="categories_menu")
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(
        "<b>ðŸ” ÐŸÐžÐ˜Ð¡Ðš ÐŸÐž ÐšÐÐ¢Ð•Ð“ÐžÐ Ð˜Ð¯Ðœ</b>\n\n"
        "Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑŽ Ð¸Ð»Ð¸ Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ ÐºÐ»ÑŽÑ‡ÐµÐ²Ñ‹Ðµ ÑÐ»Ð¾Ð²Ð°:\n"
        "<i>Ð½Ð°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: Ð½Ð°Ð»Ð¾Ð³Ð¾Ð²Ñ‹Ð¹ ÐºÐ¾Ð´ÐµÐºÑ, ÑƒÐ´Ð°Ð»ÐµÐ½Ð½Ð°Ñ Ñ€Ð°Ð±Ð¾Ñ‚Ð°, AI</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = f"""
<b>â“ ÐŸÐžÐœÐžÐ©Ð¬ â€” KPMG Law LexBot</b>
<b>ðŸ“‹ ÐžÑÐ½Ð¾Ð²Ð½Ñ‹Ðµ ÐºÐ¾Ð¼Ð°Ð½Ð´Ñ‹:</b>
/documents â€” Ð’ÑÐµ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹ Ñ Ð²ÐµÑ€ÑÐ¸ÑÐ¼Ð¸
/categories â€” ÐŸÑ€Ð¾ÑÐ¼Ð¾Ñ‚Ñ€ Ð¿Ð¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼ (15 Ñ€Ð°Ð·Ð´ÐµÐ»Ð¾Ð²)
/history â€” Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²
/stats â€” Ð”ÐµÑ‚Ð°Ð»ÑŒÐ½Ð°Ñ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°
/search â€” ÐŸÐ¾Ð¸ÑÐº Ð¿Ð¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼
<b>âš™ï¸ Ð£Ð¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ:</b>
/subscribe â€” ÐŸÐ¾Ð´Ð¿Ð¸ÑÐ°Ñ‚ÑŒÑÑ Ð½Ð° ÑƒÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ
/unsubscribe â€” ÐžÑ‚ÐºÐ»ÑŽÑ‡Ð¸Ñ‚ÑŒ ÑƒÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ
<b>ðŸ’¡ Ð’Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾ÑÑ‚Ð¸:</b>
â€¢ ðŸ“š ÐžÑ‚ÑÐ»ÐµÐ¶Ð¸Ð²Ð°Ð½Ð¸Ðµ Ð²ÐµÑ€ÑÐ¸Ð¹ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²
â€¢ ðŸ“ Ð”ÐµÑ‚Ð°Ð»ÑŒÐ½Ñ‹Ð¹ Ð°Ð½Ð°Ð»Ð¸Ð· Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ð¹
â€¢ ðŸ”” Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¾ Ð½Ð¾Ð²Ñ‹Ñ… Ñ€ÐµÐ´Ð°ÐºÑ†Ð¸ÑÑ…
â€¢ ðŸ“Š Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð¿Ð¾ 15 ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼
<b>ðŸ›ï¸ KPMG Law Uzbekistan</b>
ÐÑƒÐ´Ð¸Ñ‚ | ÐÐ°Ð»Ð¾Ð³Ð¸ | ÐŸÑ€Ð°Ð²Ð¾ | ÐšÐ¾Ð½ÑÐ°Ð»Ñ‚Ð¸Ð½Ð³
"""
    await message.answer(help_text, parse_mode="HTML")
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("â›” <b>Ð”Ð¾ÑÑ‚ÑƒÐ¿ Ð·Ð°Ð¿Ñ€ÐµÑ‰ÐµÐ½</b>", parse_mode="HTML")
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
<b>ðŸ“Š ÐÐ”ÐœÐ˜Ð-ÐŸÐÐÐ•Ð›Ð¬ KPMG LexBot</b>
<b>ðŸ‘¥ ÐŸÐ¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ð¸:</b>
â€¢ Ð’ÑÐµÐ³Ð¾ ÑƒÐ½Ð¸ÐºÐ°Ð»ÑŒÐ½Ñ‹Ñ…: <b>{total_users}</b>
â€¢ ÐÐºÑ‚Ð¸Ð²Ð½Ñ‹Ñ… Ð¿Ð¾Ð´Ð¿Ð¸ÑÑ‡Ð¸ÐºÐ¾Ð²: <b>{active_subs}</b>
<b>ðŸ“š Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ñ‹:</b>
â€¢ Ð’ÑÐµÐ³Ð¾ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²: <b>{total_docs}</b>
â€¢ Ð’ÐµÑ€ÑÐ¸Ð¹ (Ð¸ÑÑ‚Ð¾Ñ€Ð¸Ñ): <b>{total_versions}</b>
<b>ðŸ“ ÐŸÐ¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼:</b>
"""
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
        info = CATEGORIES.get(cat_key, {'name': cat_key})
        report += f"\nâ€¢ {info['name']}: {count}"
    report += "\n\n<b>ðŸ”¥ ÐŸÐ¾ÑÐ»ÐµÐ´Ð½Ð¸Ðµ Ð´ÐµÐ¹ÑÑ‚Ð²Ð¸Ñ:</b>"
    for name, username, action, time in recent:
        report += f"\nâ€¢ {name} (@{username}) â€” {action}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ“Š Ð”ÐµÑ‚Ð°Ð»ÑŒÐ½Ð°Ñ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°", callback_data="admin_stats")],
        [InlineKeyboardButton(text="ðŸ“¢ Ð Ð°ÑÑÑ‹Ð»ÐºÐ°", callback_data="admin_broadcast")]
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
    await callback.message.edit_text("âœ… <b>ÐŸÐ¾Ð´Ð¿Ð¸ÑÐºÐ° Ð¾Ñ„Ð¾Ñ€Ð¼Ð»ÐµÐ½Ð°!</b>", parse_mode="HTML")
    await callback.answer("ÐŸÐ¾Ð´Ð¿Ð¸ÑÐºÐ° Ð°ÐºÑ‚Ð¸Ð²Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð°")
@dp.callback_query(F.data == "unsubscribe")
async def callback_unsubscribe(callback: CallbackQuery):
    await remove_subscriber(callback.from_user.id)
    await callback.message.edit_text("âŒ <b>Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¾Ñ‚ÐºÐ»ÑŽÑ‡ÐµÐ½Ñ‹</b>", parse_mode="HTML")
    await callback.answer("Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¾Ñ‚ÐºÐ»ÑŽÑ‡ÐµÐ½Ñ‹")
@dp.callback_query(F.data.startswith("cat_"))
async def callback_category(callback: CallbackQuery):
    category = callback.data.replace("cat_", "")
    if category not in CATEGORIES:
        await callback.answer("ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ñ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°")
        return
    cat_info = CATEGORIES[category]
    docs = await get_documents_by_category(category, limit=10)
    if not docs:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        text += f"ðŸ“­ Ð’ ÑÑ‚Ð¾Ð¹ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¸ Ð¿Ð¾ÐºÐ° Ð½ÐµÑ‚ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²\n\n"
        text += f"<i>{cat_info['desc']}</i>"
    else:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n"
        text += f"<i>{cat_info['desc']}</i>\n\n"
        text += f"ðŸ“š ÐÐ°Ð¹Ð´ÐµÐ½Ð¾ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²: <b>{len(docs)}</b>\n\n"
        for i, doc in enumerate(docs, 1):
            type_info = DOC_TYPES.get(doc['doc_type'], {'icon': 'ðŸ“„'})
            text += f"{i}. {type_info['icon']} <b>{doc['title']}</b>\n"
            text += f"   <code>{doc['doc_number']}</code> | v{doc['version']}\n"
            text += f"   ðŸ“… {doc['date_published']}\n"
            text += f"   <a href='{doc['url']}'>ÐžÑ‚ÐºÑ€Ñ‹Ñ‚ÑŒ â†’</a>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ”™ Ð’ÑÐµ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¸", callback_data="categories_menu")],
        [InlineKeyboardButton(text="ðŸ“Š Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°", callback_data="stats")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()
@dp.callback_query(F.data.startswith("history_"))
async def callback_document_history(callback: CallbackQuery):
    """ÐŸÐ¾ÐºÐ°Ð·Ð°Ñ‚ÑŒ Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÑŽ Ð²ÐµÑ€ÑÐ¸Ð¹ ÐºÐ¾Ð½ÐºÑ€ÐµÑ‚Ð½Ð¾Ð³Ð¾ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð°"""
    doc_number = callback.data.replace("history_", "")
    doc = await get_document_by_number(doc_number)
    if not doc:
        await callback.answer("Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½")
        return
    versions = await get_document_versions(doc_number)
    type_info = DOC_TYPES.get(doc['doc_type'], {'icon': 'ðŸ“„'})
    text = f"{type_info['icon']} <b>{doc['title']}</b>\n\n"
    text += f"<b>ðŸ“š Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð²ÐµÑ€ÑÐ¸Ð¹:</b>\n\n"
    text += f"Ð¢ÐµÐºÑƒÑ‰Ð°Ñ Ð²ÐµÑ€ÑÐ¸Ñ: <b>v{doc['version']}</b>\n"
    if versions:
        text += f"ÐŸÑ€ÐµÐ´Ñ‹Ð´ÑƒÑ‰Ð¸Ñ… Ð²ÐµÑ€ÑÐ¸Ð¹: <b>{len(versions)}</b>\n\n"
        for v in versions:
            text += f"ðŸ“„ v{v['version']} â€” {v['changed_at'][:10]}\n"
    else:
        text += "\n<i>Ð­Ñ‚Ð¾ Ð¿ÐµÑ€Ð²Ð°Ñ Ð²ÐµÑ€ÑÐ¸Ñ Ð´Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð°</i>"
    # ÐŸÐ¾ÐºÐ°Ð·Ñ‹Ð²Ð°ÐµÐ¼ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ Ñ‚ÐµÐºÑƒÑ‰ÐµÐ¹ Ð²ÐµÑ€ÑÐ¸Ð¸
    changes = json.loads(doc.get('changes', '[]'))
    if changes:
        text += "\n\n<b>ðŸ“ Ð¢ÐµÐºÑƒÑ‰Ð¸Ðµ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ:</b>"
        for change in changes:
            text += f"\nâ€¢ {change.get('article', '')}: {change.get('change_type', '')}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ“– ÐŸÐ¾Ð»Ð½Ñ‹Ð¹ Ñ‚ÐµÐºÑÑ‚", url=doc['url'])],
        [InlineKeyboardButton(text="ðŸ”™ ÐÐ°Ð·Ð°Ð´", callback_data="all_docs")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
@dp.callback_query(F.data == "cats_stats")
async def callback_categories_stats(callback: CallbackQuery):
    """Ð”ÐµÑ‚Ð°Ð»ÑŒÐ½Ð°Ñ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð¿Ð¾ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑÐ¼"""
    cat_stats = await get_all_categories_stats()
    total = sum(cat_stats.values())
    text = "<b>ðŸ“Š Ð¡Ð¢ÐÐ¢Ð˜Ð¡Ð¢Ð˜ÐšÐ ÐŸÐž ÐšÐÐ¢Ð•Ð“ÐžÐ Ð˜Ð¯Ðœ</b>\n\n"
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': 'ðŸ“', 'desc': ''})
        percentage = (count / total * 100) if total > 0 else 0
        text += f"\n{info['icon']} <b>{info['name']}</b>\n"
        text += f"   Ð”Ð¾ÐºÑƒÐ¼ÐµÐ½Ñ‚Ð¾Ð²: <b>{count}</b> ({percentage:.1f}%)\n"
        text += f"   <i>{info['desc']}</i>\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ”™ ÐÐ°Ð·Ð°Ð´", callback_data="categories_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
# ==================== MAIN ====================
async def on_startup_webhook(bot: Bot, webhook_url: str):
    """Ð£ÑÑ‚Ð°Ð½Ð¾Ð²ÐºÐ° Ð²ÐµÐ±Ñ…ÑƒÐºÐ° Ð¿Ñ€Ð¸ ÑÑ‚Ð°Ñ€Ñ‚Ðµ"""
    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )
    logger.info(f"Webhook ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½: {webhook_url}")
async def on_shutdown(bot: Bot):
    """ÐžÑ‡Ð¸ÑÑ‚ÐºÐ° Ð¿Ñ€Ð¸ Ð¾ÑÑ‚Ð°Ð½Ð¾Ð²ÐºÐµ"""
    scheduler.shutdown()
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Ð‘Ð¾Ñ‚ Ð¾ÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½")
async def main_webhook():
    """Ð ÐµÐ¶Ð¸Ð¼ WEBHOOK Ð´Ð»Ñ Railway (Ð¿Ñ€Ð¾Ð´Ð°ÐºÑˆÐµÐ½)"""
    logger.info("Starting LexBot in WEBHOOK mode...")
    await init_database()
    # Ð—Ð°Ð¿ÑƒÑÐºÐ°ÐµÐ¼ Ð¿Ð»Ð°Ð½Ð¸Ñ€Ð¾Ð²Ñ‰Ð¸Ðº
    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='lexuz_check',
        name='Check Lex.uz',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started (interval: {CHECK_INTERVAL} min)")
    # ÐŸÐ¾Ð»ÑƒÑ‡Ð°ÐµÐ¼ Ð´Ð¾Ð¼ÐµÐ½ Railway
    RAILWAY_STATIC_URL = os.getenv("RAILWAY_STATIC_URL")
    RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if RAILWAY_STATIC_URL:
        WEBHOOK_HOST = f"https://{RAILWAY_STATIC_URL}"
    elif RAILWAY_PUBLIC_DOMAIN:
        WEBHOOK_HOST = f"https://{RAILWAY_PUBLIC_DOMAIN}"
    else:
        logger.error("ÐÐµ Ð½Ð°Ð¹Ð´ÐµÐ½ Ð´Ð¾Ð¼ÐµÐ½ Railway! ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒ Ð¿ÐµÑ€ÐµÐ¼ÐµÐ½Ð½Ñ‹Ðµ RAILWAY_STATIC_URL Ð¸Ð»Ð¸ RAILWAY_PUBLIC_DOMAIN")
        return
    WEBHOOK_PATH = f"/bot{BOT_TOKEN}"
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    # Ð£ÑÑ‚Ð°Ð½Ð°Ð²Ð»Ð¸Ð²Ð°ÐµÐ¼ Ð²ÐµÐ±Ñ…ÑƒÐº
    await on_startup_webhook(bot, WEBHOOK_URL)
    # Ð¡Ð¾Ð·Ð´Ð°ÐµÐ¼ aiohttp ÑÐµÑ€Ð²ÐµÑ€
    from aiohttp import web
    async def handle_webhook(request):
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚Ñ‡Ð¸Ðº Ð²ÐµÐ±Ñ…ÑƒÐºÐ¾Ð² Ð¾Ñ‚ Telegram"""
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
        """Health check Ð´Ð»Ñ Railway"""
        return web.Response(text="LexBot is running!")
    app = web.Application()
    app.router.add_post(f'/bot{BOT_TOKEN}', handle_webhook)
    app.router.add_get('/health', health_check)
    # Graceful shutdown
    async def cleanup(app):
        await on_shutdown(bot)
    app.on_cleanup.append(cleanup)
    # Ð—Ð°Ð¿ÑƒÑÐºÐ°ÐµÐ¼ ÑÐµÑ€Ð²ÐµÑ€
    runner = web.AppRunner(app)
    await runner.setup()
    PORT = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    logger.info(f"Server started on port {PORT}")
    await site.start()
    # Ð”ÐµÑ€Ð¶Ð¸Ð¼ Ð¿Ñ€Ð¾Ñ†ÐµÑÑ Ð¶Ð¸Ð²Ñ‹Ð¼
    while True:
        await asyncio.sleep(3600)
async def main_polling():
    """Ð ÐµÐ¶Ð¸Ð¼ POLLING Ð´Ð»Ñ Ð»Ð¾ÐºÐ°Ð»ÑŒÐ½Ð¾Ð¹ Ñ€Ð°Ð·Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ¸"""
    logger.info("Starting LexBot in POLLING mode...")
    await init_database()
    # Ð—Ð°Ð¿ÑƒÑÐºÐ°ÐµÐ¼ Ð¿Ð»Ð°Ð½Ð¸Ñ€Ð¾Ð²Ñ‰Ð¸Ðº
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
    # ÐŸÑ€Ð¾Ð²ÐµÑ€ÑÐµÐ¼ Ñ€ÐµÐ¶Ð¸Ð¼: ÐµÑÐ»Ð¸ ÐµÑÑ‚ÑŒ Ð¿ÐµÑ€ÐµÐ¼ÐµÐ½Ð½Ñ‹Ðµ Railway â€” Ð²ÐµÐ±Ñ…ÑƒÐºÐ¸, Ð¸Ð½Ð°Ñ‡Ðµ polling
    if os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        asyncio.run(main_webhook())
    else:
        asyncio.run(main_polling())
