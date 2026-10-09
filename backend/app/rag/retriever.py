"""Local Chinese BM25 + Chroma dense retrieval with RRF and optional local reranking."""
import asyncio
import math
import re
from collections import Counter
from functools import lru_cache
from app.core.llm import get_llm_service
from app.rag.knowledge_base import get_kb_manager
from app.rag.query_rewrite import QueryRewriter
from app.config import get_settings


def tokens(text):
    parts = re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]+', text.lower())
    output = []
    for part in parts:
        if re.fullmatch(r'[\u4e00-\u9fff]+', part):
            output.extend(part)
            output.extend(part[i:i + 2] for i in range(len(part) - 1))
        else:
            output.append(part)
    return output


def bm25(query, texts):
    docs = [Counter(tokens(text)) for text in texts]
    lengths = [sum(d.values()) for d in docs]
    average = sum(lengths) / max(len(docs), 1) or 1
    scores = [0.0] * len(docs)
    for term in set(tokens(query)):
        freq = sum(term in doc for doc in docs)
        idf = math.log(1 + (len(docs) - freq + .5) / (freq + .5))
        for i, doc in enumerate(docs):
            tf = doc[term]
            scores[i] += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * lengths[i] / average))
    return scores


def matches(meta, filters):
    for key, expected in (filters or {}).items():
        value = meta.get(key)
        if isinstance(expected, dict):
            for op, bound in expected.items():
                if op not in ('$gte', '$lte', '$eq'):
                    raise ValueError('过滤只支持 $gte/$lte/$eq')
                if value is None:
                    return False
                if op == '$gte' and value < bound or op == '$lte' and value > bound or op == '$eq' and value != bound:
                    return False
        elif value != expected:
            return False
    return True


@lru_cache(maxsize=1)
def reranker(path):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(path, max_length=512, local_files_only=True)


class HybridRetriever:
    def __init__(self, llm_service=None):
        self.llm = llm_service or get_llm_service()
        self.kb = get_kb_manager()

    async def retrieve(self, query, top_k=10, score_threshold=.5, filters=None, enable_rerank=True,
                       enable_rewrite=True):
        if filters:
            for key, value in filters.items():
                if key not in ('stock_code', 'category', 'disclosure_date', 'report_period', 'doc_id'):
                    raise ValueError('不支持的过滤字段')
                if not isinstance(value, (str, dict)):
                    raise ValueError('过滤值必须为字符串或比较对象')
                if isinstance(value, dict) and any(not isinstance(v, str) for v in value.values()):
                    raise ValueError('过滤边界必须为字符串')
                if isinstance(value, dict) and any(op not in ('$gte', '$lte', '$eq') for op in value):
                    raise ValueError('不支持的过滤运算符')
        collection = self.kb.collection
        # Local-scale corpus: load active metadata/text for BM25 and common filtering.
        raw = await asyncio.to_thread(collection.get, include=['documents', 'metadatas'])
        from app.rag.documents import store
        records = await asyncio.to_thread(store().list_documents)
        active = {d['id']: d for d in records if d['status'] == 'indexed'}
        candidates = {}
        for cid, content, meta in zip(raw['ids'], raw['documents'], raw['metadatas']):
            meta = meta or {}
            if meta.get('doc_id'):
                doc = active.get(meta['doc_id'])
                if not doc or meta.get('revision') != doc['payload'].get('revision'):
                    continue
            if matches(meta, filters):
                candidates[cid] = {'chunk_id': cid, 'content': content, 'metadata': meta}
        if not candidates:
            return []
        queries = [query]
        if enable_rewrite:
            rewriter = QueryRewriter()
            rewriter.llm = self.llm
            rewrite = await rewriter.rewrite(query)
            optimized = rewrite.get('rewritten_query')
            if isinstance(optimized, str) and optimized.strip() and optimized != query:
                queries.append(optimized[:4000])
        embeddings = await self.llm.embed(queries)
        if len(embeddings) != len(queries):
            raise RuntimeError('查询 Embedding 返回数量不正确')
        # Candidate IDs guarantee staged/deleted revisions cannot displace active results.
        dense = await asyncio.to_thread(collection.query, query_embeddings=embeddings,
            ids=list(candidates), n_results=min(len(candidates), max(20, top_k * 4)),
            include=['distances'])
        fused, similarity, lexical = Counter(), {}, {}
        ids = list(candidates)
        for index, q in enumerate(queries):
            dense_ids = []
            for cid, distance in zip(dense['ids'][index], dense['distances'][index]):
                score = 1 - distance
                similarity[cid] = max(similarity.get(cid, -1), score)
                if score >= score_threshold:
                    dense_ids.append(cid)
            sparse = bm25(q, [candidates[cid]['content'] for cid in ids])
            sparse_scores = dict(zip(ids, sparse))
            sparse_ids = sorted((cid for cid in ids if sparse_scores[cid] > 0),
                                key=sparse_scores.get, reverse=True)[:max(20, top_k * 4)]
            lexical.update({cid: score for cid, score in zip(ids, sparse)})
            for ranked in (dense_ids, sparse_ids):
                for rank, cid in enumerate(ranked, 1):
                    fused[cid] += 1 / (60 + rank)
        chunks = [{**candidates[cid], 'score': max(0, similarity.get(cid, 0)),
                   'bm25_score': lexical.get(cid, 0), 'rrf_score': score,
                   'rerank_applied': False} for cid, score in fused.most_common(max(20, top_k * 4))]
        path = get_settings().RAG_RERANK_MODEL
        if enable_rerank and path and len(chunks) > 1:
            try:
                model = await asyncio.to_thread(reranker, path)
                scores = await asyncio.to_thread(model.predict, [(query, c['content']) for c in chunks])
                if len(scores) != len(chunks):
                    raise RuntimeError('重排结果数量不一致')
                for chunk, score in zip(chunks, scores):
                    chunk.update(rerank_score=float(score), rerank_applied=True)
                chunks.sort(key=lambda c: c['rerank_score'], reverse=True)
            except Exception:
                for chunk in chunks:
                    chunk['rerank_warning'] = '重排不可用，已保留 RRF 排序'
        elif enable_rerank:
            for chunk in chunks:
                chunk['rerank_warning'] = '未配置本地重排模型或候选不足，使用 RRF 排序'
        return chunks[:top_k]

    async def retrieve_with_expansion(self, query, top_k=10, **kwargs):
        return await self.retrieve(query, top_k=top_k, enable_rewrite=True, **kwargs)


hybrid_retriever = HybridRetriever()


def get_hybrid_retriever():
    return hybrid_retriever


def evidence_context(chunks, budget=None):
    """Assign stable per-answer citations and expose precisely the text passed to the LLM."""
    remaining = budget if budget is not None else get_settings().RAG_MAX_CONTEXT_LENGTH
    evidence = []
    for chunk in chunks:
        meta = chunk.get('metadata', {})
        label = f"[来源{len(evidence) + 1}] {meta.get('title', '文档')} 页码:{meta.get('page', '-')} 章节:{meta.get('section', '-')}"
        header = f"{label}\n来源:{meta.get('source_url', '-')} 披露日期:{meta.get('disclosure_date', '-')}\n"
        if remaining <= len(header) + 20:
            break
        content = chunk['content'][:remaining - len(header)]
        evidence.append({**chunk, 'citation': f'来源{len(evidence) + 1}', 'content': content, 'label': header.strip()})
        remaining -= len(header) + len(content)
    return evidence
