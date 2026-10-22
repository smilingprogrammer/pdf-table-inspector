"""Coordinate stages; table engines communicate only through canonical models."""
import hashlib
from dataclasses import asdict
from pathlib import Path
import pdfplumber
from .adapters import PageInput, get_adapter
from .config import ParseConfig
from .context import extract_context, outside_text
from .normalization import normalize
from .validation import validate
from .exports import export_page, export_report
from .execution import execute
from .headers import attach_headers
from .provenance import engine_versions


def parse(source, destination, config=None, *, adapter=None):
    source, destination = Path(source), Path(destination)
    config = config or ParseConfig()
    engine = adapter if adapter is not None else (None if config.engine in ('auto','compare') else get_adapter(config.engine))
    engine_name = engine.name if engine is not None else config.engine
    planned_engines = config.engines if engine is None else (engine_name,)
    if engine is None and config.engine=='auto':
        planned_engines=('pdfplumber-lines',)+tuple(n for n in planned_engines if n!='pdfplumber-lines')
    destination.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 9, 'source': str(source), 'source_sha256':None,
              'hash_algorithm':'sha256', 'config': asdict(config),
              'engine_versions':engine_versions(planned_engines),
              'engine': engine_name, 'pages': [], 'errors': []}
    try:
        document_id = hashlib.sha256(source.read_bytes()).hexdigest()
        report['document_id'] = document_id
        report['source_sha256'] = document_id
        with pdfplumber.open(source) as pdf:
            for number in (config.pages if config.pages is not None else range(1, len(pdf.pages) + 1)):
                entry = {'page': number, 'source_sha256':document_id, 'text': '', 'tables': [], 'errors': [], 'warnings': [],
                         'engine_runs': [{'engine': name, 'status': 'not_run', 'table_count': 0}
                                         for name in planned_engines],
                         'engine_run': {'engine': engine_name, 'status': 'not_run',
                                        'table_count': 0}}
                report['pages'].append(entry)

                def error(stage, exc, engine=None):
                    entry['errors'].append({'stage': stage, 'type': type(exc).__name__,
                                            'message': str(exc), **({'engine':engine} if engine else {})})

                try:
                    if not 1 <= number <= len(pdf.pages):
                        raise IndexError(f'Page {number} outside valid range 1..{len(pdf.pages)}')
                    page = pdf.pages[number - 1]
                except Exception as exc:
                    error('load_page', exc)
                    entry['engine_run']['reason'] = 'page_load_failed'
                    entry['status'] = 'failed'
                    for run in entry['engine_runs']:
                        run['reason']='invalid_page' if isinstance(exc,IndexError) else 'page_load_failed'
                    continue
                try:
                    entry.update(extract_context(page, config))
                except Exception as exc:
                    error('context', exc)
                tables, diagnostics = (), {}
                if entry.get('text_status') == 'review_for_ocr':
                    entry['warnings'].append({'code':'ocr_required' if not entry.get('character_count') and entry.get('image_count') else 'ocr_review_required',
                        'message':'Image-only page requires OCR; OCR is not implemented.' if not entry.get('character_count') and entry.get('image_count') else 'Insufficient usable text; review this page for OCR.'})
                    entry['engine_run'].update(status='skipped', reason='review_for_ocr')
                    for run in entry['engine_runs']:
                        run.update(status='skipped', reason='review_for_ocr')
                else:
                    try:
                        tables, runs, ranking = execute(
                            PageInput(source, document_id, number), config,
                            entry.get('characters', []), [page.width,page.height], error, adapter)
                        entry['engine_runs'] = runs
                        entry['ranking'] = ranking
                        statuses = [r['status'] for r in runs]
                        status = ('success' if tables else 'failed' if 'failed' in statuses else 'unavailable' if 'unavailable' in statuses else 'no_tables')
                        diagnostics = {'edges':[edge for r in runs for edge in r.get('diagnostics',{}).get('edges',[])]}
                        entry['engine_run'].update(status=status,table_count=len(tables),diagnostics=diagnostics)
                        if engine is not None and len(runs)==1:
                            entry['engine_run'] = runs[0]
                    except Exception as exc:
                        error('execution', exc)
                        entry['engine_run']['status'] = 'failed'
                try:
                    entry['validation'] = validate(tables, number, [page.width, page.height])
                    entry['structural_validation'] = {
                        'status':'invalid' if entry['validation'] else 'valid',
                        'issues':entry['validation']}
                    entry['tables'] = [t.to_dict() for t in tables]
                    for issue in entry['validation']:
                        identity = issue['id']
                        for table in tables:
                            if identity == table.id or any(c.id==identity for c in table.cells):
                                measurement=entry.get('ranking',{}).get('measurements',{}).get(table.id)
                                if measurement:
                                    measurement['possible_failure']=True
                                    measurement['flags'].append('structural_validation_issue')
                except Exception as exc:
                    error('validation', exc)
                for table, structure in zip(tables, entry['tables']):
                    try:
                        structure['headers'] = attach_headers(page, table, config)
                    except Exception as exc:
                        error('header_association', exc)
                try:
                    entry['normalized_cells'] = normalize(tables, config)
                except Exception as exc:
                    error('normalization', exc)
                try:
                    entry['text_outside_tables'] = outside_text(page, tables)
                except Exception as exc:
                    error('context_outside_tables', exc)
                try:
                    export_page(page, entry, tables, diagnostics, destination, config, error)
                except Exception as exc:
                    error('exports', exc)
                entry['status'] = ('partial' if entry['errors'] or entry.get('validation')
                                   else 'ocr_required' if entry['warnings'] else 'complete')
    except Exception as exc:
        report['errors'].append({'stage': 'document', 'type': type(exc).__name__, 'message': str(exc)})
    report['status'] = ('partial' if report['errors'] or any(
        p['status'] != 'complete' for p in report['pages']) else 'complete')
    export_report(report, destination)
    return report
