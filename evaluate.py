"""Compare raw cells with a visual reference; arithmetic is a separate diagnostic."""
import argparse
import json
from pathlib import Path


def compare(expected, actual):
    mismatches = []
    passed = 0
    total = 0
    for row in range(max(len(expected), len(actual))):
        left = expected[row] if row < len(expected) else []
        right = actual[row] if row < len(actual) else []
        for col in range(max(len(left), len(right))):
            want = left[col] if col < len(left) else None
            got = right[col] if col < len(right) else None
            total += 1
            if want == got:
                passed += 1
            else:
                mismatches.append({'row': row + 1, 'column': col + 1,
                                   'expected': want, 'actual': got})
    return {'passed': passed, 'total': total, 'accuracy': passed / total if total else None,
            'mismatches': mismatches}


def number(raw):
    # Deliberately specific to this reference, not the general PDF parser.
    return 0 if raw == '－' else int(raw.replace(',', '').replace('△', '-'))


def evaluate(reference, report, table_index=0):
    page = next(p for p in report['pages'] if p['page'] == reference['page'])
    table = page['tables'][table_index] if table_index < len(page['tables']) else {}
    headers = table.get('headers', {})
    expected_headers = reference['headers']
    # Missing is distinct from an explicitly extracted blank cell.
    header_score = compare(expected_headers['rows'] + [[expected_headers['unit']]],
                           headers.get('rows', []) + [[headers.get('unit')]])
    body_score = compare(reference['body'], table.get('rows', []))
    compact_text = ''.join(page['text'].split())
    strings = [s for row in expected_headers['rows'] for s in row if s]
    strings.append(expected_headers['unit'])
    coverage = [{'text': s, 'present': ''.join(s.split()) in compact_text} for s in strings]
    checks = []
    for rule in reference['arithmetic']['rules']:
        for column in (1, 2):
            rows = reference['body']
            displayed = number(rows[rule['total']][column])
            computed = sum(number(rows[i][column]) for i in rule['items'])
            checks.append({'row': rule['total'] + 1, 'label': rows[rule['total']][0],
                           'column': column + 1, 'displayed': displayed,
                           'sum_of_displayed_items': computed,
                           'difference_displayed_minus_sum': displayed - computed})
    return {'body': body_score, 'headers': header_score,
            'header_text_coverage_only': {'passed': sum(x['present'] for x in coverage),
                                          'total': len(coverage), 'items': coverage},
            'reference_arithmetic': checks,
            'arithmetic_discrepancies': [c for c in checks if c['difference_displayed_minus_sum']],
            'notes': ['Exact raw-cell comparison; blank cells count and missing cells fail.',
                      'Header text presence does not prove column/year association.',
                      'Structured headers must be table.headers.rows and table.headers.unit.',
                      'Arithmetic differences do not alter transcription or extraction scores.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=Path('data/financial-sample.reference.json'))
    parser.add_argument('--report', type=Path, default=Path('output/tables/report.json'))
    parser.add_argument('--table', type=int, default=1, help='1-based table number on reference page')
    parser.add_argument('--out', type=Path, default=Path('output/tables/evaluation.json'))
    args = parser.parse_args()
    if args.table < 1:
        parser.error('--table must be positive')
    result = evaluate(json.loads(args.reference.read_text()), json.loads(args.report.read_text()), args.table - 1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    for key in ('body', 'headers', 'header_text_coverage_only'):
        score = result[key]
        print(f"{key}: {score['passed']}/{score['total']}")
    for item in result['arithmetic_discrepancies']:
        print(f"Reference row {item['row']}, column {item['column']}: {item['label']}: "
              f"displayed {item['displayed']}, sum {item['sum_of_displayed_items']}, "
              f"difference {item['difference_displayed_minus_sum']:+d}")
    raise SystemExit(0 if all(result[k]['passed'] == result[k]['total'] for k in ('body', 'headers')) else 1)
