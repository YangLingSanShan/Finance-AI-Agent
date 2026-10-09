"""Opt-in real-service acceptance; run only against a dedicated local test database."""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs/acceptance/p0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000/api/v1')
    parser.add_argument('--output', type=Path, default=DATA / 'live-results.json')
    args = parser.parse_args()
    results = {'checks': {}, 'questions': []}
    client = httpx.Client(base_url=args.base_url, timeout=240)

    def call(method, path, **kw):
        r = client.request(method, path, **kw)
        r.raise_for_status()
        return r.json()

    def save():
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')

    def check(name, condition):
        results['checks'][name] = bool(condition)
        save()
        print(name, 'PASS' if condition else 'FAIL', flush=True)
        assert condition, name

    manifest = json.loads((DATA / 'corpus/manifest.json').read_text())
    for item in manifest:
        data = (DATA / 'corpus' / item['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        fields = {'title': item['title'], 'category': item['category'],
                  'metadata': json.dumps(item['metadata'])}
        first = call('POST', '/rag/knowledge/upload', data=fields, files={'file': (item['file'], data)})
        again = call('POST', '/rag/knowledge/upload', data=fields, files={'file': (item['file'], data)})
        check('upload-dedup-' + item['file'], first['id'] == again['id'] and first['status'] == 'indexed')

    for q in json.loads((DATA / 'questions.json').read_text()):
        retrieval = call('POST', '/rag/query', json={'query': q['question'], 'top_k': 5,
                          'filters': {'stock_code': q['stock_code']}})
        answer = call('POST', '/chat', json={'session_id': '', 'message': q['question'],
                                           'agent_type': 'researcher', 'enable_rag': True, 'stream': False})
        sources = answer.get('sources') or []
        cited = set(re.findall(r'\[来源(\d+)\]', answer['message']))
        supported = [s for s in sources if s['metadata'].get('page') in q['pages'] and
                     s['citation'].removeprefix('来源') in cited]
        row = {'id': q['id'], 'retrieval': retrieval, 'answer': answer}
        results['questions'].append(row)
        save()
        check(q['id'] + '-company', all(s['metadata']['stock_code'] == q['stock_code'] for s in sources))
        if q['expected']:
            check(q['id'] + '-answer', all(v in answer['message'] for v in q['expected']))
            check(q['id'] + '-citation', bool(supported) and bool(cited) and
                  all(any(v in s['content'] for s in supported) for v in q['expected']) and
                  cited <= {str(i + 1) for i in range(len(sources))})
            check(q['id'] + '-recall', all(any(v in c['content'] and c['metadata'].get('page') in q['pages']
                  for c in retrieval['chunks']) for v in q['expected']))
        else:
            check(q['id'] + '-empty', not sources and not retrieval['chunks'])
            check(q['id'] + '-abstain', any(v in answer['message'] for v in ('无法', '不足', '没有')) and not cited)
        history = call('GET', '/conversations/' + answer['session_id'])['messages'][-1]
        check(q['id'] + '-history', history['content'] == answer['message'] and history['sources'] == sources)

    excluded = call('POST', '/rag/query', json={'query': '分红', 'filters': {
        'stock_code': '600519', 'disclosure_date': {'$lte': '2025-01-01'}}})
    check('date-exclusion', not excluded['chunks'])
    included = call('POST', '/rag/query', json={'query': '分红', 'filters': {
        'stock_code': '600519', 'disclosure_date': {'$gte': '2025-11-06', '$lte': '2025-11-06'}}})
    check('date-boundary', bool(included['chunks']))

    # Disposable copy of a real announcement; change metadata, not financial facts.
    item = manifest[0]
    fields = {'title': item['title'] + '（生命周期验收副本）', 'category': item['category'],
              'metadata': json.dumps(item['metadata'])}
    data = (DATA / 'corpus' / item['file']).read_bytes()
    copy = call('POST', '/rag/knowledge/upload', data=fields, files={'file': (item['file'], data)})
    fields.update(doc_id=copy['id'], title=fields['title'] + '更新')
    updated = call('POST', '/rag/knowledge/upload', data=fields, files={'file': (item['file'], data)})
    found = call('POST', '/rag/query', json={'query': '分红', 'filters': {'doc_id': copy['id']}})
    check('update', bool(found['chunks']) and all(c['metadata']['title'] == updated['title'] for c in found['chunks']))
    call('DELETE', '/rag/knowledge/documents/' + copy['id'])
    found = call('POST', '/rag/query', json={'query': '分红', 'filters': {'doc_id': copy['id']}})
    check('delete', not found['chunks'])

    report = call('POST', '/reports', json={'stock_code': '600519', 'enable_rag': True,
        'query': '仅基于知识库2025年中期分红公告，生成简短的分红专题报告：每股金额、审议条件、风险、证据局限。各角色不超过300字，不调用金融工具；如提及金融工具必须标为演示数据。保留[来源N]。'})
    for _ in range(120):
        report = call('GET', '/reports/' + report['id'])
        if report['status'] in ('completed', 'failed'):
            break
        time.sleep(2)
    results['report'] = report
    save()
    check('report-completed', report['status'] == 'completed')
    run = call('GET', '/agent/runs/' + report['run_id'])
    results['run'] = run
    save()
    download = client.get('/reports/' + report['id'] + '/download')
    check('download-equal', download.status_code == 200 and download.text == report['content'])
    check('report-evidence', '23.957' in report['content'] and bool(re.search(r'\[来源\d+\]', report['content'])))
    check('report-appendix', all(s['label'] in report['content'] and s['content'] in report['content']
                               for s in report['sources']))
    client.close()


if __name__ == '__main__':
    main()
