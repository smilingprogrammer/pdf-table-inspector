import csv
import json
from decimal import Decimal
from .cell_exports import FIELDS,long_cells
from .html_preview import page_html,document_html


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f'Cannot serialize {type(value).__name__}')


def export_page(page, entry, tables, diagnostics, destination, config, record_error):
    """Attempt each artifact separately; preserve successful outputs and errors."""
    prefix = f"page-{entry['page']:03d}"

    def attempt(kind, filename, action):
        try:
            action(destination / filename)
            return filename
        except Exception as error:
            record_error(kind, error)
            return None

    entry['text_file'] = attempt('export_text', f'{prefix}-text.txt',
        lambda path: path.write_text(entry['text'], encoding='utf-8'))
    for table in tables:
        structure = next(t for t in entry['tables'] if t['id']==table.id)
        def write_csv(path, table=table):
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerows(structure.get('headers',{}).get('display_rows',table.to_dict()['rows']))
        structure['exports'] = {'table_csv':attempt('export_csv', table.csv, write_csv)}
        def write_raw(path, table=table):
            with path.open('w',encoding='utf-8-sig',newline='') as f:
                csv.writer(f).writerows(table.to_dict()['rows'])
        structure['exports']['raw_csv'] = attempt('export_raw_csv', table.csv.replace('.csv','-raw.csv'), write_raw)
    entry['display_html'] = attempt('export_html',f'{prefix}-tables.html',
        lambda path:path.write_text(page_html(entry),encoding='utf-8'))
    entry['cell_csv'] = attempt('export_cell_csv',f'{prefix}-cells.csv',
        lambda path:write_long_csv(path,[entry]))
    if config.render:
        entry['source_image'] = attempt('render_source', f'{prefix}-source.png',
            lambda path: page.to_image(resolution=config.resolution).save(path))
        def overlay(path):
            image = page.to_image(resolution=config.resolution)
            image.draw_rects([t.bbox for t in tables], fill=(0, 0, 255, 30))
            image.draw_rects([c.bbox for t in tables for c in t.cells if c.bbox],
                             fill=None, stroke='red', stroke_width=1)
            image.draw_rects([h['bbox'] for t in entry['tables'] for h in t.get('headers',{}).get('items',[])],
                             fill=None,stroke='green',stroke_width=2)
            for edge in diagnostics.get('edges', []):
                image.draw_line([(edge['x0'], edge['top']), (edge['x1'], edge['bottom'])],
                                stroke='red', stroke_width=1)
            image.save(path)
        if entry['engine_run']['status'] in ('success', 'no_tables'):
            entry['detector_image'] = attempt('render_detector', f'{prefix}-detector.png', overlay)


def write_long_csv(path,pages):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS)
        writer.writeheader()
        for page in pages:
            writer.writerows(long_cells(page))


def export_report(report, destination):
    report['exports']={'json':'report.json'}
    for kind,name,action in [
        ('cell_csv','cells.csv',lambda p:write_long_csv(p,report['pages'])),
        ('html','preview.html',lambda p:p.write_text(document_html(report),encoding='utf-8'))]:
        try:
            action(destination/name)
            report['exports'][kind]=name
        except Exception as exc:
            report['errors'].append({'stage':'export_'+kind,'type':type(exc).__name__,'message':str(exc)})
            report['status']='partial'
    (destination / 'report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=json_value), encoding='utf-8')
