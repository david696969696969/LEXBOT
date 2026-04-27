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
    print("pip install beautifulsoup4 lxml")
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
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))
LEX_UZ_URL = 'https://lex.uz'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ==================== 15 КАТЕГОРИЙ С УЗБЕКСКИМИ ТЕГАМИ ====================

CATEGORIES = {
    'tax': {
        'name': 'Налоги и сборы',
        'icon': '💰',
        'hashtag': '#Налоги',
        'uz_tags': ['#Soliq', '#Bojxona', '#NDS', '#Daromad', '#Byudjet'],
        'keywords': ['налог', 'сбор', 'ндс', 'прибыль', 'акциз', 'таможен', 'пошлин', 'бюджет', 'сбора', 'налогов', 'солиқ', 'божхона']
    },
    'economy': {
        'name': 'Экономика и бизнес',
        'icon': '📈',
        'hashtag': '#Экономика',
        'uz_tags': ['#Iqtisodiyot', '#Biznes', '#Tadbirkorlik', '#Investitsiya'],
        'keywords': ['эконом', 'бизнес', 'предприниматель', 'инвести', 'госзакуп', 'концесс', 'франшиз', 'торговл', 'предприят', 'коммерц', 'иқтисод', 'бизнес']
    },
    'labor': {
        'name': 'Трудовое право',
        'icon': '👷',
        'hashtag': '#Труд',
        'uz_tags': ['#Mehnat', '#Ish', '#Maosh', '#Tatil', '#Xodim'],
        'keywords': ['труд', 'зарплат', 'отпуск', 'работник', 'занятост', 'профсоюз', 'коллектив', 'работодат', 'трудовой', 'меҳнат', 'иш', 'маош']
    },
    'digital': {
        'name': 'IT и цифровизация',
        'icon': '💻',
        'hashtag': '#IT',
        'uz_tags': ['#IT', '#Raqamlashtirish', '#Internet', '#Kiber', '#Dasturiy'],
        'keywords': ['цифров', 'информаци', 'коммуникаци', 'интернет', 'электрон', 'кибер', 'программ', 'телеком', 'айти', 'it', 'технолог', 'рақамлаштириш']
    },
    'civil': {
        'name': 'Гражданское право',
        'icon': '⚖️',
        'hashtag': '#ГражданскоеПраво',
        'uz_tags': ['#Fuqarolik', '#Shartnoma', '#Mulk', '#Meros'],
        'keywords': ['граждан', 'договор', 'собствен', 'наслед', 'обязательств', 'недвижим', 'жилищ', 'семейн', 'фуқаролик', 'шартнома', 'мулк']
    },
    'criminal': {
        'name': 'Уголовное право',
        'icon': '🚔',
        'hashtag': '#УголовноеПраво',
        'uz_tags': ['#Jinoyat', '#Jazo', '#Korrupsiya', '#Terror'],
        'keywords': ['уголовн', 'преступлен', 'наказан', 'экстремизм', 'терроризм', 'коррупц', 'взяточнич', 'контрабанд', 'отмыван', 'жиноят', 'жазо']
    },
    'administrative': {
        'name': 'Административное право',
        'icon': '📋',
        'hashtag': '#Административное',
        'uz_tags': ['#Ma muriyat', '#Jarima', '#Litsenziya', '#Ruxsatnoma'],
        'keywords': ['административ', 'штраф', 'лиценз', 'разрешен', 'регистрац', 'проверка', 'инспекц', 'контроль', 'маъмурият', 'жарима', 'лицензия']
    },
    'environment': {
        'name': 'Экология',
        'icon': '🌿',
        'hashtag': '#Экология',
        'uz_tags': ['#Ekologiya', '#Tabiat', '#AtrofMuhit', '#Chiqindi'],
        'keywords': ['эколог', 'природ', 'окружающ', 'земл', 'вод', 'воздух', 'отход', 'охрана', 'загрязнен', 'лес', 'экология', 'табиат']
    },
    'health': {
        'name': 'Здравоохранение',
        'icon': '🏥',
        'hashtag': '#Здравоохранение',
        'uz_tags': ['#SogliqniSaqlash', '#Tibbiyot', '#Dori', '#Shifokor'],
        'keywords': ['здравоохран', 'медицин', 'фармац', 'лекарств', 'врач', 'больниц', 'эпидем', 'санитар', 'клинич', 'соғлиқни сақлаш', 'тиббиёт']
    },
    'education': {
        'name': 'Образование',
        'icon': '🎓',
        'hashtag': '#Образование',
        'uz_tags': ['#Talim', '#Maktab', '#Universitet', '#Oqituvchi', '#Talaba'],
        'keywords': ['образован', 'школ', 'университет', 'академ', 'студент', 'учитель', 'аттестат', 'диплом', 'учебн', 'таълим', 'мактаб', 'университет']
    },
    'finance': {
        'name': 'Финансы и банки',
        'icon': '🏦',
        'hashtag': '#Финансы',
        'uz_tags': ['#Moliya', '#Bank', '#Valyuta', '#Kredit', '#Sugurta'],
        'keywords': ['банк', 'валют', 'финанс', 'кредит', 'страхован', 'бирж', 'ценн бумаг', 'ипотек', 'аудит', 'бухгалт', 'молия', 'банк', 'валюта']
    },
    'trade': {
        'name': 'Торговля и таможня',
        'icon': '🌍',
        'hashtag': '#Торговля',
        'uz_tags': ['#Savdo', '#Tamojnya', '#Eksport', '#Import', '#Tovar'],
        'keywords': ['торговл', 'таможн', 'внешнеторг', 'экспорт', 'импорт', 'товар', 'контракт', 'перевозк', 'логистик', 'савдо', 'таможня', 'экспорт']
    },
    'construction': {
        'name': 'Строительство',
        'icon': '🏗️',
        'hashtag': '#Строительство',
        'uz_tags': ['#Qurilish', '#Arxitektura', '#Uy', '#Kvartira', '#Remont'],
        'keywords': ['строитель', 'архитектур', 'жкх', 'капремонт', 'жил', 'дом', 'квартир', 'ремонт', 'инфраструктур', 'қурилиш', 'архитектура', 'уй']
    },
    'transport': {
        'name': 'Транспорт',
        'icon': '🚛',
        'hashtag': '#Транспорт',
        'uz_tags': ['#Transport', '#Avto', '#Avia', '#TemirYol', '#Haydovchi'],
        'keywords': ['транспорт', 'авто', 'авиа', 'ж/д', 'дорог', 'водител', 'перевозк', 'логистик', 'автомобил', 'транспорт', 'авто', 'авиа']
    },
    'energy': {
        'name': 'Энергетика',
        'icon': '⚡',
        'hashtag': '#Энергетика',
        'uz_tags': ['#Energetika', '#Elektr', '#Gaz', '#Neft', '#Yoqilgi'],
        'keywords': ['энерг', 'электро', 'газ', 'нефт', 'топлив', 'атом', 'возобновляем', 'тепл', 'солнечн', 'ветр', 'энергетика', 'электр', 'газ']
    },
    'general': {
        'name': 'Общие',
        'icon': '📁',
        'hashtag': '#Общие',
        'uz_tags': ['#Umumiy'],
        'keywords': []
    },
}

