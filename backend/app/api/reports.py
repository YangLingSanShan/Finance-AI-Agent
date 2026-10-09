"""Report jobs and immutable Markdown results. Single backend worker required."""
import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.agents.orchestrator import get_orchestrator
from app.models.schemas import AgentType
from app.config import get_settings
from app.market.data import DATA_POLICY

router = APIRouter(prefix='/reports')
logger = logging.getLogger(__name__)


class ReportRequest(BaseModel):
    stock_code: str = Field(pattern=r'^[0-9]{6}$')
    query: str = Field(default='生成完整投研报告', min_length=1, max_length=4000)
    enable_rag: bool = False


async def generate(report, enable_rag):
    orchestrator = get_orchestrator()
    try:
        context = {'data_note': DATA_POLICY}
        if enable_rag:
            from app.rag.retriever import get_hybrid_retriever, evidence_context
            try:
                context['rag_context'] = evidence_context(await get_hybrid_retriever().retrieve(
                    report['query'], top_k=5, filters={'stock_code': report['stock_code']}))
            except Exception as exc:
                raise RuntimeError('知识库检索服务暂不可用，请稍后重新提交报告') from exc
        await orchestrator.run(query=report['query'], session_id=report['session_id'],
            agent_types=[AgentType.REPORT], parallel=True, context=context, report_id=report['id'])
    except BaseException as exc:
        error = '任务取消或服务关闭' if isinstance(exc, asyncio.CancelledError) else str(exc)
        await asyncio.to_thread(orchestrator.store.fail_report, report['id'], error)
        logger.warning('Report generation failed: %s', report['id'])
        if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
            raise


@router.post('', status_code=202)
async def create_report(request: ReportRequest, tasks: BackgroundTasks):
    store = get_orchestrator().store
    session = await asyncio.to_thread(store.create)
    query = f'为股票{request.stock_code}生成报告。{request.query}'
    report = await asyncio.to_thread(store.create_report, f'{request.stock_code} 投研报告',
        request.stock_code, query, session['id'], get_settings().LLM_MODEL)
    tasks.add_task(generate, report, request.enable_rag)
    return report


@router.get('')
def list_reports():
    return get_orchestrator().store.list_reports()


@router.get('/{report_id}')
def get_report(report_id: str):
    try:
        return get_orchestrator().store.get_report(report_id)
    except KeyError:
        raise HTTPException(404, '报告不存在')


@router.get('/{report_id}/download')
def download_report(report_id: str):
    report = get_report(report_id)
    if report['status'] != 'completed':
        raise HTTPException(409, '报告尚未成功生成')
    return Response(report['content'], media_type='text/markdown; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="report-{report_id}.md"'})


@router.delete('/{report_id}', status_code=204)
def delete_report(report_id: str):
    try:
        get_orchestrator().store.delete_report(report_id)
    except KeyError:
        raise HTTPException(404, '报告不存在')
    except ValueError as exc:
        raise HTTPException(409, str(exc))
