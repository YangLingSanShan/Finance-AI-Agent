"""Opt-in public-data acceptance; no LLM requests or business database writes."""
import json
from pathlib import Path
from app.market import data as market


def main():
    checks = {
        'market': market.market_overview,
        'quote': lambda: market.stock_quote('600519'),
        'info': lambda: market.stock_info('600519'),
        'kline': lambda: market.stock_kline('600519', 60),
        'financials': lambda: market.stock_financials('600519', 'quarterly'),
        'annual': lambda: market.stock_financials('600519', 'annual'),
        'news': lambda: market.financial_news('600519', 3),
        'risk': lambda: market.risk_metrics('600519', 60),
    }
    for code in ('000001', '300750'):
        for name, fn in (('quote', market.stock_quote), ('info', market.stock_info),
                         ('financials', market.stock_financials), ('kline', market.stock_kline),
                         ('risk', market.risk_metrics)):
            checks[f'{code}_{name}'] = lambda code=code, fn=fn: fn(code)
    results = {}
    failed = False
    for name, call in checks.items():
        try:
            results[name] = call()
            assert results[name]['status'] == 'ok'
            print(name, 'PASS', results[name].get('as_of'), flush=True)
        except Exception as exc:
            results[name] = {'status': 'error', 'error': str(exc)}
            failed = True
            print(name, 'FAIL', str(exc), flush=True)
    target = Path(__file__).resolve().parents[2] / 'docs/acceptance/market/live-results.json'
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