DOC_TYPES = {
    'law': {'name': 'Закон', 'icon': '📜'},
    'decree': {'name': 'Указ Президента', 'icon': '⚡'},
    'resolution': {'name': 'Постановление КМ', 'icon': '📋'},
    'order': {'name': 'Приказ', 'icon': '📄'},
    'regulation': {'name': 'Нормативный акт', 'icon': '📑'},
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

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9',
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_category(self, title: str) -> str:
        title_lower = title.lower()
        scores = {}
        for cat_key, cat_info in CATEGORIES.items():
            if cat_key == 'general':
                continue
            score = 0
            for keyword in cat_info['keywords']:
                if keyword in title_lower:
                    score += 1
            if score > 0:
                scores[cat_key] = score
        
        if scores:
            return max(scores, key=scores.get)
        return 'general'

    def _get_doc_type(self, doc_number: str) -> str:
        doc_upper = doc_number.upper()
        if 'УП-' in doc_upper or doc_upper.startswith('УП') or 'УКАЗ' in doc_upper:
            return 'decree'
        elif 'ПКМ' in doc_upper or 'ПОСТАНОВЛЕНИЕ' in doc_upper:
            return 'resolution'
        elif 'ПРИКАЗ' in doc_upper or doc_upper.startswith('П '):
            return 'order'
        elif 'ЗРУ' in doc_upper or 'ЗАКОН' in doc_upper:
            return 'law'
        return 'regulation'

    def _get_hashtags(self, category: str) -> str:
        cat_info = CATEGORIES.get(category, {})
        hashtags = []
        if 'hashtag' in cat_info:
            hashtags.append(cat_info['hashtag'])
        if 'uz_tags' in cat_info:
            hashtags.extend(cat_info['uz_tags'][:2])
        return ' '.join(hashtags) if hashtags else ''

    async def fetch_new_documents(self) -> List[LawDocument]:
        documents = []
        if not BeautifulSoup:
            logger.error("BeautifulSoup not installed")
            return documents

        urls_to_try = [
            "https://lex.uz/ru/",
            "https://lex.uz/ru/search/all/",
            "https://lex.uz/ru/docs/",
        ]
        
        html = None
        
        for url in urls_to_try:
            try:
                logger.info(f"Trying {url}")
                async with self.session.get(url, allow_redirects=True) as response:
                    logger.info(f"Status: {response.status}")
                    if response.status == 200:
                        html = await response.text()
                        break
            except Exception as e:
                logger.error(f"Error with {url}: {e}")
                continue
        
        if not html:
            logger.error("All URLs failed")
            return documents

        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=True)
        doc_links = []
        
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            if '/docs/' in href and text and len(text) > 10:
                doc_links.append((text, href))
        
        logger.info(f"Found {len(doc_links)} potential documents")
        
        for title, href in doc_links[:30]:
            try:
                doc_type = 'regulation'
                title_lower = title.lower()
                if 'закон' in title_lower or 'ЗРУ' in title:
                    doc_type = 'law'
                elif 'указ' in title_lower:
                    doc_type = 'decree'
                elif 'постановление' in title_lower:
                    doc_type = 'resolution'
                elif 'приказ' in title_lower:
                    doc_type = 'order'
                
                if href.startswith('/'):
                    url = f'{self.base_url}{href}'
                elif href.startswith('http'):
                    url = href
                else:
                    url = f'{self.base_url}/ru/docs/{href}'
                
                doc_number = href.split('/')[-1] if '/' in href else 'unknown'
                category = self._get_category(title)
                
                documents.append(LawDocument(
                    id=0,
                    title=title[:300],
                    doc_type=doc_type,
                    doc_number=doc_number[:100],
                    date_published=datetime.now().strftime('%d.%m.%Y'),
                    date_effective=datetime.now().strftime('%d.%m.%Y'),
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
                logger.error(f'Parse error: {e}')
                continue

        logger.info(f'Parsed {len(documents)} documents')
        return documents

    async def test_connection(self) -> bool:
        try:
            async with self.session.get(self.base_url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Site unavailable: {e}")
            return False

# ==================== DATABASE ====================

async def init_database():
    async with aiosqlite.connect(DATABASE_PATH) as db:
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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
            SELECT * FROM documents WHERE category = ? ORDER BY created_at DESC LIMIT ?
        """, (category, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_documents_by_period(days: int = 7) -> List[Dict]:
    """Получить документы за последние N дней"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM documents 
            WHERE created_at >= datetime('now', '-{} days')
            ORDER BY created_at DESC
        """.format(days)) as cursor:
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

# ==================== CHECK & NOTIFY ====================

async def check_new_documents():
    logger.info("Checking for new documents...")
    try:
        async with LexUzParser() as parser:
            if not await parser.test_connection():
                logger.error("Lex.uz unavailable")
                return
            new_docs = await parser.fetch_new_documents()

        if not new_docs:
            logger.info("No documents found")
            return

        new_count = 0
        for doc in new_docs[:50]:
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
                logger.error(f"Error processing doc {doc.doc_number}: {e}")
                continue

        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                INSERT INTO check_logs (new_documents, updated_documents, status)
                VALUES (?, ?, ?)
            """, (new_count, 0, 'success'))
            await db.commit()

        logger.info(f"Check completed. New: {new_count}")
        if new_count > 0 and ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"Added {new_count} documents")

    except Exception as e:
        logger.error(f"Check error: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def notify_subscribers(doc: LawDocument, is_update: bool = False):
    subscribers = await get_all_subscribers()
    if not subscribers:
        return

    type_info = DOC_TYPES.get(doc.doc_type, {'name': 'Документ', 'icon': '📄'})
    cat_info = CATEGORIES.get(doc.category, {'name': doc.category, 'icon': '📁'})
    parser = LexUzParser()
    hashtags = parser._get_hashtags(doc.category)

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

<b>🏷️ Теги:</b>
{hashtags}

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

# ==================== DIGEST / OVERVIEW ====================

async def generate_digest(days: int = 7) -> str:
    """Генерация дайджеста за период"""
    docs = await get_documents_by_period(days)
    
    if not docs:
        return "📭 За указанный период документов не найдено"
    
    # Группируем по категориям
    by_category = {}
    for doc in docs:
        cat = doc['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(doc)
    
    # Формируем текст
    period_text = "неделю" if days == 7 else f"{days} дней"
    
    text = f"""<b>📰 ОБЗОР ЗАКОНОДАТЕЛЬСТВА</b>
<i>За последнюю {period_text}</i>

<b>📊 Всего документов: {len(docs)}</b>

"""
    
    # Сортируем категории по количеству документов
    sorted_cats = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)
    
    for cat_key, cat_docs in sorted_cats:
        if cat_key == 'general':
            continue
            
        cat_info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁'})
        hashtags = LexUzParser()._get_hashtags(cat_key)
        
        text += f"\n<b>{cat_info['icon']} {cat_info['name']}</b> {hashtags}\n"
        text += f"<i>{len(cat_docs)} документов</i>\n\n"
        
        for i, doc in enumerate(cat_docs[:3], 1):  # Максимум 3 в категории
            type_info = DOC_TYPES.get(doc['doc_type'], {'icon': '📄'})
            text += f"{i}. {type_info['icon']} {doc['title'][:60]}...\n"
            text += f"   <a href='{doc['url']}'>Подробнее →</a>\n"
        
        if len(cat_docs) > 3:
            text += f"\n   <i>+{len(cat_docs) - 3} ещё</i>\n"
        
        text += "\n"
    
    return text

async def send_digest_to_subscribers(days: int = 7):
    """Отправить дайджест всем подписчикам"""
    digest = await generate_digest(days)
    subscribers = await get_all_subscribers()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Полная статистика", callback_data="stats")],
        [InlineKeyboardButton(text="📁 Все категории", callback_data="categories_menu")]
    ])
    
    for sub in subscribers:
        try:
            await bot.send_message(
                sub['user_id'],
                digest,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Digest error for {sub['user_id']}: {e}")

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
• Категорий: <b>{len(CATEGORIES) - 1}</b>

<b>📋 Команды:</b>
/documents — Все документы
/categories — По категориям
/digest — Обзор за неделю
/stats — Статистика
/help — Помощь
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Документы", callback_data="all_docs"),
         InlineKeyboardButton(text="📰 Обзор", callback_data="digest_week")],
        [InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
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
        hashtags = LexUzParser()._get_hashtags(doc['category'])

        text += f"{i}. {type_info['icon']} <b>{doc['title'][:80]}</b>\n"
        text += f"   <code>{doc['doc_number']}</code>\n"
        text += f"   📅 {doc['date_published']} | {cat_info['icon']} {cat_info['name']}\n"
        text += f"   🏷️ {hashtags}\n"
        text += f"   <a href='{doc['url']}'>Открыть →</a>\n\n"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    cat_stats = await get_all_categories_stats()

    text = "<b>📁 КАТЕГОРИИ ЗАКОНОДАТЕЛЬСТВА</b>\n\nВыберите категорию:\n\n"

    keyboard_buttons = []
    row = []
    for key, info in CATEGORIES.items():
        if key == 'general':
            continue
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

@dp.message(Command("digest"))
async def cmd_digest(message: Message):
    """Обзор за неделю"""
    digest = await generate_digest(7)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 За 3 дня", callback_data="digest_3"),
         InlineKeyboardButton(text="📅 За 7 дней", callback_data="digest_7")],
        [InlineKeyboardButton(text="📅 За 30 дней", callback_data="digest_30")]
    ])
    
    await message.answer(digest, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    cat_stats = await get_all_categories_stats()
    total_docs = sum(cat_stats.values())

    text = f"<b>📊 СТАТИСТИКА</b>\n\n<b>📚 Всего документов: {total_docs}</b>\n\n<b>📁 По категориям:</b>\n"
    
    for cat_key, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            info = CATEGORIES.get(cat_key, {'name': cat_key, 'icon': '📁'})
            hashtags = info.get('hashtag', '')
            uz_tags = ' '.join(info.get('uz_tags', [])[:1])
            text += f"\n{info['icon']} {info['name']}: {count}"
            text += f"\n   🏷️ {hashtags} {uz_tags}"

    await message.answer(text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("""
<b>❓ ПОМОЩЬ — KPMG Law LexBot</b>

<b>📋 Команды:</b>
/start — Начать работу
/documents — Все документы
/categories — По категориям (15 категорий)
/digest — Обзор законодательства
/stats — Статистика
/help — Помощь

<b>🏷️ Узбекские теги:</b>
#Soliq #Mehnat #IT #Talim #Savdo

<b>🏛️ KPMG Law Uzbekistan</b>
""", parse_mode="HTML")

# ==================== CALLBACKS ====================

@dp.callback_query(F.data == "all_docs")
async def callback_all_docs(callback: CallbackQuery):
    await cmd_documents(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "categories_menu")
async def callback_categories_menu(callback: CallbackQuery):
    await cmd_categories(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "digest_week")
async def callback_digest_week(callback: CallbackQuery):
    digest = await generate_digest(7)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 За 3 дня", callback_data="digest_3"),
         InlineKeyboardButton(text="📅 За 30 дней", callback_data="digest_30")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text(digest, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("digest_"))
async def callback_digest_period(callback: CallbackQuery):
    days = int(callback.data.replace("digest_", ""))
    digest = await generate_digest(days)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 За 3 дня", callback_data="digest_3"),
         InlineKeyboardButton(text="📅 За 7 дней", callback_data="digest_7"),
         InlineKeyboardButton(text="📅 За 30 дней", callback_data="digest_30")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    
    await callback.message.edit_text(digest, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def callback_back_main(callback: CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def callback_category(callback: CallbackQuery):
    category = callback.data.replace("cat_", "")
    if category not in CATEGORIES:
        await callback.answer("Категория не найдена")
        return

    cat_info = CATEGORIES[category]
    docs = await get_documents_by_category(category, limit=10)
    hashtags = LexUzParser()._get_hashtags(category)

    if not docs:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n🏷️ {hashtags}\n\n📭 Нет документов"
    else:
        text = f"<b>{cat_info['icon']} {cat_info['name']}</b>\n\n🏷️ {hashtags}\n\n📚 Найдено: <b>{len(docs)}</b>\n\n"
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

# ==================== WEBHOOK / POLLING ====================

async def on_startup_webhook(bot: Bot, webhook_url: str):
    try:
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        logger.info(f"Webhook: {webhook_url}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")

async def on_shutdown(bot: Bot):
    try:
        scheduler.shutdown()
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

async def main_webhook():
    logger.info("Starting WEBHOOK mode...")
    await init_database()

    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='lexuz_check',
        replace_existing=True
    )
    scheduler.start()

    RAILWAY_STATIC_URL = os.getenv("RAILWAY_STATIC_URL")
    RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")

    if RAILWAY_STATIC_URL:
        WEBHOOK_HOST = f"https://{RAILWAY_STATIC_URL}"
    elif RAILWAY_PUBLIC_DOMAIN:
        WEBHOOK_HOST = f"https://{RAILWAY_PUBLIC_DOMAIN}"
    else:
        logger.error("No Railway domain!")
        return

    WEBHOOK_URL = f"{WEBHOOK_HOST}/bot{BOT_TOKEN}"
    await on_startup_webhook(bot, WEBHOOK_URL)

    from aiohttp import web

    async def handle_webhook(request):
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
        return web.Response(text="LexBot OK")

    app = web.Application()
    app.router.add_post(f'/bot{BOT_TOKEN}', handle_webhook)
    app.router.add_get('/health', health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", "8080")))
    await site.start()

    while True:
        await asyncio.sleep(3600)

async def main_polling():
    logger.info("Starting POLLING mode...")
    await init_database()

    scheduler.add_job(
        check_new_documents,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL),
        id='lexuz_check',
        replace_existing=True
    )
    scheduler.start()

    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await on_shutdown(bot)

if __name__ == "__main__":
    if os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        asyncio.run(main_webhook())
    else:
        asyncio.run(main_polling())