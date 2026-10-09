"""CNINFO issuer disclosures. Search coverage is never a no-litigation certificate."""
import html
import io
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import httpx
from pypdf import PdfReader

from app.market.data import MarketDataError, SHANGHAI, envelope, payload, symbol

CNINFO = 'https://www.cninfo.com.cn'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': CNINFO + '/'}
EVENT_TERMS = {
    'litigation_arbitration': ('诉讼', '仲裁', '起诉', '判决', '裁定', '应诉', '民事调解'),
    'investigation': ('立案', '调查通知', '调查进展'),
    'penalty': ('行政处罚', '处罚决定', '处罚事先告知'),
    'exchange_supervision': ('监管', '警示函', '纪律处分', '公开谴责', '通报批评', '问询函', '关注函', '责令改正'),
    'enforcement_bankruptcy': ('执行', '冻结', '查封', '破产', '重整'),
}


def cn_request(path, form=None):
    try:
        if form is None:
            response = httpx.get(CNINFO + path, headers=HEADERS, timeout=8)
        else:
            response = httpx.post(CNINFO + path, data=form, headers=HEADERS, timeout=8)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise MarketDataError('巨潮公告服务不可用；不能将查询失败解释为无监管或诉讼事件') from exc


def regulatory_events(stock_code, start_date=None, end_date=None, start_page=1):
    symbol(stock_code)
    today = datetime.now(SHANGHAI).date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else today
    start = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else end - timedelta(days=1095)
    if not start <= end <= today or (end - start).days > 3660 or not 1 <= start_page <= 1000:
        raise MarketDataError('日期范围应在过去10年窗口内，起始日不晚于结束日；start_page 为1–1000')
    listing = payload(cn_request('/new/data/szse_stock.json'))
    stock = next((r for r in listing.get('stockList', []) if r.get('code') == stock_code), None)
    if not stock or not stock.get('orgId'):
        raise MarketDataError('巨潮证券目录未找到该公司，不能生成无事件结论')
    form = dict(pageNum=start_page, pageSize=30, column='szse', tabName='fulltext', plate='',
        stock=f"{stock_code},{stock['orgId']}", searchkey='', secid='', category='', trade='',
        seDate=f'{start}~{end}', sortName='', sortType='', isHLtitle='true')
    records, seen = [], set()
    fetched, total, pages = 0, None, 0
    complete, errors, scanned_pages = True, [], []
    started = time.monotonic()
    for page in range(start_page, start_page + 20):
        if time.monotonic() - started > 18:
            complete = False
            errors.append('达到本次查询时间上限，请从 next_page 继续。')
            break
        try:
            body = payload(cn_request('/new/hisAnnouncement/query', form | {'pageNum': page}))
            if 'totalAnnouncement' not in body or 'announcements' not in body:
                raise MarketDataError('巨潮响应缺少总数或公告字段')
            current_total = int(body['totalAnnouncement'])
            if total is not None and current_total != total:
                raise MarketDataError('公告总数在分页过程中发生变化，请重新查询')
            total = current_total
            pages = (total + 29) // 30
            rows = body['announcements'] or []
            if total and not rows and page <= pages:
                raise MarketDataError('公告分页意外为空')
            if total == 0 and rows:
                raise MarketDataError('公告总数与记录不一致')
            if total and page > pages:
                raise MarketDataError('start_page 超出公告总页数')
            for row in rows:
                # A shared filing can carry multiple comma-separated security codes.
                if stock_code not in re.split(r'[,;]', row.get('secCode') or ''):
                    raise MarketDataError('公告证券代码不匹配')
                key = str(row['announcementId'])
                if key in seen:
                    raise MarketDataError('公告分页重复，覆盖情况无法确认')
                seen.add(key)
                date = datetime.fromtimestamp(float(row['announcementTime']) / 1000, SHANGHAI).date().isoformat()
                if not str(start) <= date <= str(end):
                    raise MarketDataError('公告日期超出查询范围')
                title = html.unescape(re.sub('<[^>]+>', '', row['announcementTitle']))
                categories = [category for category, terms in EVENT_TERMS.items() if any(t in title for t in terms)]
                if not categories:
                    continue
                path = row.get('adjunctUrl') or ''
                document_url = 'https://static.cninfo.com.cn/' + path if re.fullmatch(
                    r'finalpage/\d{4}-\d{2}-\d{2}/\d+\.[pP][dD][fF]', path) else None
                records.append(dict(id=key, stock_code=stock_code, company=stock.get('zwjc'),
                    disclosure_date=date, title=title, categories=categories,
                    evidence_level='announcement_title', document_url=document_url,
                    source_url=f'{CNINFO}/new/disclosure/detail?stockCode={stock_code}&announcementId={key}&orgId={stock["orgId"]}',
                    legal_status='需阅读公告原文确认，标题分类不等于违法/败诉认定'))
            fetched += len(rows)
            scanned_pages.append(page)
            if page >= pages:
                break
        except (MarketDataError, ValueError, KeyError, TypeError) as exc:
            if not scanned_pages:
                raise MarketDataError(str(exc)) from exc
            complete = False
            errors.append(str(exc))
            break
    next_page = (scanned_pages[-1] + 1) if scanned_pages and scanned_pages[-1] < pages else None
    complete = complete and start_page == 1 and next_page is None and fetched == total
    records.sort(key=lambda r: (r['disclosure_date'], r['id']), reverse=True)
    warnings = ['范围仅为巨潮收录的该上市公司披露公告，按标题关键词筛选。未覆盖全国法院/执行库全量案件、全部子公司、未披露事件及监管机关独立发文全量。',
                '未命中只表示所扫描公告标题没有匹配项，不代表没有处罚或诉讼；财报正文中提及的事件可能未被标题筛选命中。',
                '问询/立案不等于处罚，起诉/仲裁不等于败诉；必须调用公告原文工具核实主体、阶段、金额和日期。'] + errors
    return envelope('巨潮资讯上市公司公告', CNINFO + '/new/hisAnnouncement/query', records,
        max((r['disclosure_date'] for r in records), default=None), warnings) | {
        'status': 'ok' if complete else 'partial', 'stock_code': stock_code,
        'coverage': dict(start_date=str(start), end_date=str(end), total_announcements=total,
            scanned_announcements=fetched, scanned_pages=scanned_pages, title_scan_complete=complete,
            next_page=next_page, scope_complete=False),
        'query': form, 'matched_announcements': len(records),
        'search_terms': EVENT_TERMS, 'absence_means': 'no_matching_titles_in_scanned_pages_only'}


