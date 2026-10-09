"""RAG retrieval and document lifecycle endpoints."""
import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.models.schemas import RAGQueryRequest, RAGQueryResponse, KnowledgeBaseUpload
from app.rag import documents
from app.rag.retriever import get_hybrid_retriever, evidence_context

logger = logging.getLogger(__name__)
router = APIRouter()


def public_document(item):
    from app.rag.knowledge_base import get_kb_manager
    if item['status'] == 'indexed' and item['payload'].get('index_profile') != get_kb_manager().index_profile:
        item = {**item, 'status': 'needs_reindex'}
    return {key: value for key, value in item.items() if key != 'payload'} | {
        'metadata': item['payload'].get('metadata', {}),
        'chunk_count': item['payload'].get('chunk_count', 0),
    }


def failure(exc):
    if isinstance(exc, KeyError):
        return HTTPException(404, '文档不存在')
    if isinstance(exc, (ValueError, UnicodeError)):
        return HTTPException(400, str(exc))
    logger.exception('RAG operation failed')
    return HTTPException(503, '索引或检索服务暂不可用，请检查服务配置后重试')


@router.post('/rag/query', response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    try:
        chunks = await get_hybrid_retriever().retrieve(**request.model_dump())
        return RAGQueryResponse(query=request.query, chunks=evidence_context(chunks),
            total_retrieved=len(chunks), rerank_applied=any(c.get('rerank_applied') for c in chunks))
    except Exception as exc:
        raise failure(exc) from exc


@router.post('/rag/knowledge/add')
async def add_knowledge(request: KnowledgeBaseUpload):
    try:
        pages = documents.parse_file('document.md', request.content.encode())
        item = await documents.ingest(request.title, request.category, pages, request.metadata)
        return {**public_document(item), 'doc_id': item['id']}
    except Exception as exc:
        raise failure(exc) from exc


@router.post('/rag/knowledge/upload')
async def upload_knowledge(file: UploadFile = File(...), title: str = Form(''),
                           category: str = Form('general'), metadata: str = Form('{}'),
                           doc_id: str = Form('')):
    try:
        data = await file.read(documents.MAX_BYTES + 1)
        pages = await asyncio.to_thread(documents.parse_file, file.filename or '', data)
        meta = json.loads(metadata)
        if not isinstance(meta, dict):
            raise ValueError('metadata 必须是对象')
        item = await documents.ingest(title or file.filename or '文档', category, pages, meta, doc_id or None)
        return public_document(item)
    except Exception as exc:
        raise failure(exc) from exc
    finally:
        await file.close()


@router.get('/rag/knowledge/documents')
def list_documents():
    return [public_document(item) for item in documents.store().list_documents()]


@router.get('/rag/knowledge/documents/{doc_id}')
def get_document(doc_id: str):
    try:
        return documents.store().get_document(doc_id)
    except Exception as exc:
        raise failure(exc) from exc


@router.delete('/rag/knowledge/documents/{doc_id}')
async def delete_document(doc_id: str):
    try:
        await documents.remove(doc_id)
        return {'deleted': True}
    except Exception as exc:
        raise failure(exc) from exc


@router.post('/rag/knowledge/documents/{doc_id}/reindex')
async def reindex_document(doc_id: str):
    from langchain.schema import Document
    try:
        item = await asyncio.to_thread(documents.store().get_document, doc_id)
        pages = [Document(page_content=p['content'], metadata=p['metadata']) for p in item['payload'].get('pages', [])]
        result = await documents.ingest(item['title'], item['category'], pages,
            item['payload'].get('metadata'), doc_id, force=True)
        return public_document(result)
    except Exception as exc:
        raise failure(exc) from exc


@router.get('/rag/knowledge/stats')
def get_knowledge_stats():
    records = [public_document(item) for item in documents.store().list_documents()]
    indexed = [item for item in records if item['status'] == 'indexed']
    return {'total_documents': len(records), 'indexed_documents': len(indexed),
        'total_chunks': sum(item['chunk_count'] for item in indexed),
        'vectorstore_type': 'chroma'}
