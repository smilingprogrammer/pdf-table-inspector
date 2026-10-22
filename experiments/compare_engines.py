"""Keep all candidates from four independent routes; never auto-deduplicate."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from financial_parser import ParseConfig, parse
from evaluate import evaluate, compare


def compact(value):
    return ''.join((value or '').split())


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('pdf', type=Path)
    cli.add_argument('--out', type=Path, default=Path('output/engine-comparison'))
    cli.add_argument('--reference', type=Path, default=Path('data/financial-sample.reference.json'))
    args = cli.parse_args()
    reference = json.loads(args.reference.read_text())
    summary = {'source':str(args.pdf), 'routes':[],
        'notes':['Routes are independent; no selection, header promotion or content deduplication.',
                 'Strict scores use the unchanged reference evaluator and no row alignment.',
                 'Header text coverage ignores whitespace; it is not semantic column assignment.']}
    for engine in ('pdfplumber-lines','pdfplumber-text','camelot-stream','camelot-lattice'):
        destination = args.out / engine
        report = parse(args.pdf, destination, ParseConfig(engine=engine))
        page = next((p for p in report['pages'] if p['page']==reference['page']), None)
        route = {'engine':engine, 'report':str(destination/'report.json'),
                 'status':report['status'], 'document_errors':report['errors']}
        if page:
            route.update(engine_run=page['engine_run'], errors=page['errors'], candidates=[])
            for index, table in enumerate(page['tables']):
                score = evaluate(reference, report, index)
                cells = table['cells']
                fields = [s for row in reference['headers']['rows'] for s in row if s]
                fields.append(reference['headers']['unit'])
                coverage = [{'text':s, 'cell_ids':[c['id'] for c in cells
                            if compact(s) == compact(c['raw_text'])]} for s in fields]
                candidate = {'id':table['id'], 'dimensions':table['dimensions'],
                    'bbox':table['bbox'], 'strict_body':score['body'],
                    'structured_headers':score['headers'], 'header_cell_coverage':coverage}
                # Explicit sample-only derived comparison; do not modify canonical rows.
                if engine=='camelot-stream':
                    candidate['derived_body_after_skipping_two_header_rows_and_stripping'] = compare(
                        reference['body'], [[v.strip() if v is not None else None for v in row]
                                            for row in table['rows'][2:]])
                route['candidates'].append(candidate)
            print(engine, page['engine_run']['status'],
                  [t['dimensions'] for t in page['tables']], flush=True)
        summary['routes'].append(route)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'comparison.json').write_text(json.dumps(summary, ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