def announcement_content(document_url):
    parsed = urlsplit(document_url)
    if (parsed.scheme != 'https' or parsed.netloc != 'static.cninfo.com.cn' or parsed.query or parsed.fragment
        or not re.fullmatch(r'/finalpage/\d{4}-\d{2}-\d{2}/\d+\.[pP][dD][fF]', parsed.path)):
        raise MarketDataError('仅接受巨潮公告查询返回的 static.cninfo.com.cn PDF 原文链接')
    try:
        with httpx.stream('GET', document_url, headers=HEADERS, timeout=10, follow_redirects=False) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    raise MarketDataError('公告超过8MB，请直接打开原文阅读')
                chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise MarketDataError('公告原文下载失败，请直接打开来源链接核实') from exc
    raw = b''.join(chunks)
    if not raw.startswith(b'%PDF'):
        raise MarketDataError('原文接口没有返回PDF，可能被限流')
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or len(reader.pages) > 80:
            raise MarketDataError('公告加密或超过80页，请直接打开原文阅读')
        pages, remaining = [], 24000
        truncated = False
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            if len(text) > remaining:
                truncated = True
            pages.append(dict(page=i, text=text[:remaining]))
            remaining -= min(len(text), remaining)
            if remaining == 0:
                truncated = truncated or i < len(reader.pages)
                break
    except MarketDataError:
        raise
    except Exception as exc:
        raise MarketDataError('公告PDF解析失败，请打开原文核实') from exc
    if not any(p['text'].strip() for p in pages):
        raise MarketDataError('公告为扫描页或没有可提取文字，不能据空文本判断无风险')
    return envelope('巨潮公告原文', document_url, pages, warnings=[
        'PDF文字提取可能改变表格布局；金额、主体、结论需结合页码和原文核对。',
        '公告日期由公告列表提供，不把文档下载时间当成事件发生时间。']) | {
        'status': 'partial' if truncated else 'ok', 'total_pages': len(reader.pages), 'truncated': truncated}
