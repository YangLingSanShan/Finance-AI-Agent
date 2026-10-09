"""Opt-in public financial intelligence acceptance. No business DB writes or LLM use."""
import json
from pathlib import Path
from app.market import insights, disclosures


def main():
    checks = {
        'stock_flow': lambda: insights.fund_flow('600519', 60),
        'market_flow': lambda: insights.fund_flow(days=20),
        'margin': lambda: insights.margin_history(20),
        'northbound': lambda: insights.northbound_history(20),
        'industry_rotation': lambda: insights.sector_rotation('industry', 5),
        'concept_rotation': lambda: insights.sector_rotation('concept', 5),
        'valuation': lambda: insights.valuation_percentiles('600519', 3),
        'disclosures': lambda: disclosures.regulatory_events('600518'),
    }
    results = {}
    for name, call in checks.items():
        try:
            result = call()
            results[name] = result
            print(name, result['status'], result.get('as_of'), result.get('coverage'), flush=True)
        except Exception as exc:
            results[name] = {'status': 'error', 'error': str(exc)}
            print(name, 'ERROR', str(exc), flush=True)
    events = results.get('disclosures', {}).get('data') or []
    if events:
        try:
            results['announcement'] = disclosures.announcement_content(events[0]['document_url'])
            print('announcement', results['announcement']['status'], flush=True)
        except Exception as exc:
            results['announcement'] = {'status': 'error', 'error': str(exc)}
            print('announcement', 'ERROR', str(exc), flush=True)
    target = Path(__file__).resolve().parents[2] / 'docs/acceptance/market/insights-live.json'
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    raise SystemExit(1 if any(r['status'] != 'ok' for r in results.values()) else 0)


if __name__ == '__main__':
    main()
