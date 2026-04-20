#!/usr/bin/env python3
"""
Парсер для Lex.uz — рабочая версия
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)

@dataclass
class LawDocument:
    title: str
    doc_type: str
    doc_number: str
    date_published: str
    category: str
    description: str
    url: str

class LexUzParser:
    def __init__(self):
        self.base_url = "https://lex.uz"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
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

    async def fetch_page(self, url: str) -> Optional[str]:
        """Получение HTML страницы"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                logger.warning(f"Status {response.status} for {url}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def parse_document_list(self, html: str) -> List[LawDocument]:
        """Парсинг списка документов из HTML"""
        documents = []
        
        if not html:
            return documents
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем таблицу или список документов
        # На Lex.uz обычно это таблица с классом table или список div
        rows = (
            soup.find_all('tr', class_='doc-row') or
            soup.find_all('tr', class_=re.compile('document')) or
            soup.select('table tbody tr') or
            soup.find_all('tr')
        )
        
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                # Извлекаем данные
                doc_number = self._extract_text(cells[0])
                
                title_cell = cells[1] if len(cells) > 1 else cells[0]
                link = title_cell.find('a')
                
                title = self._extract_text(title_cell)
                href = link.get('href') if link else None
                
                date_str = self._extract_text(cells[2]) if len(cells) > 2 else ''
                
                # Определяем тип
                doc_type = self._detect_type(doc_number)
                
                # Определяем категорию по заголовку
                category = self._detect_category(title)
                
                # Формируем URL
                url = self._build_url(href, doc_number)
                
                documents.append(LawDocument(
                    title=title[:300],
                    doc_type=doc_type,
                    doc_number=doc_number[:100],
                    date_published=date_str or datetime.now().strftime('%d.%m.%Y'),
                    category=category,
                    description=title[:250],
                    url=url
                ))
                
            except Exception as e:
                logger.error(f"Error parsing row: {e}")
                continue
        
        return documents

    def _extract_text(self, element) -> str:
        """Безопасное извлечение текста"""
        if not element:
            return ''
        return element.get_text(strip=True)

    def _detect_type(self, doc_number: str) -> str:
        """Определение типа документа"""
        dn = doc_number.upper()
        if 'УП-' in dn or dn.startswith('УП'):
            return 'decree'
        elif 'ПКМ' in dn:
            return 'resolution'
        elif 'ПРИКАЗ' in dn or dn.startswith('П '):
            return 'order'
        elif 'ЗРУ' in dn or 'ЗАКОН' in dn:
            return 'law'
        return 'regulation'

    def _detect_category(self, title: str) -> str:
        """Определение категории по ключевым словам"""
        tl = title.lower()
        keywords = {
            'tax': ['налог', 'сбор', 'ндс', 'прибыль', 'акциз'],
            'labor': ['труд', 'зарплат', 'отпуск', 'работник'],
            'digital': ['цифров', 'информаци', 'интернет', 'кибер'],
            'finance': ['банк', 'валют', 'финанс', 'кредит'],
        }
        for cat, words in keywords.items():
            if any(w in tl for w in words):
                return cat
        return 'general'

    def _build_url(self, href: Optional[str], doc_number: str) -> str:
        """Построение URL документа"""
        if href:
            if href.startswith('/'):
                return f"{self.base_url}{href}"
            elif href.startswith('http'):
                return href
        
        # Поисковый URL как fallback
        return f"{self.base_url}/ru/search/all/?text={doc_number.replace(' ', '+')}"

    async def fetch_new_documents(self) -> List[LawDocument]:
        """Основной метод получения документов"""
        url = f"{self.base_url}/ru/lists/all/"
        html = await self.fetch_page(url)
        
        if html:
            return self.parse_document_list(html)
        return []

    async def fetch_by_category(self, category_url: str) -> List[LawDocument]:
        """Получение документов по категории"""
        html = await self.fetch_page(category_url)
        if html:
            return self.parse_document_list(html)
        return []

# Тестирование
async def test_parser():
    logging.basicConfig(level=logging.INFO)
    
    async with LexUzParser() as parser:
        docs = await parser.fetch_new_documents()
        print(f"Найдено документов: {len(docs)}")
        
        for doc in docs[:3]:
            print(f"\n{doc.doc_type.upper()}: {doc.title[:60]}...")
            print(f"   Номер: {doc.doc_number}")
            print(f"   Дата: {doc.date_published}")
            print(f"   URL: {doc.url}")

if __name__ == "__main__":
    asyncio.run(test_parser())