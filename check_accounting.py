"""Run explicit relationships after extraction; never alter the parse report."""
import argparse
import json
from pathlib import Path
from financial_parser.accounting import check_accounting
from financial_parser.exports import json_value
from financial_parser.validation import validate
from table_models import Cell,TableCandidate


def assess(report,spec,table_number=1):
    page=next(p for p in report['pages'] if p['page']==spec['page'])
    table=page['tables'][table_number-1]
    model=TableCandidate(table['id'],table['page'],table['bbox'],table['row_count'],table['column_count'],
                         tuple(Cell(**c) for c in table['cells']),table['csv'])
    issues=validate([model],page['page'],page['size'])
    return {'structural_validation':{'issues':issues,'status':'valid' if not issues else 'invalid'},
            'ranking_diagnostics':page.get('ranking',{}).get('measurements',{}).get(table['id']),
            'accounting':check_accounting(table,spec,structure_issues=issues)}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--report',type=Path,default=Path('output/headers/report.json'))
    cli.add_argument('--relationships',type=Path,default=Path('data/financial-sample.relationships.json'))
    cli.add_argument('--table',type=int,default=1)
    cli.add_argument('--out',type=Path,default=Path('output/headers/accounting.json'))
    args=cli.parse_args()
    if args.table<1: cli.error('--table must be positive')
    result=assess(json.loads(args.report.read_text()),json.loads(args.relationships.read_text()),args.table)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=json_value),encoding='utf-8')
    accounting=result['accounting']
    print('Grid:',result['structural_validation']['status'],'Accounting:',accounting['status'],accounting.get('summary',{}))
    for c in accounting['discrepancies']:
        print(f"{c['relationship_id']} {c['kind']} {c['period']}: displayed {c['displayed']}, computed {c['computed']}, difference {c['difference']:+}")
    return 1 if result['structural_validation']['issues'] or accounting['status']!='checked' or accounting.get('summary',{}).get('unresolved') else 0


if __name__=='__main__':
    raise SystemExit(main())
