"""Geometric heading associations, separate from the canonical extracted cells."""
from statistics import median
import re
from .numbers import parse_number


UNIT = re.compile(r'単位|\bunits?\b|\bin\s+(?:thousands|millions|billions)\b', re.I)


def bbox(words):
    return [min(w['x0'] for w in words),min(w['top'] for w in words),
            max(w['x1'] for w in words),max(w['bottom'] for w in words)]


def attach_headers(page, table, config):
    numeric = [c for c in table.cells if c.bbox and
               parse_number(c.raw_text).status in ('number','ambiguous')]
    if not numeric:
        return {'items':[], 'rows':[], 'unit':None, 'display_rows':table.to_dict()['rows']}
    numeric_columns = sorted({c.column for c in numeric})
    columns = {col:(median(c.bbox[0] for c in numeric if c.column==col),
                   median(c.bbox[2] for c in numeric if c.column==col)) for col in numeric_columns}
    first_numeric_top = min(c.bbox[1] for c in numeric)
    height = median(c.bbox[3]-c.bbox[1] for c in table.cells if c.bbox)
    window = (max(page.bbox[0],table.bbox[0]-config.header_horizontal_margin),
              max(page.bbox[1],first_numeric_top-height*config.header_search_lines),
              min(page.bbox[2],table.bbox[2]+config.header_horizontal_margin),first_numeric_top)
    # Cropped word positions remain in the page's top-left PDF coordinate system.
    words = page.crop(window).extract_words()
    words = [w for w in words if w['bottom'] <= first_numeric_top]
    lines=[]
    for word in sorted(words,key=lambda w:(w['top'],w['x0'])):
        if not lines or abs(word['top']-lines[-1][0]['top'])>config.header_line_tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)
    items=[]
    heading_lines=[]
    unit_lines=[]
    for line in lines:
        line=sorted(line,key=lambda w:w['x0'])
        text=' '.join(w['text'] for w in line)
        if UNIT.search(text):
            unit_lines.append(line)
            continue
        assignments={}
        for word in line:
            intersections={col:max(0,min(word['x1'],right)-max(word['x0'],left))
                           for col,(left,right) in columns.items()}
            col=max(intersections,key=intersections.get)
            if intersections[col]/max(word['x1']-word['x0'],1e-9)>=0.6:
                assignments.setdefault(col,[]).append(word)
        # Parallel headings over multiple numeric columns distinguish header bands
        # from chapter titles or a lone section label at the left of the page.
        if len(assignments)>=max(2,len(numeric_columns)//2+1):
            heading_lines.append((line,assignments))
    # Only a contiguous band adjacent to the table's first numeric row is eligible.
    accepted=[]
    anchor=table.bbox[1] if table.bbox[1]<first_numeric_top else first_numeric_top
    for line,assignments in reversed(heading_lines):
        box=bbox(line)
        if anchor-box[3] > height*config.header_max_gap_lines:
            break
        accepted.append((line,assignments))
        anchor=box[1]
    accepted.reverse()

    def add(role, line, column=None):
        box=bbox(line)
        matches=[c.id for c in table.cells if c.bbox and
                 any(c.bbox[0] <= (w['x0']+w['x1'])/2 < c.bbox[2] and
                     c.bbox[1] <= (w['top']+w['bottom'])/2 < c.bbox[3] for w in line)]
        item={'id':f'{table.id}:heading:{len(items)}','role':role,
              'raw_text':' '.join(w['text'] for w in line),'bbox':box,
              'column':column,'source':'inside_grid' if matches else 'outside_grid',
              'cell_ids':matches,
              'words':[{k:w[k] for k in ('text','x0','top','x1','bottom')} for w in line]}
        items.append(item)
        return item

    rows=[]
    outside_rows=[]
    for line,assignments in accepted:
        row=['']*table.column_count
        outside=['']*table.column_count
        for col,group in assignments.items():
            item=add('column_header',group,col)
            row[col]=item['raw_text']
            if item['source']=='outside_grid': outside[col]=item['raw_text']
        rows.append(row)
        if any(outside): outside_rows.append(outside)
    # A unit caption must be near and above the accepted header band/table top.
    unit_anchor=bbox(accepted[0][0])[1] if accepted else table.bbox[1]
    units=[]
    for line in unit_lines:
        box=bbox(line)
        if 0 <= unit_anchor-box[3] <= height*config.header_max_gap_lines:
            units.append(add('unit',line))
    units.sort(key=lambda item:item['bbox'][1])
    unit_rows=[]
    for unit in units:
        if unit['source']=='outside_grid':
            center=(unit['bbox'][0]+unit['bbox'][2])/2
            col=min(columns,key=lambda c:abs(center-sum(columns[c])/2))
            row=['']*table.column_count
            row[col]=unit['raw_text']
            unit_rows.append(row)
    return {'items':items,'rows':rows,'unit':units[0]['raw_text'] if len(units)==1 else None,
            'crop_bbox':list(window), 'column_bounds':{str(k):list(v) for k,v in columns.items()},
            'display_rows':unit_rows+outside_rows+table.to_dict()['rows'],
            'requires_review':True}
