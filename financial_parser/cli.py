"""Argument parsing and concise result reporting; processing lives in the pipeline."""
import argparse
from pathlib import Path
from . import ParseConfig,parse,parse_batch
from .adapters import ADAPTERS
from .numbers import PROFILES


def pages_argument(tokens):
    if tokens is None: return None
    pages=[]
    for token in tokens:
        for part in token.split(','):
            if '-' in part[1:]:
                start,end=part.split('-',1)
                start,end=int(start),int(end)
                if end<start: raise ValueError('Page ranges must be ascending')
                pages.extend(range(start,end+1))
            else: pages.append(int(part))
    return tuple(dict.fromkeys(pages))


def print_result(result):
    print(f"{result['source']}: {result['status']}")
    for error in result['errors']:
        print(f"  Error [{error['stage']}/{error['type']}]: {error['message']}")
    for page in result['pages']:
        run=page['engine_run']
        print(f"  Page {page['page']}: {run['engine']} {run['status']}; {run['table_count']} candidates")
        for warning in page.get('warnings',[]):
            print(f"    Warning [{warning['code']}]: {warning['message']}")
        for error in page['errors']:
            print(f"    Error [{error['stage']}/{error['type']}]: {error['message']}")
        for attempt in page.get('engine_runs',[]):
            if run['engine'] in ('auto','compare'):
                print(f"    {attempt['engine']}: {attempt['status']} ({attempt['table_count']} candidates)")
        for table in page['tables']:
            print(f"    {table['id']}: {table['row_count']} x {table['column_count']}")


def main(argv=None):
    cli=argparse.ArgumentParser(description='Extract reviewable PDF table candidates and provenance.')
    cli.add_argument('files',type=Path,nargs='*',metavar='PDF')
    cli.add_argument('--out',type=Path,default=Path('output/tables'))
    selection=cli.add_mutually_exclusive_group()
    selection.add_argument('--engine',choices=[*ADAPTERS,'auto','compare'])
    selection.add_argument('--compare',action='store_true',help='Retain candidates from every configured route')
    selection.add_argument('--strategy',choices=['lines','text'],help='Compatibility alias for a pdfplumber route')
    cli.add_argument('--engines',nargs='+',choices=list(ADAPTERS),help='Ordered routes for auto/compare')
    cli.add_argument('--number-format','--number-profile',dest='number_profile',choices=['auto',*PROFILES],default='auto')
    cli.add_argument('--pages',nargs='+',metavar='N[,N]|START-END',help='1-based page selections; invalid page numbers are retained as errors')
    cli.add_argument('--batch-files',type=Path,nargs='+',metavar='PDF',help='Additional files, always using isolated batch outputs')
    cli.add_argument('--batch-list',type=Path,action='append',metavar='FILE',help='UTF-8 list of PDF paths, one per line, relative to the list file')
    cli.add_argument('--no-render',action='store_true')
    args=cli.parse_args(argv)
    engine='compare' if args.compare else args.engine or f"pdfplumber-{args.strategy or 'lines'}"
    if args.engines and engine not in ('auto','compare'): cli.error('--engines requires --compare or --engine auto/compare')
    sources=args.files+(args.batch_files or [])
    try:
        pages=pages_argument(args.pages)
        for manifest in args.batch_list or []:
            sources.extend(manifest.parent/line.strip() for line in manifest.read_text(encoding='utf-8').splitlines()
                           if line.strip() and not line.lstrip().startswith('#'))
    except (ValueError,OSError) as exc: cli.error(str(exc))
    if not sources: cli.error('Provide at least one PDF or a batch file list')
    options={'engine':engine,'pages':pages,'number_profile':args.number_profile,'render':not args.no_render}
    if args.engines: options['engines']=tuple(args.engines)
    try:
        config=ParseConfig(**options)
    except ValueError as exc:
        cli.error(str(exc))
    if len(sources)>1 or args.batch_files is not None or args.batch_list:
        batch=parse_batch(sources,args.out,config)
        for document in batch['documents']:
            if 'result' in document: print_result(document['result'])
            else: print(f"{document['source']}: failed {document['errors']}")
        return int(batch['status']!='complete')
    result=parse(sources[0],args.out,config)
    print_result(result)
    return int(result['status']!='complete')
