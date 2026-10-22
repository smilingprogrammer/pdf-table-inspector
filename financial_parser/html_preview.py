"""HTML presentation only; all PDF-derived strings and IDs are escaped."""
from html import escape

STYLE='<style>body{font:16px sans-serif;margin:32px}table{border-collapse:collapse;margin:24px 0}td,th{border:1px solid #aaa;padding:6px;white-space:pre-wrap}caption{text-align:left;font-size:12px}th{background:#eef3f8}.error{color:#a00}</style>'


def page_tables(entry):
    parts=[]
    for structure in entry['tables']:
        parts.append('<table><caption>'+escape(structure['id'])+'</caption>')
        headers=structure.get('headers',{})
        display=headers.get('display_rows',structure['rows'])
        prefix_count=max(0,len(display)-structure['row_count'])
        for row in display[:prefix_count]:
            parts.append('<tr>'+''.join('<td>'+escape(v or '')+'</td>' for v in row)+'</tr>')
        header_ids={identity for h in headers.get('items',[]) if h['role']=='column_header' for identity in h['cell_ids']}
        header_rows={c['row'] for c in structure['cells'] if c['id'] in header_ids}
        for r in range(structure['row_count']):
            parts.append('<tr>')
            for cell in sorted((c for c in structure['cells'] if c['row']==r),key=lambda c:c['column']):
                tag='th' if cell['row'] in header_rows else 'td'
                rowspan=cell['row_span'] if isinstance(cell['row_span'],int) and cell['row_span']>0 else 1
                colspan=cell['column_span'] if isinstance(cell['column_span'],int) and cell['column_span']>0 else 1
                parts.append(f'<{tag} data-cell-id="{escape(cell["id"],quote=True)}" rowspan="{rowspan}" colspan="{colspan}">'+escape(cell['raw_text'] or '')+f'</{tag}>')
            parts.append('</tr>')
        parts.append('</table>')
    for error in entry.get('errors',[]):
        parts.append('<p class="error">'+escape(f"{error['stage']}: {error['message']}")+'</p>')
    for warning in entry.get('warnings',[]):
        parts.append('<p>'+escape(f"{warning['code']}: {warning['message']}")+'</p>')
    return '\n'.join(parts)


def page_html(entry):
    return '<!doctype html><meta charset="utf-8"><title>Extracted tables</title>'+STYLE+page_tables(entry)


def document_html(report):
    parts=['<!doctype html><meta charset="utf-8"><title>PDF table candidates</title>',STYLE,
           '<h1>'+escape(report['source'])+'</h1>']
    for error in report['errors']:
        parts.append('<p class="error">'+escape(f"{error['stage']}: {error['message']}")+'</p>')
    for page in report['pages']:
        parts.extend([f'<h2>Page {page["page"]}</h2>',page_tables(page)])
    return '\n'.join(parts)
