import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.orchestrator import get_orchestrator

router = APIRouter(prefix='/conversations')


class ArchiveRequest(BaseModel):
    archived: bool


@router.get('')
def list_conversations(archived: bool = False):
    return get_orchestrator().store.list(archived)


@router.post('', status_code=201)
def create_conversation():
    return get_orchestrator().store.create()


@router.get('/{session_id}')
def get_conversation(session_id: str):
    store = get_orchestrator().store
    try:
        session = store.get(session_id)
    except KeyError:
        raise HTTPException(404, '对话不存在或已删除')
    messages = []
    for turn in store.turns(session_id):
        messages.extend([
            {'role': 'user', 'content': turn['query']},
            {'role': 'assistant', 'content': turn['final_response'], **turn.get('response_metadata', {})},
        ])
    return {**session, 'messages': messages}


@router.patch('/{session_id}')
async def archive_conversation(session_id: str, request: ArchiveRequest):
    orchestrator = get_orchestrator()
    async with orchestrator.session_lock(session_id):
        try:
            return await asyncio.to_thread(orchestrator.store.archive, session_id, request.archived)
        except KeyError:
            raise HTTPException(404, '对话不存在或已删除')


@router.delete('/{session_id}', status_code=204)
async def delete_conversation(session_id: str):
    orchestrator = get_orchestrator()
    async with orchestrator.session_lock(session_id):
        try:
            await asyncio.to_thread(orchestrator.store.delete, session_id)
        except KeyError:
            raise HTTPException(404, '对话不存在或已删除')
