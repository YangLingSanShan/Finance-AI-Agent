"""Document lifecycle: stage vectors, then atomically publish the active revision."""
import asyncio
import hashlib
import io
import json
import uuid
from pathlib import Path
from langchain.schema import Document
from app.rag.knowledge_base import get_kb_manager

lock = asyncio.Lock()  # Single-worker deployment, matching report jobs.
MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 2_000_000


def store():
    from app.agents.orchestrator import get_orchestrator
    return get_orchestrator().store


def parse_file(name, data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('文件不能为空，且不能超过 10 MB')
    extension = Path(name).suffix.lower()
    if extension == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > 500:
            raise ValueError('不支持加密 PDF 或超过 500 页的 PDF')
        pages = []
        total = 0
        for index, page in enumerate(reader.pages):
            text = page.extract_text(extraction_mode='layout') or ''
            total += len(text)
            if total > MAX_TEXT:
                raise ValueError('解析文本超过 200 万字符，请拆分文件')
            if not text.strip():
                raise ValueError(f'第 {index + 1} 页没有可提取文字；请先 OCR 后上传，避免漏掉扫描页')
            pages.append(Document(page_content=text, metadata={'page': index + 1}))
        return pages
    if extension not in ('.txt', '.md'):
        raise ValueError('仅支持 PDF、UTF-8 TXT 和 Markdown')
    text = data.decode('utf-8-sig')
    if not text.strip() or len(text) > MAX_TEXT:
        raise ValueError('文本为空或超过 200 万字符')
    # Keep Markdown sections as provenance; TXT has a single section.
    pages, section, lines = [], '', []
    for line in text.splitlines(keepends=True):
        if extension == '.md' and line.startswith('#'):
            if ''.join(lines).strip():
                pages.append(Document(page_content=''.join(lines), metadata={'section': section}))
            section, lines = line.lstrip('#').strip(), []
        lines.append(line)
    if ''.join(lines).strip():
        pages.append(Document(page_content=''.join(lines), metadata={'section': section}))
    return pages


def validate_metadata(value):
    from datetime import date
    allowed = ('source_url', 'stock_code', 'report_period', 'disclosure_date')
    result = {key: str(value[key]).strip() for key in allowed if value.get(key)}
    if result.get('disclosure_date'):
        date.fromisoformat(result['disclosure_date'])
        result['disclosure_day'] = date.fromisoformat(result['disclosure_date']).toordinal()
    if result.get('source_url'):
        from urllib.parse import urlparse
        if urlparse(result['source_url']).scheme not in ('http', 'https'):
            raise ValueError('来源链接必须是 http 或 https 地址')
    if result.get('stock_code'):
        import re
        if not re.fullmatch(r'[0-9]{6}', result['stock_code']):
            raise ValueError('股票代码应为六位数字')
    return result


async def ingest(title, category, pages, metadata=None, doc_id=None, force=False):
    title, category = title.strip(), category.strip()
    if not title or not category or not pages:
        raise ValueError('标题、分类和内容不能为空')
    meta = validate_metadata(metadata or {})
    digest = hashlib.sha256(json.dumps({'pages': [(p.page_content, p.metadata) for p in pages],
        'title': title, 'category': category, 'metadata': meta}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    async with lock:
        db = store()
        old = await asyncio.to_thread(db.get_document, doc_id) if doc_id else None
        records = await asyncio.to_thread(db.list_documents)
        kb = get_kb_manager()
        for item in records:
            if not force and item['content_hash'] == digest and item['status'] == 'indexed' and item['payload'].get('index_profile') == kb.index_profile:
                if doc_id and item['id'] != doc_id:
                    raise ValueError('相同内容已存在于另一文档，请删除重复文档后更新')
                return {**item, 'deduplicated': True}
        doc_id = doc_id or str(uuid.uuid4())
        revision = str(uuid.uuid4())
        kb = get_kb_manager()
        chunks = kb.chunk_documents(pages)
        if not chunks:
            raise ValueError('没有可索引的正文')
        for index, chunk in enumerate(chunks):
            chunk.chunk_id = f'{doc_id}:{revision}:{index}'
            chunk.metadata = {**chunk.metadata, **meta, 'doc_id': doc_id, 'revision': revision,
                              'title': title, 'category': category}
        payload = {'index_profile': kb.index_profile, 'metadata': meta, 'revision': revision, 'chunk_count': len(chunks),
                   'chunk_ids': [c.chunk_id for c in chunks],
                   'pages': [{'content': p.page_content, 'metadata': p.metadata} for p in pages]}
        if old is None:
            await asyncio.to_thread(db.save_document, doc_id, title, category, digest, payload, 'indexing')
        try:
            count = await kb.add_chunks_to_vectorstore(chunks)
            if count != len(chunks):
                raise RuntimeError('向量索引写入不完整')
            await asyncio.to_thread(db.save_document, doc_id, title, category, digest, payload, 'indexed')
        except BaseException as exc:
            try:
                await asyncio.to_thread(kb.collection.delete, where={'revision': revision})
            except Exception:
                pass  # Unpublished revisions are always excluded from retrieval.
            if old is None:
                await asyncio.to_thread(db.save_document, doc_id, title, category, digest, payload, 'failed', str(exc))
            raise
        # Published new revision first. Old vectors cannot be retrieved even if cleanup fails.
        if old and old['payload'].get('revision'):
            try:
                await asyncio.to_thread(kb.collection.delete, where={'revision': old['payload']['revision']})
            except Exception:
                pass
        return await asyncio.to_thread(db.get_document, doc_id)


async def remove(doc_id):
    async with lock:
        db = store()
        item = await asyncio.to_thread(db.get_document, doc_id)
        # Hide from search before deleting vectors, including after a crash.
        await asyncio.to_thread(db.save_document, doc_id, item['title'], item['category'],
            item['content_hash'], item['payload'], 'deleting')
        try:
            await asyncio.to_thread(get_kb_manager().collection.delete, where={'doc_id': doc_id})
            await asyncio.to_thread(db.delete_document, doc_id)
        except Exception as exc:
            await asyncio.to_thread(db.save_document, doc_id, item['title'], item['category'],
                item['content_hash'], item['payload'], 'deleting', str(exc))
            raise
