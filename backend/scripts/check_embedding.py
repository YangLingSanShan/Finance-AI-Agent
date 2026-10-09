"""Opt-in live Embedding probe. Never print credentials or provider response bodies."""
import asyncio
import json
import logging
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.llm import LLMService


async def main():
    logging.disable(logging.CRITICAL)
    service = LLMService()
    settings = service.settings
    endpoint = urlsplit(settings.EMBEDDING_API_BASE)
    result = {'host': endpoint.hostname, 'path': endpoint.path,
              'model': settings.EMBEDDING_MODEL, 'dimensions': settings.EMBEDDING_DIM,
              'key_present': bool(settings.EMBEDDING_API_KEY)}
    try:
        await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, endpoint.hostname,
                                                 endpoint.port or 443), 10)
        result['dns'] = 'ok'
        vectors = await asyncio.wait_for(service.embed(['公开披露资料检索连接测试']), 30)
        result.update(success=True, returned_dimensions=len(vectors[0]))
    except Exception as exc:
        result.update(success=False, error_type=type(exc).__name__,
                      http_status=getattr(exc, 'status_code', None))
        if isinstance(exc, socket.gaierror):
            result['dns'] = 'failed'
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
