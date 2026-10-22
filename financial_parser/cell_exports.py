"""Long-form export retains cell identity and distinguishes context from body."""
FIELDS=['source_sha256','engine','page','table_id','cell_id','cell_kind','context_source',
        'row','column','row_span','column_span','raw_text','is_missing',
        'x0','top','x1','bottom','number_status','number_value','number_profile','referenced_cell_ids']


def long_cells(entry):
    for table in entry['tables']:
        engine=entry.get('ranking',{}).get('candidate_engines',{}).get(table['id'],entry['engine_run']['engine'])
        common={'source_sha256':entry.get('source_sha256'),'engine':engine,'page':entry['page'],'table_id':table['id']}
        items=table.get('headers',{}).get('items',[])
        inside={identity:item for item in items if item['source']=='inside_grid' for identity in item['cell_ids']}
        header_rows={cell['row'] for cell in table['cells'] if cell['id'] in inside and inside[cell['id']]['role']=='column_header'}
        for cell in table['cells']:
            item=inside.get(cell['id'])
            number=entry.get('normalized_cells',{}).get(cell['id'],{}).get('number',{})
            box=cell['bbox'] or [None]*4
            yield {**common,'cell_id':cell['id'],'cell_kind':('caption' if item['role']=='unit' else 'header') if item else 'header' if cell['row'] in header_rows else 'body',
                   'context_source':'inside_grid','raw_text':cell['raw_text'],'is_missing':cell['raw_text'] is None,
                   **{key:cell[key] for key in ('row','column','row_span','column_span')},
                   **dict(zip(('x0','top','x1','bottom'),box)),
                   'number_status':number.get('status'),'number_value':number.get('value'),
                   'number_profile':number.get('profile'),'referenced_cell_ids':''}
        tops=sorted({item['bbox'][1] for item in items if item['role']=='column_header'})
        for item in items:
            if item['source']=='inside_grid': continue
            yield {**common,'cell_id':item['id'],'cell_kind':'caption' if item['role']=='unit' else 'header',
                   'context_source':item['source'],'raw_text':item['raw_text'],'is_missing':False,
                   'row':tops.index(item['bbox'][1]) if item['role']=='column_header' else None,
                   'column':item['column'],'row_span':None,'column_span':None,
                   **dict(zip(('x0','top','x1','bottom'),item['bbox'])),
                   'referenced_cell_ids':'|'.join(item['cell_ids'])}
